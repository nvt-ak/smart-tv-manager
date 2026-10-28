"""LG second-screen control, independent of ADB and the Developer Mode installer.

One lock owns each socket's request/response stream. A cached socket can go stale while
the TV sleeps, so one transparent retry on a fresh connection is allowed in exactly two
cases: the frame could not be written at all (the TV never saw it), or the request is
read-only. A request that may already have reached the TV (launch, power, input switch,
text) is never replayed after a failure.
WSS uses trust-on-first-pairing certificate pinning because LG certificates are not
public-CA verifiable. Plain WS is only used when explicitly selecting port 3000.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import ssl
import tempfile
import threading
import time
from urllib.parse import urlsplit

from app_brand import user_data_dir


class WebOsError(Exception):
    """Recoverable TV connection, pairing or command failure."""


class WebOsCommandError(WebOsError):
    """TV explicitly refused a command; the transport is still usable."""


def identity_for(host, port):
    """Key-store identity of one TV endpoint; must match WebOsClient.identity."""
    return f'{str(host).strip().lower()}:{int(port)}'


class WebOsKeyStore:
    def __init__(self, directory=None):
        self.directory = directory or os.path.join(user_data_dir(), 'webos')
        self._lock = threading.RLock()

    def _path(self, identity):
        return os.path.join(self.directory, hashlib.sha256(identity.encode()).hexdigest() + '.json')

    def delete(self, identity):
        """Forget the pairing key and pinned certificate; True when a record existed."""
        with self._lock:
            try:
                os.unlink(self._path(identity))
                return True
            except FileNotFoundError:
                return False

    def load(self, identity):
        with self._lock:
            try:
                with open(self._path(identity), encoding='utf-8') as stream:
                    value = json.load(stream)
                    return value if isinstance(value, dict) else {}
            except (OSError, ValueError):
                return {}

    def save(self, identity, value):
        with self._lock:
            os.makedirs(self.directory, mode=0o700, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix='key-', dir=self.directory)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(value, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self._path(identity))
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)


PERMISSIONS = [
    'LAUNCH', 'CONTROL_AUDIO', 'CONTROL_INPUT_MEDIA_PLAYBACK', 'CONTROL_INPUT_TV',
    'CONTROL_POWER', 'CONTROL_INPUT_TEXT', 'CONTROL_MOUSE_AND_KEYBOARD',
    'READ_INSTALLED_APPS', 'READ_INPUT_DEVICE_LIST', 'READ_RUNNING_APPS',
]
BUTTONS = {
    'up': 'UP', 'down': 'DOWN', 'left': 'LEFT', 'right': 'RIGHT', 'ok': 'ENTER',
    'enter': 'ENTER', 'select': 'ENTER', 'home': 'HOME', 'back': 'BACK',
    'exit': 'EXIT', 'menu': 'MENU', 'settings': 'MENU', 'info': 'INFO',
    'red': 'RED', 'green': 'GREEN', 'yellow': 'YELLOW', 'blue': 'BLUE',
    **{str(n): str(n) for n in range(10)},
}
# Requests without side effects: safe to resend on a fresh connection after a failure.
READ_ONLY_URIS = frozenset({
    'ssap://system/getSystemInfo',
    'ssap://com.webos.applicationManager/listLaunchPoints',
    'ssap://tv/getExternalInputList',
    'ssap://audio/getVolume',
    'ssap://com.webos.service.networkinput/getPointerInputSocket',
})
# A reused pointer socket older than this is replaced: a write to a socket the TV already
# closed can succeed locally and silently drop the key press, and nothing is read back.
# Conservative guess, not yet measured on a real TV.
POINTER_REUSE_SECONDS = 5.0
ENDPOINTS = {
    'volume_up': 'audio/volumeUp', 'volume_down': 'audio/volumeDown',
    'play': 'media.controls/play',
    'pause': 'media.controls/pause', 'stop': 'media.controls/stop',
    'rewind': 'media.controls/rewind', 'fast_forward': 'media.controls/fastForward',
    'channel_up': 'tv/channelUp', 'channel_down': 'tv/channelDown',
    'power_off': 'system/turnOff', 'power': 'system/turnOff',
}


def _connect(url, **kwargs):
    try:
        import websocket
    except ImportError as exc:
        raise WebOsError('Thiếu websocket-client; cài dependencies của SmartTV Manager.') from exc
    return websocket.create_connection(url, **kwargs)


class WebOsClient:
    def __init__(self, host, port=3001, *, secure=None, key_store=None, connector=None, timeout=20):
        host = str(host or '').strip()
        try:
            port = int(port)
        except (TypeError, ValueError) as exc:
            raise WebOsError('Cổng LG không hợp lệ.') from exc
        if not host or any(c in host for c in '/?#@\\') or any(c.isspace() for c in host) or not 1 <= port <= 65535:
            raise WebOsError('Địa chỉ hoặc cổng LG không hợp lệ.')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host):
                raise WebOsError('Địa chỉ LG không hợp lệ.')
        self.host, self.port = host, port
        self.secure = port != 3000 if secure is None else bool(secure)
        self.timeout = max(0.1, float(timeout))
        self.identity = identity_for(host, port)
        self.key_store = key_store if key_store is not None else WebOsKeyStore()
        self.connector = connector or _connect
        self._injected = connector is not None
        self._socket = None
        self._pointer = None
        self._pointer_used = 0.0
        self._lock = threading.RLock()
        self._serial = 0
        self._fingerprint = None

    @property
    def url(self):
        host = f'[{self.host}]' if ':' in self.host else self.host
        return f'{"wss" if self.secure else "ws"}://{host}:{self.port}'

    def _open(self, url):
        options = {'timeout': self.timeout}
        if url.startswith('wss:'):
            options['sslopt'] = {'cert_reqs': ssl.CERT_NONE, 'check_hostname': False}
        return self.connector(url, **options)

    def _certificate(self, transport):
        try:
            cert = transport.sock.getpeercert(binary_form=True)
        except (AttributeError, OSError):
            if self._injected:
                return None
            raise WebOsError('Không đọc được chứng chỉ LG.')
        if not cert:
            raise WebOsError('LG không cung cấp chứng chỉ TLS.')
        return hashlib.sha256(cert).hexdigest()

    def _alive(self):
        return self._socket is not None and bool(getattr(self._socket, 'connected', True))

    def connect(self):
        with self._lock:
            if self._alive():
                return {'connected': True}
            self.close()  # drops a socket the library already knows is dead
            try:
                saved = self.key_store.load(self.identity)
                self._socket = self._open(self.url)
                self._fingerprint = self._certificate(self._socket) if self.secure else None
                pinned = saved.get('certificate_sha256')
                if pinned and pinned != self._fingerprint:
                    raise WebOsError('Chứng chỉ LG đã thay đổi. Xác minh đúng TV rồi bấm «Quên ghép cặp» trên thẻ thiết bị để ghép lại.')
                payload = {'forcePairing': False, 'pairingType': 'PROMPT', 'manifest': {
                    'manifestVersion': 1, 'appVersion': '1.0', 'permissions': list(PERMISSIONS)}}
                if saved.get('client_key'):
                    payload['client-key'] = saved['client_key']
                self._socket.send(json.dumps({'type': 'register', 'id': 'register_0', 'payload': payload}))
                msg = self._receive('register_0', registration=True)
                key = msg.get('payload', {}).get('client-key')
                if not isinstance(key, str) or not key.strip():
                    raise WebOsError('LG không trả khóa ghép cặp hợp lệ.')
                value = {'client_key': key}
                if self._fingerprint:
                    value['certificate_sha256'] = self._fingerprint
                self.key_store.save(self.identity, value)
                return {'connected': True}
            except Exception as exc:
                self.close()
                if isinstance(exc, WebOsError):
                    raise
                raise WebOsError(f'Không kết nối/ghép cặp LG: {exc}') from exc

    def _receive(self, rid, registration=False):
        deadline = time.monotonic() + (max(self.timeout, 60) if registration else self.timeout)
        for _ in range(128):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WebOsError('Hết thời gian chờ LG phản hồi.')
            self._socket.settimeout(remaining)
            raw = self._socket.recv()
            if not raw:
                raise WebOsError('LG đã đóng kết nối.')
            msg = json.loads(raw)
            if not isinstance(msg, dict):
                raise WebOsError('Phản hồi LG không hợp lệ.')
            if msg.get('id') != rid:
                continue
            if msg.get('type') == 'error':
                raise WebOsCommandError(str(msg.get('error') or 'LG từ chối yêu cầu.'))
            payload = msg.get('payload', {})
            if not isinstance(payload, dict):
                raise WebOsError('Dữ liệu LG không hợp lệ.')
            if payload.get('returnValue') is False:
                raise WebOsCommandError(str(payload.get('errorText') or payload.get('errorCode') or 'LG từ chối yêu cầu.'))
            if msg.get('type') == ('registered' if registration else 'response'):
                return msg
        raise WebOsError('LG không trả phản hồi đúng mã yêu cầu.')

    def request(self, uri, payload=None):
        if not isinstance(uri, str) or not uri.startswith('ssap://'):
            raise WebOsError('SSAP URI không hợp lệ.')
        with self._lock:
            for attempt in (0, 1):
                reused = self._alive()  # same test connect() uses to skip reconnecting
                written = False
                try:
                    self.connect()
                    self._serial += 1
                    rid = f'request_{self._serial}'
                    self._socket.send(json.dumps({'type': 'request', 'id': rid, 'uri': uri, 'payload': payload or {}}, ensure_ascii=False))
                    written = True
                    return self._receive(rid).get('payload', {})
                except WebOsCommandError:
                    raise
                except Exception as exc:
                    self.close()
                    # Only a socket that was already open can be stale; a failed fresh
                    # connect (pairing refused, changed certificate) must not be repeated.
                    if attempt == 0 and reused and (not written or uri in READ_ONLY_URIS):
                        continue
                    if isinstance(exc, WebOsError):
                        raise
                    raise WebOsError(f'LG không phản hồi: {exc}') from exc

    def _close_pointer(self):
        transport, self._pointer = self._pointer, None
        if transport:
            try:
                transport.close()
            except Exception:
                pass

    def close(self):
        with self._lock:
            # The pointer path belongs to the control session, so both go together.
            self._close_pointer()
            transport, self._socket = self._socket, None
            if transport:
                try:
                    transport.close()
                except Exception:
                    pass

    def get_info(self):
        try:
            info = self.request('ssap://system/getSystemInfo')
        except WebOsCommandError:
            # New firmware can deny system info after registration. Identity is
            # optional: do not undo a successful pairing for unavailable metadata.
            info = {}
        return {'model': info.get('modelName') or info.get('model') or 'LG webOS',
                'platform': 'lg_webos', 'webos': info.get('sdkVersion') or '', 'raw': info}

    info = get_info

    def list_apps(self):
        points = self.request('ssap://com.webos.applicationManager/listLaunchPoints').get('launchPoints', [])
        if not isinstance(points, list):
            raise WebOsError('Danh sách ứng dụng LG không hợp lệ.')
        return [{'id': p['id'], 'title': p.get('title') or p['id'],
                 'icon': p.get('largeIcon') or p.get('icon') or ''}
                for p in points if isinstance(p, dict) and p.get('id') and not p.get('hidden')]

    def list_inputs(self):
        devices = self.request('ssap://tv/getExternalInputList').get('devices', [])
        if not isinstance(devices, list):
            raise WebOsError('Danh sách input LG không hợp lệ.')
        return [dict(d, label=d.get('label') or d['id']) for d in devices
                if isinstance(d, dict) and d.get('id')]

    def launch_app(self, app_id):
        if not isinstance(app_id, str) or not app_id.strip():
            raise WebOsError('App ID LG trống.')
        return self.request('ssap://system.launcher/launch', {'id': app_id})

    def switch_input(self, input_id):
        if not isinstance(input_id, str) or not input_id.strip():
            raise WebOsError('Input LG trống.')
        return self.request('ssap://tv/switchInput', {'inputId': input_id})

    def send_text(self, text):
        if not isinstance(text, str) or not text:
            raise WebOsError('Nội dung trống.')
        return self.request('ssap://com.webos.service.ime/insertText', {'text': text, 'replace': 0})

    def power_off(self):
        return self.request('ssap://system/turnOff')

    def remote(self, command):
        command = str(command).strip().lower()
        command = {'volumeup':'volume_up', 'volumedown':'volume_down',
                   'channelup':'channel_up', 'channeldown':'channel_down',
                   'fastforward':'fast_forward'}.get(command, command)
        if command == 'input':
            return self.launch_app('com.webos.app.inputpicker')
        if command == 'mute':
            status = self.request('ssap://audio/getVolume')
            muted = status.get('muted', (status.get('volumeStatus') or {}).get('muted', False))
            return self.request('ssap://audio/setMute', {'mute': not muted})
        if command in ENDPOINTS:
            return self.request('ssap://' + ENDPOINTS[command])
        if command not in BUTTONS:
            raise WebOsError(f'Lệnh remote LG không hỗ trợ: {command}')
        return self._send_button(BUTTONS[command])

    def _peer_hosts(self):
        """Addresses the authenticated control socket is actually connected to.

        The TV answers with an IP URL even when the user added it by hostname, so the
        configured name alone would reject every key press for such a TV.
        """
        hosts = {self.host.lower()}
        try:
            hosts.add(str(self._socket.sock.getpeername()[0]).split('%')[0].lower())
        except (AttributeError, OSError, IndexError, TypeError, ValueError):
            pass
        return hosts

    def _open_pointer(self):
        payload = self.request('ssap://com.webos.service.networkinput/getPointerInputSocket')
        path = payload.get('socketPath', '')
        try:
            parsed = urlsplit(path)
            pointer_port = parsed.port
        except (ValueError, TypeError, AttributeError) as exc:
            raise WebOsError('Địa chỉ pointer socket LG không hợp lệ.') from exc
        # The authenticated SSAP service may return a plain WS input URL even
        # when the control channel uses TLS. Honor that TV-local endpoint;
        # never follow an off-TV URL or send registration credentials here.
        if (parsed.hostname not in self._peer_hosts() or parsed.scheme not in ('wss', 'ws')
                or pointer_port not in (self.port, 3000, 3001) or parsed.username or parsed.password):
            raise WebOsError('Địa chỉ pointer socket LG không hợp lệ.')
        pointer = None
        try:
            pointer = self._open(path)
            if parsed.scheme == 'wss' and self.secure and self._certificate(pointer) != self._fingerprint:
                raise WebOsError('Chứng chỉ pointer socket LG không khớp.')
        except Exception as exc:
            if pointer:
                try:
                    pointer.close()
                except Exception:
                    pass
            if isinstance(exc, WebOsError):
                raise
            raise WebOsError(f'Không mở được kênh phím LG: {exc}') from exc
        self._pointer = pointer
        return pointer

    def _send_button(self, name):
        message = f'type:button\nname:{name}\n\n'
        with self._lock:
            if self._pointer is not None and (
                    time.monotonic() - self._pointer_used > POINTER_REUSE_SECONDS
                    or not getattr(self._pointer, 'connected', True)):
                self._close_pointer()
            for attempt in (0, 1):
                reused = self._pointer is not None
                pointer = self._pointer or self._open_pointer()
                try:
                    pointer.send(message)
                except Exception as exc:
                    self._close_pointer()
                    # A failed write means the key never reached the TV, so one resend on a
                    # fresh socket cannot press it twice. Only a reused socket can be stale.
                    if attempt == 0 and reused:
                        continue
                    raise WebOsError(f'Không gửi được phím LG: {exc}') from exc
                self._pointer_used = time.monotonic()
                return {'returnValue': True}

    remote_key = remote

"""Protocol behavior tests; fake transport, no TV or websocket dependency required."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core.webos_client import WebOsClient, WebOsError, WebOsKeyStore


class Socket:
    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []
        self.closed = False
    def send(self, data):
        self.sent.append(json.loads(data) if data.startswith('{') else data)
    def recv(self):
        frame = self.frames.pop(0)
        if isinstance(frame, Exception):
            raise frame
        return json.dumps(frame)
    def close(self):
        self.closed = True
    def settimeout(self, timeout):
        pass


def registered(key='key1'):
    return {'type': 'registered', 'id': 'register_0', 'payload': {'client-key': key}}


def response(payload=None, rid='request_1'):
    return {'type': 'response', 'id': rid, 'payload': payload or {}}


class ClientTests(unittest.TestCase):
    def make(self, frames):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        sock = Socket(frames)
        connector = unittest.mock.Mock(return_value=sock)
        keys = WebOsKeyStore(temp.name)
        client = WebOsClient('192.168.1.10', connector=connector, key_store=keys)
        self.addCleanup(client.close)
        return client, sock, keys, connector

    def test_registration_uses_unsigned_minimal_manifest_and_reuses_key(self):
        client, sock, keys, connector = self.make([registered()])
        client.connect()
        manifest = sock.sent[0]['payload']['manifest']
        self.assertNotIn('signed', manifest)
        self.assertNotIn('signatures', manifest)
        self.assertNotIn('TEST_PROTECTED', manifest['permissions'])
        self.assertEqual(keys.load(client.identity)['client_key'], 'key1')
        self.assertEqual(connector.call_args.args[0], 'wss://192.168.1.10:3001')
        client.close()
        sock2 = Socket([registered()])
        connector.return_value = sock2
        client.connect()
        self.assertEqual(sock2.sent[0]['payload']['client-key'], 'key1')

    def test_pairing_error_closes_socket_and_does_not_persist(self):
        client, sock, keys, _ = self.make([{'type':'error','id':'register_0','error':'403 rejected'}])
        with self.assertRaisesRegex(WebOsError, '403 rejected'):
            client.connect()
        self.assertTrue(sock.closed)
        self.assertEqual(keys.load(client.identity), {})

    def test_registration_requires_nonempty_key(self):
        client, sock, keys, _ = self.make([registered('')])
        with self.assertRaises(WebOsError):
            client.connect()
        self.assertEqual(keys.load(client.identity), {})
        self.assertTrue(sock.closed)

    def test_timeout_and_malformed_json_are_typed_and_disconnect(self):
        for failure in (TimeoutError('late'), ValueError('bad')):
            with self.subTest(failure=failure):
                client, sock, _, _ = self.make([failure])
                with self.assertRaises(WebOsError):
                    client.connect()
                self.assertTrue(sock.closed)

    def test_request_ignores_unrelated_frames_and_routes_matching_id(self):
        client, sock, _, _ = self.make([registered(), response({'wrong':True}, 'subscription_4'), response({'ok':True})])
        client.connect()
        self.assertEqual(client.request('ssap://test'), {'ok':True})
        self.assertEqual(sock.sent[-1]['id'], 'request_1')

    def test_error_frames_and_false_return_value_fail(self):
        for frame in ({'type':'error','id':'request_1','error':'denied'}, response({'returnValue':False,'errorText':'denied'})):
            client, _, _, _ = self.make([registered(), frame])
            client.connect()
            with self.assertRaisesRegex(WebOsError, 'denied'):
                client.request('ssap://test')

    def test_request_connection_failure_does_not_replay_mutation(self):
        client, sock, _, connector = self.make([registered(), TimeoutError('lost')])
        client.connect()
        with self.assertRaises(WebOsError):
            client.launch_app('netflix')
        self.assertTrue(sock.closed)
        self.assertEqual(connector.call_count, 1)

    def test_apps_and_inputs_keep_missing_icons(self):
        client, _, _, _ = self.make([registered(), response({'launchPoints':[{'id':'netflix','title':'Netflix'},{'id':'hide','hidden':True}]}), response({'devices':[{'id':'HDMI_1','label':'Console','appId':'hdmi1'}]}, 'request_2')])
        client.connect()
        self.assertEqual(client.list_apps(), [{'id':'netflix','title':'Netflix','icon':''}])
        self.assertEqual(client.list_inputs()[0]['id'], 'HDMI_1')

    def test_launch_and_input_payloads(self):
        client, sock, _, _ = self.make([registered(), response({'returnValue':True}), response({'returnValue':True}, 'request_2')])
        client.connect()
        client.launch_app('netflix')
        client.switch_input('HDMI_1')
        self.assertEqual(sock.sent[1]['payload'], {'id':'netflix'})
        self.assertEqual(sock.sent[2]['payload'], {'inputId':'HDMI_1'})

    def test_text_is_json_not_shell_and_unicode_preserved(self):
        client, sock, _, _ = self.make([registered(), response({'returnValue':True})])
        client.connect()
        client.send_text('Xin chào " $;')
        self.assertEqual(sock.sent[-1]['payload']['text'], 'Xin chào " $;')

    def test_volume_uses_audio_endpoint(self):
        client, sock, _, _ = self.make([registered(), response({'returnValue':True})])
        client.connect()
        client.remote('volume_up')
        self.assertEqual(sock.sent[-1]['uri'], 'ssap://audio/volumeUp')

    def test_pointer_button_uses_returned_socket_and_closes(self):
        client, sock, _, connector = self.make([registered(), response({'socketPath':'wss://192.168.1.10:3001/pointer'})])
        pointer = Socket([])
        client.connect()
        connector.return_value = pointer
        client.remote('home')
        self.assertEqual(pointer.sent, ['type:button\nname:HOME\n\n'])
        self.assertTrue(pointer.closed)

    def test_pointer_cannot_redirect_credentials_to_another_host(self):
        client, _, _, connector = self.make([registered(), response({'socketPath':'wss://evil.example/pointer'})])
        client.connect()
        with self.assertRaises(WebOsError):
            client.remote('home')
        self.assertEqual(connector.call_count, 1)

    def test_unknown_remote_command_fails_before_network(self):
        client, _, _, connector = self.make([])
        with self.assertRaises(WebOsError):
            client.remote('shell;reboot')
        connector.assert_not_called()

    def test_key_store_isolates_tvs_and_writes_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            keys = WebOsKeyStore(directory)
            keys.save('tv1:3001', {'client_key':'one'})
            keys.save('tv2:3001', {'client_key':'two'})
            self.assertEqual(keys.load('tv1:3001')['client_key'], 'one')
            self.assertEqual(keys.load('tv2:3001')['client_key'], 'two')
            if os.name != 'nt':
                for name in os.listdir(directory):
                    self.assertEqual(os.stat(os.path.join(directory, name)).st_mode & 0o777, 0o600)

    def test_changed_certificate_rejected_before_stored_key_is_sent(self):
        client, sock, keys, _ = self.make([registered()])
        keys.save(client.identity, {'client_key':'secret', 'certificate_sha256':'old'})
        with patch.object(client, '_certificate', return_value='changed'):
            with self.assertRaisesRegex(WebOsError, 'Chứng chỉ'):
                client.connect()
        self.assertEqual(sock.sent, [])
        self.assertTrue(sock.closed)
        self.assertEqual(keys.load(client.identity)['client_key'], 'secret')

    def test_approved_registration_pins_certificate(self):
        client, _, keys, _ = self.make([registered()])
        with patch.object(client, '_certificate', return_value='fingerprint'):
            client.connect()
        self.assertEqual(keys.load(client.identity)['certificate_sha256'], 'fingerprint')

    def test_malformed_and_closed_frames_are_errors(self):
        for raw in ('bad json', '[]', ''):
            client, sock, keys, _ = self.make([])
            sock.recv = lambda: raw
            with self.assertRaises(WebOsError):
                client.connect()
            self.assertTrue(sock.closed)
            self.assertEqual(keys.load(client.identity), {})

    def test_mute_uses_current_state_and_set_mute(self):
        client, sock, _, _ = self.make([registered(), response({'muted':True}), response({'returnValue':True}, 'request_2')])
        client.connect()
        client.remote('MUTE')
        self.assertEqual(sock.sent[-1]['uri'], 'ssap://audio/setMute')
        self.assertEqual(sock.sent[-1]['payload'], {'mute':False})

    def test_ui_aliases_and_input_picker(self):
        for command, uri in [('volumeup','audio/volumeUp'), ('volumedown','audio/volumeDown'), ('fastforward','media.controls/fastForward')]:
            client, sock, _, _ = self.make([registered(), response({'returnValue':True})])
            client.connect()
            client.remote(command)
            self.assertEqual(sock.sent[-1]['uri'], 'ssap://' + uri)
        client, sock, _, _ = self.make([registered(), response({'returnValue':True})])
        client.connect()
        client.remote('input')
        self.assertEqual(sock.sent[-1]['payload'], {'id':'com.webos.app.inputpicker'})

    def test_denied_optional_system_info_does_not_undo_pairing(self):
        client, sock, keys, _ = self.make([registered(), {'type':'error','id':'request_1','error':'403 access denied'}])
        client.connect()
        self.assertEqual(client.get_info()['model'], 'LG webOS')
        self.assertFalse(sock.closed)
        self.assertEqual(keys.load(client.identity)['client_key'], 'key1')

    def test_secure_main_accepts_authenticated_local_plain_pointer_path(self):
        client, _, _, connector = self.make([registered(), response({'socketPath':'ws://192.168.1.10:3000/pointer'})])
        pointer = Socket([])
        client.connect()
        connector.return_value = pointer
        client.remote('home')
        self.assertEqual(pointer.sent, ['type:button\nname:HOME\n\n'])

    def test_malformed_pointer_url_is_typed_error(self):
        client, _, _, connector = self.make([registered(), response({'socketPath':'wss://192.168.1.10:bad/pointer'})])
        client.connect()
        with self.assertRaises(WebOsError):
            client.remote('home')
        self.assertEqual(connector.call_count, 1)

    def test_malformed_app_list_is_typed_error(self):
        client, _, _, _ = self.make([registered(), response({'launchPoints':None})])
        client.connect()
        with self.assertRaises(WebOsError):
            client.list_apps()

    def test_invalid_host_or_port_rejected(self):
        for host, port in [('https://example.com',3001), ('',3001), ('host',0)]:
            with self.assertRaises(WebOsError):
                WebOsClient(host, port)


if __name__ == '__main__':
    unittest.main()

"""Build a webOS Home snapshot from SmartTV Manager's own theme catalog.

No credentials enter the bundle. Applying another theme/data snapshot explicitly
repackages/reinstalls the app; this is not a live-update service or default Home.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import ntpath
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import paths
from core import theme_widgets

APP_ID = 'com.smtvmanager.home'
# The .ipk is copied onto the TV, whose app storage is small. The theme catalog caps images at
# 100 files of 10 MB each, far more than a Home package should carry.
MAX_WALLPAPERS = 12
MAX_WALLPAPER_BYTES = 24 * 1024 * 1024
# Where npm usually puts global CLIs. An app started from Finder/launcher does not inherit the
# shell PATH, so `ares-*` would look missing even though it is installed.
EXTRA_CLI_DIRS = ('/opt/homebrew/bin', '/usr/local/bin', '~/.npm-global/bin', '~/.volta/bin', '~/.local/bin')


class WebOsHomeError(Exception):
    pass


# Only semantic equivalents; SmartTube deliberately has no LG equivalent here.
APP_MAPPING = {
    'com.google.android.youtube.tv': 'youtube.leanback.v4',
    'com.netflix.ninja': 'netflix',
    'com.spotify.tv.android': 'spotify-beehive',
    'com.android.tv.settings': 'com.palm.app.settings',
}


def map_app_id(app_id, apps):
    available = {a.get('id') for a in apps}
    target = APP_MAPPING.get(app_id, app_id)
    return target if target in available else None


def build_bundle(theme, destination, apps=None, inputs=None, widget_data=None, widget_switches=None):
    """Create a new directory; refuse overwrite and assets outside the theme root."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Bundle destination must not already exist')
    root = Path(theme['path']).resolve()
    config = copy.deepcopy(theme.get('config') or {})
    config.update(theme_widgets.overrides(config, widget_switches or {}))
    if config.get('dashboard') and config.get('design_profile') not in {'aurora','hanoi','hanoi2','hanoi3'}:
        raise ValueError('Unsupported webOS dashboard profile')
    sources = list(theme.get('wallpapers') or [])
    if not sources and theme.get('wallpaper'):
        sources = [theme['wallpaper']]
    verified = []
    for source in sources:
        asset = Path(source).resolve()
        if not asset.is_relative_to(root) or not asset.is_file() or asset.suffix.lower() not in {'.jpg','.jpeg','.png','.webp'}:
            raise ValueError('Wallpaper must be an image inside the selected theme')
        verified.append(asset)
    total = sum(asset.stat().st_size for asset in verified)
    if len(verified) > MAX_WALLPAPERS or total > MAX_WALLPAPER_BYTES:
        raise ValueError(
            f'Too many or too large wallpapers for a webOS Home package ({len(verified)} files, '
            f'{total // (1024 * 1024)} MB; limit {MAX_WALLPAPERS} files, {MAX_WALLPAPER_BYTES // (1024 * 1024)} MB)')
    clean_apps = []
    for app in apps or []:
        if not isinstance(app, dict) or not app.get('id') or app.get('hidden') or app['id'] == APP_ID:
            continue
        # Icons are optional: never drop a launchable app on an icon download error.
        clean_apps.append({'id':str(app['id']), 'title':str(app.get('title') or app.get('name') or app['id'])})
    mapped = [map_app_id(app_id, clean_apps) for app_id in config.get('dock_apps', [])]
    config['dock_apps'] = list(dict.fromkeys(app_id for app_id in mapped if app_id))
    config['hidden_apps'] = [v for v in (map_app_id(i, clean_apps) for i in config.get('hidden_apps', [])) if v]
    clean_inputs = [{'id':str(i.get('id') or ''),'appId':str(i.get('appId') or ''),
                     'label':str(i.get('label') or i.get('id') or '')} for i in inputs or [] if isinstance(i,dict)]
    runtime = {'schema_version':1, 'theme_id':theme['id'], 'config':config,
               'widgets':copy.deepcopy(widget_data or {}), 'apps':clean_apps, 'inputs':clean_inputs,
               'wallpapers':[f'wallpapers/{n}{source.suffix.lower()}' for n,source in enumerate(verified)],
               'data_updated_at':datetime.now(timezone.utc).isoformat()}
    template = Path(paths.app_root())/'webos-home'
    try:
        shutil.copytree(template, destination)
        assets = destination/'wallpapers'; assets.mkdir(exist_ok=True)
        for source, name in zip(verified,runtime['wallpapers']):
            shutil.copyfile(source,destination/name)
        fonts = destination/'fonts'; fonts.mkdir(exist_ok=True)
        for name in ('Inter-Regular.otf','Inter-Bold.otf'):
            source = Path(paths.app_root())/'assets'/'fonts'/name
            if source.is_file(): shutil.copyfile(source,fonts/name)
        source = Path(paths.app_root())/'assets'/'fonts'/'Inter-LICENSE-OFL.txt'
        if source.is_file(): shutil.copyfile(source,fonts/'LICENSE.txt')
        from PIL import Image
        with Image.open(Path(paths.app_root())/'ui'/'assets'/'app-icon.png') as icon:
            icon.resize((80,80)).save(destination/'icon.png')
        serialized = json.dumps(runtime,ensure_ascii=False)
        (destination/'runtime.json').write_text(serialized,encoding='utf-8')
        (destination/'runtime.js').write_text('window.SMARTTV_HOME = '+serialized+';\n',encoding='utf-8')
        return str(destination)
    except Exception:
        shutil.rmtree(destination,ignore_errors=True)
        raise


def cli_argv(argv, windows=None):
    """Invoke npm's Windows JS entrypoint through Node, never a batch shell.

    cmd.exe shims can interpret metacharacters even when subprocess shell=False.
    Resolving the official CLI entrypoint keeps every device/path an argv value.
    """
    if windows is None:
        windows = os.name == 'nt'
    if not windows:
        return argv
    executable = shutil.which(argv[0])
    if not executable:
        raise WebOsHomeError('Install webOS CLI and make it available on PATH')
    if executable.lower().endswith(('.cmd', '.bat', '.ps1')):
        script = ntpath.join(ntpath.dirname(executable), 'node_modules', '@webos-tools',
                             'cli', 'bin', argv[0] + '.js')
        node = shutil.which('node')
        if not node or not Path(script).is_file():
            raise WebOsHomeError('Install Node.js and the official npm webOS CLI on PATH')
        return [node, script, *argv[1:]]
    return [executable, *argv[1:]]


def cli_env(base=None, windows=None):
    """Environment for the webOS CLI; on POSIX, appends npm's usual global bin dirs to PATH."""
    env = dict(os.environ if base is None else base)
    if os.name == 'nt' if windows is None else windows:
        return env
    entries = [e for e in env.get('PATH', '').split(os.pathsep) if e]
    for directory in EXTRA_CLI_DIRS:
        directory = os.path.expanduser(directory)
        if os.path.isdir(directory) and directory not in entries:
            entries.append(directory)
    env['PATH'] = os.pathsep.join(entries)
    return env


def deploy(bundle_path, device_name, runner=None, expected_host=None):
    """Use an already configured Developer Mode CLI device; bounded argv only."""
    runner = runner or subprocess.run
    if not str(device_name).strip() or str(device_name).startswith('-'):
        raise WebOsHomeError('Configure a valid webOS CLI device name first')
    bundle_path = Path(bundle_path).resolve()
    if not (bundle_path/'appinfo.json').is_file():
        raise WebOsHomeError('Missing webOS Home bundle')
    def run(argv, timeout):
        try:
            result = runner(cli_argv(argv),capture_output=True,text=True,timeout=timeout,check=False,env=cli_env())
        except FileNotFoundError as exc:
            raise WebOsHomeError('Install webOS CLI (@webos-tools/cli) and configure a Developer Mode device') from exc
        except subprocess.TimeoutExpired as exc:
            raise WebOsHomeError(f'webOS CLI timeout: {argv[0]}') from exc
        if result.returncode:
            raise WebOsHomeError(f'{argv[0]} failed: {(result.stderr or result.stdout or "unknown error")[-1500:]}')
        return result
    if expected_host is not None:
        # @webos-tools/cli 3.2.6 setup-device.js emits this JSON shape for --listfull.
        result = run(['ares-setup-device','--listfull'],30)
        try:
            profiles = json.loads(result.stdout)
            matches = [p for p in profiles if p.get('name') == str(device_name)]
            target = matches[0]['deviceinfo']['ip'] if len(matches) == 1 else None
        except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
            raise WebOsHomeError('Cannot verify webOS CLI target profile') from exc
        if target != str(expected_host):
            raise WebOsHomeError('webOS CLI target does not match the selected TV; update its device profile first')
    with tempfile.TemporaryDirectory(prefix='smarttv-webos-ipk-') as tmp:
        run(['ares-package',str(bundle_path),'-o',tmp],120)
        packages = list(Path(tmp).glob(f'{APP_ID}_*.ipk'))
        if len(packages) != 1:
            raise WebOsHomeError('webOS CLI did not produce exactly one Home package')
        run(['ares-install','--device',str(device_name),str(packages[0])],180)
        run(['ares-launch','--device',str(device_name),APP_ID],60)
    return {'ok':True,'app_id':APP_ID,'snapshot':True}

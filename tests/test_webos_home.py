"""Behavior contracts for the webOS Home snapshot and deployment (TDD)."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import os

from core import webos_home
from core.cleanyourtv_themes import CleanyourtvThemes


class HomeBundleTests(unittest.TestCase):
    def test_catalog_profiles_switches_and_snapshot_are_preserved(self):
        themes = CleanyourtvThemes().list_themes()
        self.assertEqual({t['config']['design_profile'] for t in themes}, {'aurora', 'hanoi', 'hanoi2', 'hanoi3'})
        for theme in themes:
            original = copy.deepcopy(theme)
            with tempfile.TemporaryDirectory() as tmp:
                result = Path(webos_home.build_bundle(theme, Path(tmp)/'app', apps=[{'id':'netflix','title':'Netflix'}], widget_data={'gold':None,'generated':'12:00'}, widget_switches={'show_weather':False}))
                payload = json.loads((result/'runtime.json').read_text(encoding='utf-8'))
                self.assertEqual(payload['theme_id'], theme['id'])
                self.assertEqual(payload['config']['design_profile'], theme['config']['design_profile'])
                self.assertFalse(payload['config']['show_weather'])
                self.assertEqual(payload['widgets']['generated'], '12:00')
                self.assertEqual(payload['apps'][0]['id'], 'netflix')
                self.assertTrue(payload['wallpapers'])
                self.assertTrue((result/payload['wallpapers'][0]).is_file())
                self.assertEqual(json.loads((result/'appinfo.json').read_text(encoding='utf-8'))['id'], 'com.smtvmanager.home')
                self.assertNotIn('client-key', (result/'runtime.js').read_text(encoding='utf-8'))
            self.assertEqual(theme, original)

    def test_reject_asset_outside_theme_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            theme_root = root/'theme'; theme_root.mkdir()
            outsider = root/'secret.jpg'; outsider.write_bytes(b'secret')
            theme = {'id':'bad','path':str(theme_root),'config':{},'wallpaper':str(outsider)}
            with self.assertRaises(ValueError):
                webos_home.build_bundle(theme,root/'out')
            theme['wallpaper'] = None
            (root/'existing').mkdir()
            with self.assertRaises(ValueError):
                webos_home.build_bundle(theme,root/'existing')

    def test_oversized_wallpaper_sets_are_rejected_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            theme_root = root / 'theme'; theme_root.mkdir()
            images = []
            for n in range(3):
                image = theme_root / f'{n}.jpg'; image.write_bytes(b'x' * 10); images.append(str(image))
            theme = {'id': 'big', 'path': str(theme_root), 'config': {}, 'wallpapers': images}
            for name, value in (('MAX_WALLPAPER_BYTES', 25), ('MAX_WALLPAPERS', 2)):
                with patch.object(webos_home, name, value):
                    with self.assertRaisesRegex(ValueError, 'Too many or too large'):
                        webos_home.build_bundle(theme, root / 'out')
                self.assertFalse((root / 'out').exists())

    def test_android_mapping_never_rebrands_smarttube_as_youtube(self):
        apps=[{'id':'youtube.leanback.v4','title':'YouTube'}, {'id':'netflix','title':'Netflix'}]
        self.assertEqual(webos_home.map_app_id('com.google.android.youtube.tv', apps), 'youtube.leanback.v4')
        self.assertIsNone(webos_home.map_app_id('com.teamsmart.videomanager.tv', apps))
        self.assertIsNone(webos_home.map_app_id('com.netflix.ninja', []))


class HomeDeployTests(unittest.TestCase):
    def setUp(self):
        # These tests inject a fake runner. Without this, cli_argv resolves the real CLI on
        # Windows (npm .cmd shim -> node) and fails when it is not installed.
        patcher = patch.object(webos_home, 'cli_argv', side_effect=lambda argv, windows=None: argv)
        patcher.start()
        self.addCleanup(patcher.stop)

    def bundle(self, root):
        result=root/'bundle'; result.mkdir(); (result/'appinfo.json').write_text('{}'); return result

    def test_safe_argv_and_install_then_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=self.bundle(root)
            def run(argv, **kw):
                self.assertFalse(kw.get('shell',False)); self.assertGreater(kw['timeout'],0)
                if argv[0]=='ares-package': (Path(argv[-1])/'com.smtvmanager.home_1.0.0_all.ipk').write_bytes(b'ipk')
                return subprocess.CompletedProcess(argv,0,'ok','')
            runner=Mock(side_effect=run)
            result=webos_home.deploy(bundle,'living room',runner=runner)
            self.assertTrue(result['ok'])
            self.assertEqual([c.args[0][0] for c in runner.call_args_list],['ares-package','ares-install','ares-launch'])
            self.assertIn('living room',runner.call_args_list[1].args[0])

    def test_cli_failure_never_reports_success_or_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner=Mock(return_value=subprocess.CompletedProcess([],1,'','install denied'))
            with self.assertRaisesRegex(webos_home.WebOsHomeError,'install denied'):
                webos_home.deploy(self.bundle(Path(tmp)),'tv',runner=runner)
            self.assertEqual(runner.call_count,1)

    def test_wrong_cli_target_stops_before_package_or_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner=Mock(return_value=subprocess.CompletedProcess([],0,json.dumps([{'name':'tv','deviceinfo':{'ip':'192.168.1.8'}}]),''))
            with self.assertRaisesRegex(webos_home.WebOsHomeError,'target'):
                webos_home.deploy(self.bundle(Path(tmp)), 'tv', runner=runner, expected_host='192.168.1.9')
            self.assertEqual(runner.call_args.args[0], ['ares-setup-device','--listfull'])
            self.assertEqual(runner.call_count,1)

    def test_matching_cli_target_can_deploy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def run(argv, **kwargs):
                if argv[0]=='ares-setup-device':
                    return subprocess.CompletedProcess(argv,0,json.dumps([{'name':'tv','deviceinfo':{'ip':'192.168.1.9'}}]),'')
                if argv[0]=='ares-package': (Path(argv[-1])/'com.smtvmanager.home_1.0.0_all.ipk').write_bytes(b'ipk')
                return subprocess.CompletedProcess(argv,0,'ok','')
            self.assertTrue(webos_home.deploy(self.bundle(root),'tv',runner=run,expected_host='192.168.1.9')['ok'])

    def test_cli_timeout_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(webos_home.WebOsHomeError,'timeout'):
                webos_home.deploy(self.bundle(Path(tmp)),'tv',runner=Mock(side_effect=subprocess.TimeoutExpired('ares',1)))


class WindowsCliTests(unittest.TestCase):
    def test_windows_npm_shim_uses_node_without_shell_interpolation(self):
        from unittest.mock import patch
        with patch.object(webos_home.shutil, 'which', side_effect=[r'C:\npm\ares-install.cmd', r'C:\node\node.exe']), \
                patch.object(webos_home.Path, 'is_file', return_value=True):
            argv = webos_home.cli_argv(['ares-install', '--device', 'living room & TV'], windows=True)
        self.assertEqual(argv[0], r'C:\node\node.exe')
        self.assertTrue(argv[1].endswith(r'node_modules\@webos-tools\cli\bin\ares-install.js'))
        self.assertEqual(argv[2:], ['--device', 'living room & TV'])

    def test_windows_missing_cli_is_actionable(self):
        from unittest.mock import patch
        with patch.object(webos_home.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(webos_home.WebOsHomeError, 'CLI'):
                webos_home.cli_argv(['ares-package', 'bundle'], windows=True)


class CliEnvTests(unittest.TestCase):
    def test_posix_env_gains_existing_global_bin_dirs_without_reordering_path(self):
        with tempfile.TemporaryDirectory() as extra, \
                patch.object(webos_home, 'EXTRA_CLI_DIRS', (extra, '/does/not/exist')):
            env = webos_home.cli_env({'PATH': '/usr/bin'}, windows=False)
            self.assertEqual(env['PATH'], os.pathsep.join(['/usr/bin', extra]))
            again = webos_home.cli_env(env, windows=False)
            self.assertEqual(again['PATH'], env['PATH'])  # never duplicated

    def test_windows_env_is_left_alone(self):
        self.assertEqual(webos_home.cli_env({'PATH': r'C:\tools'}, windows=True)['PATH'], r'C:\tools')

    def test_deploy_runs_the_cli_with_the_extended_environment(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(webos_home, 'cli_env', return_value={'PATH': 'marker'}), \
                patch.object(webos_home, 'cli_argv', side_effect=lambda argv, windows=None: argv):
            bundle = Path(tmp) / 'bundle'; bundle.mkdir(); (bundle / 'appinfo.json').write_text('{}')
            runner = Mock(return_value=subprocess.CompletedProcess([], 1, '', 'stop here'))
            with self.assertRaises(webos_home.WebOsHomeError):
                webos_home.deploy(bundle, 'tv', runner=runner)
            self.assertEqual(runner.call_args.kwargs['env'], {'PATH': 'marker'})

"""Behavior contracts for the webOS Home snapshot and deployment (TDD)."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

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
                payload = json.loads((result/'runtime.json').read_text())
                self.assertEqual(payload['theme_id'], theme['id'])
                self.assertEqual(payload['config']['design_profile'], theme['config']['design_profile'])
                self.assertFalse(payload['config']['show_weather'])
                self.assertEqual(payload['widgets']['generated'], '12:00')
                self.assertEqual(payload['apps'][0]['id'], 'netflix')
                self.assertTrue(payload['wallpapers'])
                self.assertTrue((result/payload['wallpapers'][0]).is_file())
                self.assertEqual(json.loads((result/'appinfo.json').read_text())['id'], 'com.smtvmanager.home')
                self.assertNotIn('client-key', (result/'runtime.js').read_text())
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

    def test_android_mapping_never_rebrands_smarttube_as_youtube(self):
        apps=[{'id':'youtube.leanback.v4','title':'YouTube'}, {'id':'netflix','title':'Netflix'}]
        self.assertEqual(webos_home.map_app_id('com.google.android.youtube.tv', apps), 'youtube.leanback.v4')
        self.assertIsNone(webos_home.map_app_id('com.teamsmart.videomanager.tv', apps))
        self.assertIsNone(webos_home.map_app_id('com.netflix.ninja', []))


class HomeDeployTests(unittest.TestCase):
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

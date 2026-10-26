"""ThemeManager drives the smtv-home launcher; upstream CleanYourTV is no longer supported."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.theme_manager import CLASS_PKG, LAUNCHER_PKGS, PKG, ThemeManager  # noqa: E402

(SMTV,) = LAUNCHER_PKGS
GATHIN = "com.gathin.tvhome"  # upstream, unsupported


def manager(packages, home_pkg=None):
    """A ThemeManager whose TV has `packages` installed and `home_pkg` as the default Home."""
    tm = ThemeManager(None)
    calls = []

    def fake_shell(cmd, timeout_s=None):
        calls.append(cmd)
        pm = "".join(f"package:{p}\n" for p in packages)
        home = f"priority=0 system=false\n{home_pkg}/{CLASS_PKG}.MainActivity\n" if home_pkg else ""
        return f"{pm}@@STV:HOMER@@\n{home}@@STV:ROLE@@\n"

    tm._shell = fake_shell
    tm.calls = calls
    return tm


class ResolvePackageTests(unittest.TestCase):
    def test_fork_is_used_even_when_upstream_is_also_installed(self):
        self.assertEqual(manager([GATHIN, SMTV]).pkg, SMTV)

    def test_upstream_alone_is_ignored(self):
        self.assertEqual(manager([GATHIN]).pkg, PKG)

    def test_nothing_installed_falls_back_to_the_fork_name(self):
        self.assertEqual(manager([]).pkg, SMTV)

    def test_result_is_cached_until_refreshed(self):
        tm = manager([SMTV])
        tm.pkg, tm.pkg
        self.assertEqual(len(tm.calls), 1)
        tm.resolve_pkg(refresh=True)
        self.assertEqual(len(tm.calls), 2)

    def test_paths_and_provider_follow_the_package(self):
        tm = manager([SMTV])
        self.assertEqual(tm.theme_uri, f"content://{SMTV}.theme")
        self.assertEqual(tm.home_dir, f"/sdcard/Android/data/{SMTV}/files")


class ComponentNameTests(unittest.TestCase):
    def test_fork_keeps_the_upstream_class_package(self):
        # The fork changes only the applicationId, so ".MainActivity" would resolve to the wrong class.
        self.assertEqual(manager([SMTV]).component_prefix, f"{SMTV}/{CLASS_PKG}.")


if __name__ == "__main__":
    unittest.main()

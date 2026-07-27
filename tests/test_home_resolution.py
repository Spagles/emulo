"""Home resolution must follow the mined data, not a bare directory.

Regression for a bug that silently orphaned every upgraded user's profile store
and segment cache: `resolve_emulo_home` chose ~/.emulo whenever that directory
merely EXISTED. Emulo Pro and the release tooling both create ~/.emulo for
unrelated reasons, so on a real upgraded machine the miner stopped seeing 59
profile files and 272 cached reports still living in ~/.ditto. Every re-mine then
paid full price -- 112 worker calls where 9 were genuinely needed.
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("emulo_home", ROOT / "emulo.py")
emulo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(emulo)


class HomeResolutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._home = emulo.HOME
        emulo.HOME = self.tmp
        self.new = os.path.join(self.tmp, ".emulo")
        self.legacy = os.path.join(self.tmp, ".ditto")
        for key in ("EMULO_HOME", "DITTO_HOME"):
            self._saved = os.environ.pop(key, None)

    def tearDown(self):
        emulo.HOME = self._home

    def resolved(self):
        return os.path.basename(emulo.resolve_emulo_home())

    def test_fresh_machine_picks_new_home(self):
        self.assertEqual(self.resolved(), ".emulo")

    def test_upgraded_user_keeps_legacy_home(self):
        os.makedirs(os.path.join(self.legacy, "profiles"))
        self.assertEqual(self.resolved(), ".ditto")

    def test_unrelated_new_home_does_not_orphan_legacy_data(self):
        """The regression: Pro/release tooling creates ~/.emulo with no mined data."""
        os.makedirs(os.path.join(self.legacy, "profiles"))
        for unrelated in ("release-keys", "release-builds", "pro", "autopilot"):
            os.makedirs(os.path.join(self.new, unrelated))
        self.assertEqual(
            self.resolved(),
            ".ditto",
            "an ~/.emulo holding only release/Pro dirs must not claim the home and "
            "strand the user's profile store and segment cache in ~/.ditto",
        )

    def test_cache_only_legacy_home_is_still_honoured(self):
        """A user mid-migration may have a cache but no profiles yet."""
        os.makedirs(os.path.join(self.legacy, "cache", "reports"))
        os.makedirs(os.path.join(self.new, "pro"))
        self.assertEqual(self.resolved(), ".ditto")

    def test_genuinely_migrated_home_wins(self):
        os.makedirs(os.path.join(self.legacy, "profiles"))
        os.makedirs(os.path.join(self.new, "profiles"))
        self.assertEqual(self.resolved(), ".emulo")

    def test_explicit_env_var_overrides_everything(self):
        os.makedirs(os.path.join(self.legacy, "profiles"))
        custom = os.path.join(self.tmp, "custom")
        os.environ["EMULO_HOME"] = custom
        try:
            self.assertEqual(self.resolved(), "custom")
        finally:
            del os.environ["EMULO_HOME"]

    def test_legacy_env_var_still_honoured(self):
        custom = os.path.join(self.tmp, "legacy-env")
        os.environ["DITTO_HOME"] = custom
        try:
            self.assertEqual(self.resolved(), "legacy-env")
        finally:
            del os.environ["DITTO_HOME"]

    def test_home_holds_mined_data_predicate(self):
        blank = os.path.join(self.tmp, "blank")
        os.makedirs(os.path.join(blank, "release-keys"))
        self.assertFalse(emulo.home_holds_mined_data(blank))
        os.makedirs(os.path.join(blank, "cache", "segments"))
        self.assertTrue(emulo.home_holds_mined_data(blank))


if __name__ == "__main__":
    unittest.main()

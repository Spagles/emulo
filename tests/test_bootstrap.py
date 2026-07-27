import hashlib
import importlib.util
import subprocess
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = ROOT / ".agents" / "skills" / "emulo" / "scripts" / "bootstrap.py"
SPEC = importlib.util.spec_from_file_location("emulo_bootstrap", BOOTSTRAP_PATH)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def metadata(version="0.0.0-dev", ref=None, py_hash=None, prompt_hash=None):
    return {
        "schema_version": "1",
        "version": version,
        "ref": ref,
        "files": {
            "emulo.py": {"sha256": py_hash},
            "MINING_PROMPT.md": {"sha256": prompt_hash},
        },
    }


class BootstrapTest(unittest.TestCase):
    def make_source(self, root):
        source = root / "source"
        source.mkdir()
        (source / "emulo.py").write_bytes(b"print('emulo')\n")
        (source / "MINING_PROMPT.md").write_bytes(b"# prompt\n")
        return source

    def test_dev_metadata_refuses_network_without_source_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "development runtime requires --source-root"):
                bootstrap.install_runtime(metadata(), str(Path(tmp) / "private"))

    def test_repository_runtime_metadata_is_valid(self):
        value = bootstrap.load_metadata(ROOT / ".agents" / "skills" / "emulo" / "runtime.json")
        self.assertEqual(value, bootstrap.validate_metadata(value))

    def test_release_runtime_hashes_match_the_bytes_at_the_pinned_ref(self):
        # What the bootstrap actually promises is that runtime.json describes the
        # bytes a user downloads *at the pinned tag*. Hashing the working tree
        # instead only holds at a release commit, so it turned every feature
        # branch that touched emulo.py permanently red.
        value = bootstrap.load_metadata(ROOT / ".agents" / "skills" / "emulo" / "runtime.json")
        ref = value["ref"]
        for name in ("emulo.py", "MINING_PROMPT.md"):
            shown = subprocess.run(
                ["git", "show", f"{ref}:{name}"],
                cwd=ROOT, capture_output=True,
            )
            if shown.returncode != 0:
                self.skipTest(
                    f"tag {ref} is not present in this checkout, so the pinned bytes "
                    "cannot be read. Fetch tags (fetch-depth: 0) to enforce this."
                )
            canonical = shown.stdout.replace(b"\r\n", b"\n")
            self.assertEqual(digest(canonical), value["files"][name]["sha256"], name)

    def test_working_tree_matches_the_pin_when_this_commit_is_the_release(self):
        # The other half of the old test, kept where it is actually true: if HEAD
        # *is* the pinned release commit, the tree must match the pin. That is what
        # catches editing emulo.py and forgetting to re-pin before tagging.
        value = bootstrap.load_metadata(ROOT / ".agents" / "skills" / "emulo" / "runtime.json")
        ref = value["ref"]
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        tag = subprocess.run(
            ["git", "rev-parse", f"{ref}^{{commit}}"], cwd=ROOT, capture_output=True, text=True
        )
        if head.returncode != 0 or tag.returncode != 0:
            self.skipTest(f"cannot resolve HEAD or {ref} in this checkout")
        if head.stdout.strip() != tag.stdout.strip():
            self.skipTest(f"HEAD is not the {ref} release commit")
        for name in ("emulo.py", "MINING_PROMPT.md"):
            canonical = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(digest(canonical), value["files"][name]["sha256"], name)

    def test_source_root_installs_both_files_outside_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            home = root / "private"
            result = bootstrap.install_runtime(metadata(), str(home), source_root=str(source))
            runtime = Path(result["runtime_dir"])
            self.assertEqual(b"print('emulo')\n", (runtime / "emulo.py").read_bytes())
            self.assertEqual(b"# prompt\n", (runtime / "MINING_PROMPT.md").read_bytes())
            self.assertTrue(str(runtime).startswith(str(home)))
            self.assertTrue((home / "runtime" / "current.json").is_file())

    def test_hash_mismatch_preserves_previous_runtime_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            home = root / "private"
            bootstrap.install_runtime(metadata(), str(home), source_root=str(source))
            pointer = home / "runtime" / "current.json"
            before = pointer.read_bytes()
            release = metadata("0.2.0", "v0.2.0", "0" * 64, digest(b"# prompt\n"))
            with self.assertRaisesRegex(ValueError, "sha256 mismatch for emulo.py"):
                bootstrap.install_runtime(release, str(home), source_root=str(source))
            self.assertEqual(before, pointer.read_bytes())


if __name__ == "__main__":
    unittest.main()

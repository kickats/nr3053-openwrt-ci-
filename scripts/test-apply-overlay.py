#!/usr/bin/env python3
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ApplyOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        self.script = self.repo / "scripts/apply-overlay.sh"
        shutil.copy2(Path(__file__).with_name("apply-overlay.sh"), self.script)
        self.source = self.root / "openwrt"
        self.source.mkdir()
        self.git("init", "--quiet")
        (self.source / "base.txt").write_text("before\n")
        self.git("add", "base.txt")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "Fixture")
        for tree in ("target", "files", "package"):
            path = self.repo / "overlay" / tree / "new/script"
            path.parent.mkdir(parents=True)
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        (self.repo / "nr3053.seed.config").write_text("CONFIG_CCACHE=y\n")
        (self.repo / "overlay/0001-nr3053-integration.patch").write_text(
            "diff --git a/base.txt b/base.txt\n--- a/base.txt\n+++ b/base.txt\n"
            "@@ -1 +1 @@\n-before\n+after\n")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.source), *args], text=True)

    def apply(self):
        return subprocess.run(["bash", str(self.script), str(self.source)],
                              capture_output=True, text=True)

    def assert_rejected_before_patch(self, message):
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertEqual((self.source / "base.txt").read_text(), "before\n")

    def test_all_trees_and_modes_copied(self):
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.source / "base.txt").read_text(), "after\n")
        for tree in ("target", "files", "package"):
            path = self.source / tree / "new/script"
            self.assertEqual(path.read_bytes(), (self.repo / "overlay" / tree / "new/script").read_bytes())
            self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_missing_tree_rejected(self):
        shutil.rmtree(self.repo / "overlay/package")
        self.assert_rejected_before_patch("Missing or invalid overlay tree: package")

    def test_file_collision_rejected(self):
        path = self.source / "package/new/script"
        path.parent.mkdir(parents=True)
        path.write_text("existing\n")
        self.assert_rejected_before_patch("Refusing to overwrite")
        self.assertEqual(path.read_text(), "existing\n")

    def test_directory_file_collision_rejected(self):
        (self.source / "package").mkdir()
        (self.source / "package/new").write_text("existing\n")
        self.assert_rejected_before_patch("Refusing to overwrite")

    def test_symlink_directory_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.source / "package").symlink_to(outside, target_is_directory=True)
        self.assert_rejected_before_patch("Refusing invalid overlay destination")
        self.assertFalse(any(outside.iterdir()))

    def test_seed_collision_rejected(self):
        (self.source / "nr3053.seed.config").write_text("existing\n")
        self.assert_rejected_before_patch("Refusing to overwrite")


if __name__ == "__main__":
    unittest.main()

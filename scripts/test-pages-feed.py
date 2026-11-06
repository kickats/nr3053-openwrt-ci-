#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("pages_feed", Path(__file__).with_name("pages-feed.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
feed_path = Path(sys.argv.pop(1)).resolve()
key_path = Path("keys/nr3053-kmods.pub").resolve()


class PagesFeedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.feed = self.root / "feed"
        shutil.copytree(feed_path, self.feed)
        self.output = self.root / "pages"

    def prepare(self, build_id="123-1"):
        module.prepare(self.feed, self.output, build_id, key_path)

    def test_only_public_payload(self):
        (self.feed / "private.key").write_text("must not publish")
        self.prepare()
        files = [path for path in self.output.rglob("*") if path.is_file()]
        names = {path.name for path in files}
        self.assertNotIn("private.key", names)
        self.assertNotIn("kernel-build.config", names)
        self.assertNotIn("kmod-feed.json", names)
        self.assertEqual(len([path for path in files if path.suffix == ".apk"]), 74)
        self.assertEqual(names - {path.name for path in files if path.suffix == ".apk"},
                         {"index.html", "packages.adb", "nr3053-kmods.pub"})
        with self.assertRaises(ValueError):
            self.prepare()

    def test_corrupted_payload(self):
        package = next(self.feed.glob("*.apk"))
        with package.open("ab") as stream:
            stream.write(b"corruption")
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            self.prepare()

    def test_mixed_abi(self):
        report_path = self.feed / "kmod-feed.json"
        report = json.loads(report_path.read_text())
        report["packages"][0]["kernel_dependency"] = "kernel=wrong"
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "Mixed kernel ABI"):
            self.prepare()

    def test_bad_path(self):
        with self.assertRaisesRegex(ValueError, "identifier"):
            self.prepare("../../untrusted")

    def test_unverified_index(self):
        report_path = self.feed / "kmod-feed.json"
        report = json.loads(report_path.read_text())
        report["index_signature_verified"] = False
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "signatures"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ThemeDefaultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = Path(__file__).resolve().parents[1]
        original = self.repo / "overlay/files/etc/uci-defaults/zzzz-nr3053-theme"
        self.defaults = self.root / "defaults"
        self.defaults.mkdir()
        self.script = self.defaults / original.name
        self.script.write_text(original.read_text().replace("/usr/share/ucode/", str(self.root / "usr/share/ucode") + "/")
                               .replace("/www/", str(self.root / "www") + "/"))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin) + ":" + os.environ["PATH"],
                        UCI_CALLS=str(self.root / "uci.calls"),
                        LOGGER_CALLS=str(self.root / "logger.calls"), FAIL_UCI="")
        for name, body in {
            "uci": 'printf "%s\\n" "$*" >> "$UCI_CALLS"\n'
                   '[ -z "$FAIL_UCI" ] || [ "$*" != "$FAIL_UCI" ]\n',
            "logger": 'printf "%s\\n" "$*" >> "$LOGGER_CALLS"\n',
        }.items():
            path = self.bin / name
            path.write_text("#!/bin/sh\n" + body)
            path.chmod(0o755)
        assets = [
            *(f"usr/share/ucode/luci/template/themes/glass/{name}.ut"
              for name in ("header", "header_login", "footer", "footer_login", "sysauth")),
            "www/luci-static/glass/css/cascade.css",
            "www/luci-static/glass/css/dark.css",
            "www/luci-static/glass/img/glass-logo.svg",
            "www/luci-static/resources/menu-glass.js",
            "www/luci-static/resources/status-glass.js",
            "www/luci-static/resources/view/system/glass.js",
            "www/luci-static/bootstrap/cascade.css",
        ]
        for relative in assets:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n")

    def run_defaults(self):
        return subprocess.run(
            ["sh", "-c", 'result=0; for file in "$1"/*; do [ -f "$file" ] || continue; '
             '( . "$file" ) && rm "$file" || result=1; done; exit "$result"',
             "defaults-test", str(self.defaults)], env=self.env, capture_output=True, text=True)

    def test_selects_glass_once_and_preserves_later_choices(self):
        first = self.run_defaults()
        self.assertEqual(first.returncode, 0, first.stderr)
        expected = ["set luci.themes.Glass=/luci-static/glass",
                    "set luci.main.mediaurlbase=/luci-static/glass", "commit luci"]
        self.assertEqual((self.root / "uci.calls").read_text().splitlines(), expected)
        self.assertFalse(self.script.exists())
        second = self.run_defaults()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.root / "uci.calls").read_text().splitlines(), expected)

    def test_missing_template_fails_before_uci_and_is_retained(self):
        (self.root / "usr/share/ucode/luci/template/themes/glass/header.ut").unlink()
        result = self.run_defaults()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing or empty theme file", result.stderr)
        self.assertTrue(self.script.exists())
        self.assertFalse((self.root / "uci.calls").exists())
        self.assertIn("Missing or empty theme file", (self.root / "logger.calls").read_text())

    def test_empty_css_fails_before_uci(self):
        (self.root / "www/luci-static/glass/css/cascade.css").write_text("")
        result = self.run_defaults()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "uci.calls").exists())

    def test_uci_failures_are_explicit_and_retryable(self):
        for command in ("set luci.themes.Glass=/luci-static/glass",
                        "set luci.main.mediaurlbase=/luci-static/glass", "commit luci"):
            with self.subTest(command=command):
                self.env["FAIL_UCI"] = command
                result = self.run_defaults()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("nr3053-theme: Cannot", result.stderr)
                self.assertTrue(self.script.exists())
                self.assertIn("Cannot", (self.root / "logger.calls").read_text())


if __name__ == "__main__":
    unittest.main()

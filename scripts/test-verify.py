#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class VerifyConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.source = Path(self.temporary.name)
        self.repo = Path(__file__).resolve().parent.parent
        self.seed = (self.repo / "nr3053.seed.config").read_text()

    def verify(self, additions="", kmods=False):
        config = self.seed + "\n" + additions
        command = [sys.executable, str(self.repo / "scripts/verify.py"),
                   str(self.source), "--config-only"]
        if kmods:
            config += "\n" + (self.repo / "nr3053.kmods.config").read_text()
            command += ["--kmod-config", str(self.repo / "nr3053.kmods.config")]
        (self.source / ".config").write_text(config)
        return subprocess.run(command, capture_output=True, text=True)

    def test_both_modes_accept_debugfs(self):
        for extended in (False, True):
            with self.subTest(extended=extended):
                result = self.verify(kmods=extended)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_required_parity_selections(self):
        for symbol in ("PACKAGE_htop", "PACKAGE_iperf3", "PACKAGE_openssl-util",
                       "PACKAGE_libustream-openssl", "PACKAGE_bridger",
                       "PACKAGE_kmod-nf-nathelper-extra", "KERNEL_DEBUG_FS"):
            with self.subTest(symbol=symbol):
                original = self.seed
                self.seed = original.replace(f"CONFIG_{symbol}=y", "")
                result = self.verify()
                self.seed = original
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Missing config", result.stderr)

    def test_conflicting_variants(self):
        for name in ("dnsmasq", "iperf3-ssl", "wpad-basic-mbedtls",
                     "wpad-basic-openssl", "wpad-mbedtls", "libustream-mbedtls"):
            with self.subTest(package=name):
                result = self.verify(f"CONFIG_PACKAGE_{name}=y\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Conflicting", result.stderr)

    def test_existing_guardrails(self):
        for symbol in ("KERNEL_DEBUG_INFO", "KERNEL_DEBUG_INFO_BTF",
                       "KERNEL_DEBUG_INFO_BTF_MODULES", "KERNEL_DEBUG_KERNEL",
                       "PACKAGE_MAC80211_DEBUGFS", "PACKAGE_tailscale",
                       "PACKAGE_usteer", "LUCI_LANG_zh_Hans"):
            with self.subTest(symbol=symbol):
                self.assertNotEqual(self.verify(f"CONFIG_{symbol}=y\n").returncode, 0)

    def test_optional_modules_must_remain_standalone(self):
        self.seed += "\nCONFIG_PACKAGE_kmod-usb3=y\n"
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.source / ".config").write_text(self.seed)
        result = subprocess.run(
            [sys.executable, str(self.repo / "scripts/verify.py"), str(self.source),
             "--config-only", "--kmod-config", str(self.repo / "nr3053.kmods.config")],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Optional kmods missing/not standalone", result.stderr)


if __name__ == "__main__":
    unittest.main()

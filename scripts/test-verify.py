#!/usr/bin/env python3
import hashlib
import json
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
                       "PACKAGE_libustream-openssl", "PACKAGE_wpad-openssl", "PACKAGE_bridger",
                       "PACKAGE_kmod-nf-nathelper-extra", "PACKAGE_luci-theme-glass", "KERNEL_DEBUG_FS"):
            with self.subTest(symbol=symbol):
                original = self.seed
                self.seed = original.replace(f"CONFIG_{symbol}=y", "")
                result = self.verify()
                self.seed = original
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Missing config", result.stderr)

    def test_seed_preserves_default_variant_exclusions(self):
        for package in ("dnsmasq", "wpad-basic-mbedtls", "libustream-mbedtls"):
            with self.subTest(package=package):
                exclusion = f"# CONFIG_PACKAGE_{package} is not set"
                self.assertEqual(self.seed.splitlines().count(exclusion), 1,
                                 f"Preserve the seed exclusion verbatim: {exclusion}")
                self.assertNotIn(f"CONFIG_PACKAGE_{package}=y", self.seed.splitlines())
                self.assertNotIn(f"CONFIG_PACKAGE_{package}=m", self.seed.splitlines())

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

    def test_glass_required_in_image_manifest(self):
        (self.source / ".config").write_text(self.seed)
        images = self.source / "bin/targets/mediatek/filogic"
        images.mkdir(parents=True)
        entries = []
        for kind in ("kernel", "sysupgrade"):
            path = images / f"test-{kind}.bin"
            path.write_bytes(b"fixture")
            entries.append({"type": kind, "name": path.name, "size": path.stat().st_size,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        (images / "profiles.json").write_text(json.dumps({
            "target": "mediatek/filogic", "version_number": "25.12.6",
            "linux_kernel": {"version": "6.12.112"},
            "profiles": {"sdmc_nr3053": {
                "supported_devices": ["viettel,nr3053", "sdmc,nr3053"],
                "file_size_limits": {"image": 0xEA00000}, "images": entries}},
        }))
        names = [line.split("=", 1)[0].removeprefix("CONFIG_PACKAGE_")
                 for line in self.seed.splitlines()
                 if line.startswith("CONFIG_PACKAGE_") and line.endswith("=y")
                 and line != "CONFIG_PACKAGE_luci-theme-glass=y"]
        (images / "openwrt-mediatek-filogic-sdmc_nr3053.manifest").write_text(
            "".join(f"{name} - fixture\n" for name in names))
        result = subprocess.run(
            [sys.executable, str(self.repo / "scripts/verify.py"), str(self.source),
             "--output", str(self.source / "output")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing image packages: {'luci-theme-glass'}", result.stderr)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile


def require(condition, message):
    if not condition:
        raise SystemExit(message)


parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("--tag", default="v25.12.6")
parser.add_argument("--config-only", action="store_true")
parser.add_argument("--kmod-config", type=Path)
parser.add_argument("--output", type=Path, default=Path("artifacts"))
args = parser.parse_args()
source = args.source.resolve()
config = (source / ".config").read_text()
selected = set(re.findall(r"^CONFIG_([^=\n]+)=y$", config, re.MULTILINE))
required_packages = {"cloudflared", "luci-app-cloudflared", "pbr", "luci-app-pbr"}
required_config = {
    "TARGET_mediatek", "TARGET_mediatek_filogic",
    "TARGET_mediatek_filogic_DEVICE_sdmc_nr3053", "CCACHE",
    *(f"PACKAGE_{name}" for name in required_packages),
}
require(required_config <= selected, f"Missing config: {required_config - selected}")
require(not any("tailscale" in name.lower() for name in selected), "Tailscale selected")
require(not ({"PACKAGE_usteer", "PACKAGE_luci-app-usteer"} & selected),
        "Unrequested band-steering package selected")
require(not any(re.search(r"(?:LUCI_LANG_zh|PACKAGE_luci-i18n-.*-zh-)", name)
                for name in selected), "Chinese translation selected")
require(not any(name.startswith("KERNEL_DEBUG_INFO") for name in selected),
        "Kernel debug/BTF selected")
require(not ({"KERNEL_DEBUG_KERNEL", "KERNEL_DEBUG_FS", "PACKAGE_MAC80211_DEBUGFS"} & selected),
        "Kernel/Wi-Fi debug selected")
if args.kmod_config:
    requested = set(re.findall(r"^CONFIG_PACKAGE_(kmod-[^=\n]+)=m$",
                               args.kmod_config.read_text(), re.MULTILINE))
    resolved = set(re.findall(r"^CONFIG_PACKAGE_(kmod-[^=\n]+)=m$", config, re.MULTILINE))
    require(requested and requested <= resolved,
            f"Optional kmods missing/not standalone: {requested - resolved}")
if args.config_only:
    print("NR3053 configuration verified; no firmware build performed by this check.")
    raise SystemExit(0)

images_dir = source / "bin/targets/mediatek/filogic"
overview = json.loads((images_dir / "profiles.json").read_text())
require(overview["target"] == "mediatek/filogic", "Wrong target")
require(overview["version_number"] == args.tag.removeprefix("v"), "Unexpected version")
require(overview["linux_kernel"]["version"].startswith("6.12."), "Review port for new kernel")
profile = overview["profiles"]["sdmc_nr3053"]
aliases = {"viettel,nr3053", "sdmc,nr3053"}
require(set(profile["supported_devices"]) == aliases, "Device aliases changed")
require(profile["file_size_limits"]["image"] <= 0xEA00000, "Image limit exceeds UBI partition")
images = {entry["type"]: entry for entry in profile["images"]}
require({"kernel", "sysupgrade"} <= images.keys(), "Missing initramfs or sysupgrade")
output = args.output.resolve()
require(not output.exists() or not any(output.iterdir()), "Output must be absent or empty")
output.mkdir(parents=True, exist_ok=True)
for kind in ("kernel", "sysupgrade"):
    entry = images[kind]
    require(Path(entry["name"]).name == entry["name"], "Unsafe image filename")
    image = images_dir / entry["name"]
    require(image.stat().st_size == entry["size"], f"Wrong image size: {image.name}")
    require(hashlib.sha256(image.read_bytes()).hexdigest() == entry["sha256"],
            f"Wrong image digest: {image.name}")

image_manifest = images_dir / "openwrt-mediatek-filogic-sdmc_nr3053.manifest"
packages = {line.split()[0] for line in image_manifest.read_text().splitlines() if line.strip()}
require(required_packages <= packages, f"Missing image packages: {required_packages - packages}")
require(not any("tailscale" in name.lower() for name in packages), "Tailscale in image")
require(not any(re.search(r"^luci-i18n-.*-zh-", name) for name in packages),
        "Chinese translation in image")
sysupgrade = images_dir / images["sysupgrade"]["name"]
metadata_path = output / "sysupgrade-metadata.json"
subprocess.run([str(source / "staging_dir/host/bin/fwtool"), "-i",
                str(metadata_path), str(sysupgrade)], check=True)
metadata = json.loads(metadata_path.read_text())
require(set(metadata["supported_devices"]) == aliases, "Wrong sysupgrade aliases")
require(metadata["version"]["board"] == "sdmc_nr3053", "Wrong metadata board")
with tempfile.TemporaryDirectory(prefix="nr3053-image-check-") as directory:
    temporary = Path(directory)
    with tarfile.open(sysupgrade) as archive:
        for member, destination in (("kernel", "kernel.fit"), ("root", "root.squashfs")):
            info = archive.getmember(f"sysupgrade-sdmc_nr3053/{member}")
            require(info.isfile() and info.size > 0, f"Missing/empty {member}")
            with archive.extractfile(info) as reader, (temporary / destination).open("wb") as writer:
                shutil.copyfileobj(reader, writer)
    require((temporary / "root.squashfs").read_bytes()[:4] == b"hsqs", "Rootfs is not squashfs")
    for label, path in (("sysupgrade", temporary / "kernel.fit"),
                        ("initramfs", images_dir / images["kernel"]["name"])):
        listing = subprocess.check_output(
            [str(source / "staging_dir/host/bin/mkimage"), "-l", str(path)], text=True)
        for image_type in ("Kernel Image", "Flat Device Tree"):
            require(re.search(rf"Type:\s+{image_type}", listing), f"{label}: missing {image_type}")
        for reference in ("Kernel", "FDT"):
            match = re.search(rf"^\s+{reference}:\s+(\S+)", listing, re.MULTILINE)
            require(match is not None, f"{label}: missing {reference} reference")
            require(re.search(rf"Image \d+ \({re.escape(match[1])}\)", listing),
                    f"{label}: dangling {reference} reference")
        if label == "initramfs":
            require(re.search(r"Type:\s+RAMDisk Image", listing), "Initramfs has no ramdisk")
        (output / f"{label}-fit.txt").write_text(listing)
    subprocess.run([str(source / "staging_dir/host/bin/unsquashfs4"), "-no-xattrs",
                    "-d", str(temporary / "rootfs"), "-excludes",
                    str(temporary / "root.squashfs"), "dev/console"], check=True,
                   stdout=subprocess.DEVNULL)
    rootfs = temporary / "rootfs"
    matches = subprocess.run(["grep", "-r", "-a", "-i", "-l", "diepkhoa", str(rootfs)],
                             capture_output=True, text=True)
    require(matches.returncode == 1, f"Branding scan failed: {matches.stdout}{matches.stderr}")
    for path in rootfs.rglob("*"):
        require(not any(marker in path.name for marker in ("zh-cn", "zh-tw", "zh_Hans", "zh_Hant")),
                f"Chinese translation path: {path}")
    repositories = (rootfs / "etc/apk/repositories.d/distfeeds.list").read_text().splitlines()
    urls = [line.strip() for line in repositories if line.strip() and not line.startswith("#")]
    require(urls and all(url.startswith("https://downloads.openwrt.org/") for url in urls),
            "Non-official repository configured")
    platform = (rootfs / "lib/upgrade/platform.sh").read_text()
    require('nand_do_platform_check "sdmc,nr3053" "$1"' in platform, "Upgrade alias fix missing")

for kind in ("kernel", "sysupgrade"):
    shutil.copy2(images_dir / images[kind]["name"], output / images[kind]["name"])
for name in ("profiles.json", "config.buildinfo", "feeds.buildinfo", "version.buildinfo"):
    shutil.copy2(images_dir / name, output / name)
shutil.copy2(image_manifest, output / image_manifest.name)
shutil.copy2(source / ".config", output / ".config")
(output / "verification.json").write_text(json.dumps({
    "tag": args.tag, "target": overview["target"], "kernel": overview["linux_kernel"],
    "supported_devices": sorted(aliases), "required_packages": sorted(required_packages),
    "tailscale_present": False, "diepkhoa_matches": 0, "chinese_translation_files": 0,
    "artifact_checks_passed": True, "native_sysupgrade_test_performed": False,
    "hardware_boot_tested": False, "flashed": False,
    "warning": "CI checks cannot replace native sysupgrade -T and hardware testing. Never force-flash."
}, indent=2) + "\n")
(output / "sha256sums").write_text("".join(
    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
    for path in sorted(output.iterdir()) if path.is_file() and path.name != "sha256sums"
))
subprocess.run(["sha256sum", "-c", "sha256sums"], cwd=output, check=True)
print(f"Verified artifacts: {output}; no factory image exported.")

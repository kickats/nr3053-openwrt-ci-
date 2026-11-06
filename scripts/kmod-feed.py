#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def fail(message):
    raise SystemExit(message)


def group(name):
    if name.startswith(("kmod-mt", "kmod-cfg80211", "kmod-mac80211")):
        return "wifi"
    if name.startswith(("kmod-nf", "kmod-ipt")):
        return "firewall-flowtable"
    if name.startswith(("kmod-ppp", "kmod-slhc", "kmod-tun", "kmod-wireguard", "kmod-udptunnel")):
        return "ppp-vpn"
    if name.startswith(("kmod-usb", "kmod-scsi", "kmod-fs", "kmod-nls")):
        return "usb-filesystems"
    if name.startswith(("kmod-sched", "kmod-ifb", "kmod-tcp-bbr")):
        return "sqm-scheduler"
    if name.startswith("kmod-crypto"):
        return "crypto"
    return "platform-dependencies"


parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--sign-key", type=Path, required=True)
parser.add_argument("--public-key", type=Path, required=True)
args = parser.parse_args()
source = args.source.resolve()
output = args.output.resolve()
if output.exists() and any(output.iterdir()):
    fail("Output must be absent or empty; never mix different build ABIs.")
apk = source / "staging_dir/host/bin/apk"
manifest_path = source / "bin/targets/mediatek/filogic/openwrt-mediatek-filogic-sdmc_nr3053.manifest"
firmware = dict(line.split(" - ", 1) for line in manifest_path.read_text().splitlines() if line.strip())
kernel = firmware["kernel"]
kernel_version, abi = kernel.split("~", 1)
abi = abi.rsplit("-r", 1)[0]
vermagic_file = source / f"build_dir/target-aarch64_cortex-a53_musl/linux-mediatek_filogic/linux-{kernel_version}/.vermagic"
if vermagic_file.read_text().strip() != abi:
    fail("Built kernel ABI differs from the firmware manifest; rebuild firmware and modules together.")
config = (source / ".config").read_text()
selected = dict(re.findall(r"^CONFIG_PACKAGE_(kmod-[^=\n]+)=(y|m)$", config, re.MULTILINE))
public = subprocess.check_output(["openssl", "pkey", "-in", str(args.sign_key), "-pubout"])
if public.strip() != args.public_key.read_bytes().strip():
    fail("Signing secret does not match the repository public key.")
packages = {}
duplicates = 0
module_vermagic = set()
with tempfile.TemporaryDirectory(prefix="nr3053-kmod-check-") as directory:
    temporary = Path(directory)
    for base in (source / "bin/targets/mediatek/filogic/packages", source / "bin/packages"):
        for path in sorted(base.rglob("kmod-*.apk")):
            data = json.loads(subprocess.check_output(
                [str(apk), "adbdump", "--format", "json", str(path)]))
            info = data["info"]
            name = info["name"]
            if name not in selected:
                continue
            dependencies = info.get("depends", [])
            if [entry for entry in dependencies if entry.startswith("kernel=")] != [f"kernel={kernel}"]:
                fail(f"{path.name}: wrong kernel dependency; refusing mixed ABI feed.")
            if name in packages:
                if packages[name]["input_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
                    fail(f"Conflicting package copies: {name}")
                duplicates += 1
                continue
            destination = temporary / name
            destination.mkdir()
            # Inspect only locally built input; exported copies are resigned and verified below.
            subprocess.run([str(apk), "extract", "--allow-untrusted", "--no-chown",
                            "--destination", str(destination), str(path)],
                           check=True, stdout=subprocess.DEVNULL)
            modules = list(destination.rglob("*.ko"))
            for module in modules:
                values = re.findall(rb"vermagic=([^\x00]+)\x00", module.read_bytes())
                if len(values) != 1 or not values[0].startswith((kernel_version + " ").encode()):
                    fail(f"Invalid module vermagic: {module.name}")
                module_vermagic.add(values[0].decode())
            packages[name] = {
                "name": name, "version": info["version"], "arch": info["arch"],
                "input_path": str(path.relative_to(source)),
                "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "input_size_bytes": path.stat().st_size,
                "in_firmware": name in firmware,
                "config": selected[name], "group": group(name),
                "kernel_dependency": f"kernel={kernel}", "module_count": len(modules),
                "dependencies": dependencies,
            }
    if set(selected) != packages.keys():
        fail(f"Selected kmods not built: {sorted(set(selected) - packages.keys())}")
    if len(module_vermagic) != 1:
        fail(f"Inconsistent module vermagic: {module_vermagic}")
    arches = {package["arch"] for package in packages.values()}
    if arches != {"aarch64_cortex-a53"}:
        fail(f"Unexpected architecture: {arches}")
    for name, package in packages.items():
        for dependency in package["dependencies"]:
            dependency_name = re.split(r"[<>=~]", dependency, maxsplit=1)[0]
            if dependency_name.startswith("kmod-") and dependency_name not in packages:
                fail(f"Missing dependency {dependency_name} for {name}")
    output.mkdir(parents=True, exist_ok=True)
    trusted = temporary / "keys"
    trusted.mkdir()
    shutil.copy2(args.public_key, trusted / "nr3053-kmods.pub")
    apk_paths = []
    for name, package in sorted(packages.items()):
        destination = output / f"{name}-{package['version']}.apk"
        shutil.copy2(source / package["input_path"], destination)
        subprocess.run([str(apk), "adbsign", "--allow-untrusted", "--reset-signatures", "--sign-key",
                        str(args.sign_key), str(destination)], check=True)
        subprocess.run([str(apk), "--keys-dir", str(trusted), "verify", str(destination)],
                       check=True, stdout=subprocess.DEVNULL)
        package["signed_size_bytes"] = destination.stat().st_size
        apk_paths.append(str(destination))
    subprocess.run([str(apk), "--keys-dir", str(trusted), "mkndx", "--sign-key", str(args.sign_key),
                    "--description", f"NR3053 {kernel}",
                    "--output", str(output / "packages.adb"), *apk_paths], check=True)
    subprocess.run([str(apk), "--keys-dir", str(trusted), "verify", str(output / "packages.adb")],
                   check=True)

shutil.copy2(args.public_key, output / "nr3053-kmods.pub")
shutil.copy2(source / ".config", output / "kernel-build.config")
categories = {}
for package in packages.values():
    category = categories.setdefault(package["group"], {"count": 0, "input_bytes": 0})
    category["count"] += 1
    category["input_bytes"] += package["input_size_bytes"]
report = {
    "kernel_package": kernel, "abi": abi, "elf_vermagic": sorted(module_vermagic),
    "count": len(packages), "duplicate_copies_excluded": duplicates,
    "input_apk_bytes": sum(package["input_size_bytes"] for package in packages.values()),
    "signed_apk_bytes": sum(package["signed_size_bytes"] for package in packages.values()),
    "in_firmware_count": sum(package["in_firmware"] for package in packages.values()),
    "standalone_only_count": sum(not package["in_firmware"] for package in packages.values()),
    "module_files_checked": sum(package["module_count"] for package in packages.values()),
    "categories": categories, "packages": list(packages.values()),
    "index_signature_verified": True, "package_signatures_verified": True,
    "live_router_verified": False,
    "warning": "Exact kernel package ABI is required, not just uname -r. Never force dependencies.",
}
(output / "kmod-feed.json").write_text(json.dumps(report, indent=2) + "\n")
(output / "sha256sums").write_text("".join(
    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
    for path in sorted(output.iterdir()) if path.is_file() and path.name != "sha256sums"
))
subprocess.run(["sha256sum", "-c", "sha256sums"], cwd=output, check=True,
               stdout=subprocess.DEVNULL)
print(json.dumps({key: value for key, value in report.items() if key != "packages"}, indent=2))

#!/usr/bin/env python3
"""Publish only the signed feed payload, never build logs or private material."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil


def prepare(feed, output, build_id, public_key):
    if not re.fullmatch(r"[0-9]+-[0-9]+", build_id):
        raise ValueError("Invalid run-attempt identifier")
    if output.exists():
        raise ValueError("Pages output must not already exist")
    report = json.loads((feed / "kmod-feed.json").read_text())
    kernel = report["kernel_package"]
    match = re.fullmatch(r"([0-9]+\.[0-9]+\.[0-9]+)~([0-9a-f]{32})-r[0-9]+", kernel)
    if not match or report["abi"] != match[2]:
        raise ValueError("Invalid or inconsistent kernel ABI")
    if not report["index_signature_verified"] or not report["package_signatures_verified"]:
        raise ValueError("Build did not verify feed signatures")
    checksums = {}
    for line in (feed / "sha256sums").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or Path(name).name != name or name in checksums:
            raise ValueError("Invalid checksum entry")
        checksums[name] = digest
    names = {"packages.adb", "nr3053-kmods.pub"}
    for package in report["packages"]:
        if package["kernel_dependency"] != f"kernel={kernel}":
            raise ValueError("Mixed kernel ABI")
        name = f"{package['name']}-{package['version']}.apk"
        if not re.fullmatch(r"kmod-[a-zA-Z0-9+_.~-]+\.apk", name) or name in names:
            raise ValueError("Invalid or duplicate package filename")
        names.add(name)
    if len(names) != report["count"] + 2 or not report["count"]:
        raise ValueError("Incorrect package count")
    for name in names:
        path = feed / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Invalid payload: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksums.get(name):
            raise ValueError(f"Checksum mismatch: {name}")
    if (feed / "nr3053-kmods.pub").read_bytes() != public_key.read_bytes():
        raise ValueError("Feed key differs from the reviewed repository key")
    relative = Path("feeds") / match[1] / match[2] / build_id
    destination = output / relative
    destination.mkdir(parents=True)
    for name in sorted(names):
        shutil.copyfile(feed / name, destination / name)
    fingerprint = hashlib.sha256(public_key.read_bytes()).hexdigest()
    text = f"""<!doctype html>
<html lang="vi"><meta charset="utf-8"><title>NR3053 signed kmods</title>
<h1>NR3053: kho kmod da ky</h1>
<p>Kernel package bat buoc: <code>{html.escape(kernel)}</code>.
Khong ep dependencies; chi dung firmware build cung luot.</p>
<p>SHA256 public key: <code>{fingerprint}</code>. Doi chieu qua kenh tin cay.</p>
<p><a href="nr3053-kmods.pub">Public key</a> |
<a href="packages.adb">Signed APK index</a></p>
<p>Sau khi xac minh key, chep vao /etc/apk/keys/nr3053-kmods.pub.
Dat FEED_URL la URL HTTPS cua thu muc nay (khong gom index.html):</p>
<pre>printf 'ndx @nr3053_kmods %s/packages.adb\\n' "$FEED_URL" &gt; /etc/apk/repositories.d/nr3053-kmods.list
apk update
apk add kmod-sched-cake@nr3053_kmods</pre>
<p>Khong dung --allow-untrusted. Pages chi giu lan deploy moi nhat;
URL cu se khong con, hay luu artifact neu can kho lau dai.</p></html>
"""
    (destination / "index.html").write_text(text)
    (output / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>NR3053</title>'
        f'<a href="{relative.as_posix()}/">Signed kmods: {html.escape(kernel)}</a>\n'
    )
    print(f"Pages feed directory: {relative.as_posix()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feed", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--public-key", type=Path, default=Path("keys/nr3053-kmods.pub"))
    args = parser.parse_args()
    prepare(args.feed, args.output, args.build_id, args.public_key)

#!/usr/bin/env python3
"""Build auditable, static ASUS payloads from the qualified fork commit."""
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess

CORE = "a32d18362c987e5007eab9f76c69118947a7b047"
VERSION = "1.104.7"
TAGS = "ts_include_cli,ts_omit_clientupdate,ts_omit_flashappliance"
ROOT = Path(__file__).resolve().parent


def run(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--release", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--arch", choices=("arm64", "armv7"), default="arm64")
    p.add_argument("--go", default="go")
    args = p.parse_args()
    if not re.fullmatch(re.escape(f"v{VERSION}"), args.release):
        p.error("use the application version tag: v1.104.7")
    if f"\nRELEASE={args.release}\n" not in (ROOT / "install.sh").read_text():
        p.error("bootstrap installer must pin the requested release")
    source = args.source.resolve()
    if run(["git", "rev-parse", "HEAD"], cwd=source) != CORE:
        p.error("source must be the qualified v1.104.7 commit")
    if run(["git", "status", "--porcelain"], cwd=source):
        p.error("source must be clean")
    if "go1.27.4 " not in run([args.go, "version"]) + " ":
        p.error("use the qualified Go 1.27.4 toolchain")
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    binary = output / f"tailscaled-{args.arch}"
    env = dict(os.environ, CGO_ENABLED="0", GOOS="linux",
               GOARCH="arm64" if args.arch == "arm64" else "arm", GOARM="7",
               GOARM64="v8.0", GOTOOLCHAIN="local", GOFLAGS="", GOWORK="off", GOMAXPROCS="4")
    stamp = VERSION
    ldflags = (f"-s -w -buildid= -X tailscale.com/version.longStamp={stamp.split(' ')[0]} "
               f"-X tailscale.com/version.shortStamp={VERSION} "
               f"-X tailscale.com/version.gitCommitStamp={CORE}")
    subprocess.run([args.go, "build", "-p=4", "-mod=readonly", "-trimpath", "-tags", TAGS,
                    "-ldflags", ldflags, "-o", str(binary), "./cmd/tailscaled"],
                   cwd=source, env=env, check=True)
    info = run([args.go, "version", "-m", str(binary)])
    for marker in ("CGO_ENABLED=0", "go1.27.4", "v0.65.0-quic.4", "v0.0.35", "7effde6a93dc"):
        if marker not in info:
            raise SystemExit(f"missing build identity: {marker}")
    if CORE.encode() not in binary.read_bytes():
        raise SystemExit("embedded commit mismatch")
    (output / f"build-info-{args.arch}.txt").write_text(info + "\n")
    archive = output / f"tailscale-asus-{args.release}-{args.arch}.gz"
    with binary.open("rb") as src, archive.open("wb") as dst:
        with gzip.GzipFile(filename="", mode="wb", fileobj=dst, compresslevel=9, mtime=0) as gz:
            shutil.copyfileobj(src, gz)
    shutil.copy2(ROOT / "tailscale-asus", output / "tailscale-asus")
    shutil.copy2(ROOT / "install.sh", output / "install-asus.sh")
    for name in ("LICENSE", "LICENSE.tailscale", "NOTICE"):
        shutil.copy2(ROOT.parent / name, output / name)
    manifest = dict(format=1, release=args.release, version=VERSION, arch=args.arch,
                    core=CORE, core_tag="v1.104.7", quic="v0.65.0-quic.4",
                    go="go1.27.4", build_tags=TAGS, sha256=digest(archive),
                    binary_sha256=digest(binary), binary_bytes=binary.stat().st_size,
                    manager_sha256=digest(ROOT / "tailscale-asus"))
    archive.with_suffix(".gz.manifest").write_text("".join(f"{k}={v}\n" for k, v in manifest.items()))
    print(f"{args.arch}: binary={binary.stat().st_size} gzip={archive.stat().st_size} bytes")


if __name__ == "__main__":
    main()

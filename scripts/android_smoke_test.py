#!/usr/bin/env python3
"""Install and launch the Android debug APK when exactly one adb device exists."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APK = ROOT / "android/app/build/outputs/apk/debug/app-debug.apk"


def parse_devices(output: str) -> list[tuple[str, str]]:
    devices = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))
    return devices


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK)
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()

    if shutil.which("adb") is None:
        print(json.dumps({"passed": False, "reason": "adb_missing"}, ensure_ascii=False))
        return 2
    devices = parse_devices(run(["adb", "devices"]).stdout)
    ready = [serial for serial, state in devices if state == "device"]
    if len(ready) != 1:
        print(json.dumps({"passed": False, "reason": "no_device" if not ready else "multiple_devices", "devices": devices}, ensure_ascii=False))
        return 2
    if not args.apk.is_file():
        print(json.dumps({"passed": False, "reason": "apk_missing", "apk": str(args.apk)}, ensure_ascii=False))
        return 1

    serial = ready[0]
    install = None
    if not args.skip_install:
        install = run(["adb", "-s", serial, "install", "-r", str(args.apk)])
        if install.returncode != 0:
            print(json.dumps({"passed": False, "reason": "install_failed", "stderr": install.stderr[-1000:]}, ensure_ascii=False))
            return 1
    launch = run(["adb", "-s", serial, "shell", "am", "start", "-n", "com.blindnav.mobile/.MainActivity"])
    result = {
        "passed": launch.returncode == 0,
        "serial": serial,
        "apk": str(args.apk),
        "installed": not args.skip_install,
        "launch_stdout": launch.stdout.strip(),
        "launch_stderr": launch.stderr.strip(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

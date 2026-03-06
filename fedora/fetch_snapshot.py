#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import urllib.request


CONFIG_PATH = os.path.expanduser("~/.config/hwremote-monitor.json")
DEFAULT_SOURCE = "ssh://loofi@192.168.1.3"


def load_source() -> str:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get("url", DEFAULT_SOURCE)
    except Exception:
        return DEFAULT_SOURCE


def fetch_over_ssh(target: str) -> dict:
    remote_script = r"C:\Users\loofi\hwremote-monitor\lhm-snapshot.ps1"
    cmd = [
        "ssh",
        "-F",
        "/dev/null",
        target,
        f"powershell -NoProfile -ExecutionPolicy Bypass -File {remote_script}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=12, check=True)
    return json.loads(result.stdout)


def fetch_over_http(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "hwremote-monitor/1.0"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch HWMonitor remote snapshot JSON.")
    parser.add_argument("--source", default=load_source(), help="ssh:// target or http(s):// JSON URL")
    args = parser.parse_args()

    try:
        if args.source.startswith("ssh://"):
            payload = fetch_over_ssh(args.source[len("ssh://") :])
        else:
            payload = fetch_over_http(args.source)
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        json.dump({"error": str(exc)}, sys.stdout)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

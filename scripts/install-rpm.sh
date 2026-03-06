#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOPDIR="${RPM_TOPDIR:-$HOME/rpmbuild}"

RPM_PATH="${1:-}"
if [[ -z "$RPM_PATH" ]]; then
  RPM_PATH="$(find "$TOPDIR/RPMS" -type f -name 'hwmonitor-remote-*.rpm' | sort | tail -n 1)"
fi

if [[ -z "$RPM_PATH" || ! -f "$RPM_PATH" ]]; then
  echo "No RPM found. Build one first with scripts/build-rpm.sh" >&2
  exit 1
fi

exec sudo dnf install -y "$RPM_PATH"

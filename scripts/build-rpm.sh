#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-0.2.0}"
TOPDIR="${RPM_TOPDIR:-$HOME/rpmbuild}"
NAME="hwmonitor-remote"
TARBALL="$TOPDIR/SOURCES/${NAME}-${VERSION}.tar.gz"
SPEC_DST="$TOPDIR/SPECS/${NAME}.spec"

mkdir -p "$TOPDIR/SOURCES" "$TOPDIR/SPECS"

python3 - <<PY
import os, tarfile
root = ${ROOT_DIR@Q}
version = ${VERSION@Q}
name = "hwmonitor-remote"
prefix = f"{name}-{version}"
tar_path = ${TARBALL@Q}
with tarfile.open(tar_path, "w:gz") as tar:
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for filename in files:
            if filename.endswith(".pyc"):
                continue
            path = os.path.join(current_root, filename)
            rel = os.path.relpath(path, root)
            tar.add(path, arcname=os.path.join(prefix, rel))
PY

install -m 0644 "$ROOT_DIR/packaging/rpm/${NAME}.spec" "$SPEC_DST"
rpmbuild -ba "$SPEC_DST"

RPM_PATH="$TOPDIR/RPMS/noarch/${NAME}-${VERSION}-1.$(rpm --eval '%{dist}' | sed 's/^\.//').noarch.rpm"
echo "$RPM_PATH"

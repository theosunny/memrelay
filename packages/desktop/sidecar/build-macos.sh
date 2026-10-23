#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
root="$(cd ../../.. && pwd)"
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python \
  "pyinstaller==6.11.1" \
  "$root/packages/core" \
  "$root/packages/sync"
rm -rf build dist
.venv/bin/pyinstaller --noconfirm --clean --onefile --name memrelay \
  --collect-submodules memrelay \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan.on \
  memrelay_entry.py
.venv/bin/pyinstaller --noconfirm --clean --onefile --name memrelay-sync \
  --collect-submodules memrelay_sync \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan.on \
  memrelay_sync_entry.py
dest="$root/packages/desktop/src-tauri/resources"
mkdir -p "$dest"
cp dist/memrelay dist/memrelay-sync "$dest/"
chmod 755 "$dest/memrelay" "$dest/memrelay-sync"
"$dest/memrelay" --help >/dev/null
"$dest/memrelay-sync" --help >/dev/null

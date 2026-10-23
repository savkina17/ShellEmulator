#!/usr/bin/env bash
set -u
echo "=== Stage 2: config ==="
python3 emulator.py --debug --vfs vfs/minimal.json --script scripts/start.sh
echo "--- нет файла VFS ---"
python3 emulator.py --vfs vfs/missing.json
echo "--- нет скрипта ---"
python3 emulator.py --script scripts/missing.sh
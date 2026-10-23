#!/usr/bin/env bash
set -u
echo "=== Stage 3: VFS minimal ==="
printf 'ls /\ncd /home\nls\nexit\n' | python3 emulator.py --vfs vfs/minimal.json

echo "=== Stage 3: VFS multi ==="
printf 'cd /home/user\nls\ndu\nvfs-save multi_out.json\nexit\n' \
  | python3 emulator.py --vfs vfs/multi.json

echo "=== Stage 3: VFS deep ==="
printf 'cd /home/user/projects/alpha/src\npwd\nls\ndu\ncd /home/user/projects\ndu\nexit\n' \
  | python3 emulator.py --vfs vfs/deep.json

echo "=== Stage 3: bad VFS ==="
printf 'exit\n' | python3 emulator.py --vfs vfs/bad.json
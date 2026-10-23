#!/usr/bin/env bash
set -u
echo "=== Stage 4: ls/cd/pwd/du ==="
printf 'pwd\nls /cd /home/user\npwd\nls\ncd ..\npwd\ndu /home\ndu /nope\nls /nope\nexit\n' \
  | python3 emulator.py --vfs vfs/multi.json
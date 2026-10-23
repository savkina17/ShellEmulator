#!/usr/bin/env bash
set -u
echo "=== Stage 1: REPL ==="
printf 'ls\ncd /tmp\npwd\nexit\n' | python3 emulator.py
echo "--- ошибка: неизвестная команда ---"
printf 'foobar a b\nexit\n' | python3 emulator.py
echo "--- кавычки ---"
printf 'ls "a b" c\nexit\n' | python3 emulator.py
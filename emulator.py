#!/usr/bin/env python3

import argparse
import base64
import getpass
import json
import os
import shlex
import socket
import sys



class VFS:
    """Виртуальная файловая система в памяти. Хранится как дерево узлов."""

    def __init__(self, root=None):
        # корень всегда каталог "/"
        self.root = root if root is not None else {"type": "dir", "children": {}}

    # загрузка/сохранение
    @classmethod
    def load(cls, path):
        if not os.path.isfile(path):
            raise FileNotFoundError(f"VFS file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid VFS JSON: {e}")
        cls._validate(data)
        return cls(data)

    @staticmethod
    def _validate(node):
        if not isinstance(node, dict) or "type" not in node:
            raise ValueError("VFS: node must be dict with 'type'")
        if node["type"] == "dir":
            if "children" not in node or not isinstance(node["children"], dict):
                raise ValueError("VFS: dir must have 'children' dict")
            for child in node["children"].values():
                VFS._validate(child)
        elif node["type"] == "file":
            if "content" not in node:
                raise ValueError("VFS: file must have 'content'")
        else:
            raise ValueError(f"VFS: unknown node type {node['type']}")

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.root, f, indent=2, ensure_ascii=False)

    #навигация
    @staticmethod
    def _split(path):
        parts = []
        for p in path.split("/"):
            if p in ("", "."):
                continue
            if p == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        return parts

    def _resolve(self, cwd, path):
        """Возвращает список компонентов абсолютного пути."""
        if path.startswith("/"):
            return self._split(path)
        return self._split(cwd + "/" + path)

    def _get(self, components):
        node = self.root
        for c in components:
            if node["type"] != "dir" or c not in node["children"]:
                return None
            node = node["children"][c]
        return node

    def is_dir(self, cwd, path):
        n = self._get(self._resolve(cwd, path))
        return n is not None and n["type"] == "dir"

    def exists(self, cwd, path):
        return self._get(self._resolve(cwd, path)) is not None

    def listdir(self, cwd, path="."):
        n = self._get(self._resolve(cwd, path))
        if n is None or n["type"] != "dir":
            raise NotADirectoryError(path)
        return sorted(n["children"].keys())

    def size(self, cwd, path):
        n = self._get(self._resolve(cwd, path))
        if n is None:
            raise FileNotFoundError(path)
        return self._size_of(n)

    def _size_of(self, node):
        if node["type"] == "file":
            c = node["content"]
            if node.get("encoding") == "base64":
                try:
                    return len(base64.b64decode(c))
                except Exception:
                    return len(c)
            return len(c.encode("utf-8"))
        return sum(self._size_of(ch) for ch in node["children"].values())

    def walk_size(self, cwd, path="."):
        """Аналог du: общий размер поддерева."""
        return self.size(cwd, path)


#Shell
class Shell:
    def __init__(self, vfs, user, host):
        self.vfs = vfs
        self.user = user
        self.host = host
        self.cwd = "/"
        self.running = True
        self.commands = {
            "ls": self.cmd_ls,
            "cd": self.cmd_cd,
            "pwd": self.cmd_pwd,
            "du": self.cmd_du,
            "vfs-save": self.cmd_vfs_save,
            "exit": self.cmd_exit,
        }

    # ---------- приглашение ----------
    def prompt(self):
        home = f"/home/{self.user}"
        display = "~" if self.cwd == home else self.cwd
        return f"{self.user}@{self.host}:{display}$ "

    # ---------- парсер ----------
    @staticmethod
    def parse(line):
        try:
            return shlex.split(line, posix=True)
        except ValueError as e:
            raise ValueError(f"parse error: {e}")

    # ---------- цикл REPL ----------
    def repl(self):
        while self.running:
            try:
                line = input(self.prompt())
            except EOFError:
                print()
                break
            self.execute(line)

    def execute(self, line, echo=False):
        line = line.strip()
        if not line or line.startswith("#"):
            return
        if echo:
            print(self.prompt() + line)
        try:
            tokens = self.parse(line)
        except ValueError as e:
            print(f"error: {e}")
            return
        if not tokens:
            return
        cmd, args = tokens[0], tokens[1:]
        handler = self.commands.get(cmd)
        if handler is None:
            print(f"{cmd}: command not found")
            return
        try:
            handler(args)
        except Exception as e:
            print(f"{cmd}: {e}")

    # ---------- команды ----------
    def cmd_ls(self, args):
        targets = args if args else ["."]
        multi = len(targets) > 1
        for t in targets:
            try:
                if not self.vfs.exists(self.cwd, t):
                    print(f"ls: cannot access '{t}': No such file or directory")
                    continue
                if self.vfs.is_dir(self.cwd, t):
                    if multi:
                        print(f"{t}:")
                    for name in self.vfs.listdir(self.cwd, t):
                        print(name)
                else:
                    print(t)
            except NotADirectoryError:
                print(f"ls: {t}: Not a directory")

    def cmd_cd(self, args):
        if len(args) > 1:
            raise ValueError("too many arguments")
        target = args[0] if args else f"/home/{self.user}"
        if not self.vfs.exists(self.cwd, target):
            raise FileNotFoundError(f"no such directory: {target}")
        if not self.vfs.is_dir(self.cwd, target):
            raise NotADirectoryError(f"not a directory: {target}")
        comps = self.vfs._resolve(self.cwd, target)
        self.cwd = "/" + "/".join(comps)

    def cmd_pwd(self, args):
        if args:
            raise ValueError("too many arguments")
        print(self.cwd)

    def cmd_du(self, args):
        targets = args if args else ["."]
        for t in targets:
            try:
                print(f"{self.vfs.walk_size(self.cwd, t)}\t{t}")
            except FileNotFoundError:
                print(f"du: cannot access '{t}': No such file or directory")

    def cmd_vfs_save(self, args):
        if len(args) != 1:
            raise ValueError("usage: vfs-save <path>")
        self.vfs.save(args[0])
        print(f"VFS saved to {args[0]}")

    def cmd_exit(self, args):
        self.running = False


#main
def run_script(shell, script_path):
    if not os.path.isfile(script_path):
        print(f"error: start script not found: {script_path}", file=sys.stderr)
        return 1
    with open(script_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            shell.execute(line, echo=True)
            if not shell.running:
                break
    return 0


def main():
    ap = argparse.ArgumentParser(description="UNIX-like shell emulator")
    ap.add_argument("--vfs", required=False, help="path to VFS JSON")
    ap.add_argument("--script", required=False, help="path to start script")
    ap.add_argument("--debug", action="store_true", help="debug dump")
    args = ap.parse_args()

    # --- Этап 2: отладочный вывод параметров ---
    if args.debug:
        print("=== DEBUG PARAMETERS ===")
        print(f"VFS path   : {args.vfs}")
        print(f"Start script: {args.script}")
        print("========================")

    # --- загрузка VFS ---
    if args.vfs:
        try:
            vfs = VFS.load(args.vfs)
        except (FileNotFoundError, ValueError) as e:
            print(f"VFS load error: {e}", file=sys.stderr)
            return 1
    else:
        # VFS по умолчанию: /home/<user> и /tmp
        user = getpass.getuser()
        vfs = VFS({
            "type": "dir",
            "children": {
                "home": {"type": "dir", "children": {
                    user: {"type": "dir", "children": {}}
                }},
                "tmp": {"type": "dir", "children": {}},
            }
        })

    user = getpass.getuser()
    host = socket.gethostname()
    shell = Shell(vfs, user, host)

    # --- режим скрипта ---
    if args.script:
        return run_script(shell, args.script)

    # --- интерактивный REPL ---
    shell.repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
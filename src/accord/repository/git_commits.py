"""正本の置き場の git に、書き込みの操作が変えたファイルを 1 件ずつコミットする口。

git を呼ぶのはこの文書だけである。上の層は、ファイルの名前（設定に書いた名前）だけを渡し、
コマンドの形も作業ツリーの場所も知らない。コミットするのは渡されたファイル 1 つだけで、
人の手で索引に積んだほかの変更は巻き込まない（`git commit -- <path>` の形で、そのパスだけを確定する）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# git に名乗る名前が設定されていない作業ツリーで、コミットが止まらないように使う名前。
FALLBACK_NAME = "accord"
FALLBACK_EMAIL = "accord@localhost"


class GitError(RuntimeError):
    """git のコマンドが失敗したこと。メッセージに置き場の絶対パスは入れない。"""


class GitCommits:
    """1 つの作業ツリーの中のファイルを、状態を見てコミットする。"""

    def __init__(self, work_dir: Path) -> None:
        self.work_dir = work_dir

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.work_dir), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def has_uncommitted_change(self, path: Path) -> bool:
        """そのファイルに、まだコミットしていない変更（索引に積んだものと、追跡していないものを含む）があるか。"""
        if not path.exists():
            return False
        completed = self._run("status", "--porcelain", "--", str(path))
        if completed.returncode != 0:
            raise GitError("git の状態を読めなかった")
        return bool(completed.stdout.strip())

    def _identity(self) -> list[str]:
        """名乗る名前とメールアドレスが作業ツリーに無ければ、代わりの名前を渡す引数を返す。"""
        name = self._run("config", "user.name").stdout.strip()
        email = self._run("config", "user.email").stdout.strip()
        if name and email:
            return []
        return ["-c", f"user.name={name or FALLBACK_NAME}", "-c", f"user.email={email or FALLBACK_EMAIL}"]

    def commit_file(self, path: Path, message: str) -> str:
        """そのファイル 1 つだけをコミットし、コミットの短い識別子を返す。変更が無ければ空文字。"""
        if not self.has_uncommitted_change(path):
            return ""
        added = self._run("add", "--", str(path))
        if added.returncode != 0:
            raise GitError("git の索引にファイルを積めなかった")
        committed = self._run(*self._identity(), "commit", "-m", message, "--", str(path))
        if committed.returncode != 0:
            raise GitError("git のコミットが通らなかった")
        head = self._run("rev-parse", "--short", "HEAD")
        return head.stdout.strip()

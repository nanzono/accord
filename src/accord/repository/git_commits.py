"""正本の置き場の git に、書き込みの操作が変えたファイルを 1 件ずつコミットし、履歴と作業ツリーを読み、戻す口。

git を呼ぶのはこの文書だけである。上の層は、ファイルの名前（accord の形の名前）とコミットの識別子だけを渡し、
コマンドの形も作業ツリーの場所も知らない。コミットするのは渡されたファイルだけで、
accord の外で索引に積まれたほかの変更は巻き込まない（`git commit -- <path>` の形で、そのパスだけを確定する）。

ほかに、置き場の未コミットの変更の一覧（追跡していないファイルを含み、`.gitignore` で外したものは含めない）、
履歴のコミットの一覧、コミット 1 件を打ち消す変更を作ることとそれを取りやめること、作業ツリーを最後の
コミットの状態に戻すことの口を持つ。どのコミットを accord のコミットと見るかは、上の層が決める。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# git に名乗る名前が設定されていない作業ツリーで、コミットが止まらないように使う名前。
FALLBACK_NAME = "accord"
FALLBACK_EMAIL = "accord@localhost"


class GitError(RuntimeError):
    """git のコマンドが失敗したこと。メッセージに置き場の絶対パスは入れない。"""


# 履歴を 1 回で読むときの区切り。コミットの説明に現れない制御文字を使う。
FIELD_SEPARATOR = "\x1f"
RECORD_SEPARATOR = "\x1e"
LOG_FORMAT = f"%H{FIELD_SEPARATOR}%h{FIELD_SEPARATOR}%P{FIELD_SEPARATOR}%B{RECORD_SEPARATOR}"


@dataclass(frozen=True)
class CommitEntry:
    """履歴のコミット 1 件。長い識別子・短い識別子・親の長い識別子・説明の全文。"""

    full: str
    short: str
    parents: tuple[str, ...] = field(default_factory=tuple)
    message: str = ""

    @property
    def is_merge(self) -> bool:
        """合流のコミット（親が 2 つ以上）か。"""
        return len(self.parents) > 1


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

    def commit_paths(self, added: list[Path], removed: list[Path], message: str) -> str:
        """足したか変えたファイルと、消したファイルだけを 1 件のコミットにし、短い識別子を返す。

        移行の操作が、語彙のファイルを作ることと設定ファイルを消すことを 1 件のコミットにするために使う。
        ほかのファイルの変更は巻き込まない（渡したパスだけを確定する）。
        """
        paths: list[str] = []
        for path in added:
            if self._run("add", "--", str(path)).returncode != 0:
                raise GitError("git の索引にファイルを積めなかった")
            paths.append(str(path))
        for path in removed:
            tracked = self._run("ls-files", "--error-unmatch", "--", str(path)).returncode == 0
            if not tracked:
                continue
            if self._run("rm", "-q", "--cached", "--", str(path)).returncode != 0:
                raise GitError("git の索引からファイルを外せなかった")
            paths.append(str(path))
        committed = self._run(*self._identity(), "commit", "-q", "-m", message, "--", *paths)
        if committed.returncode != 0:
            raise GitError("git のコミットが通らなかった")
        head = self._run("rev-parse", "--short", "HEAD")
        return head.stdout.strip()

    # ------------------------------------------------------------ 作業ツリーの状態

    def uncommitted_paths(self) -> list[str]:
        """置き場の中の、まだコミットしていない変更のあるファイルの名前（作業ツリーの根から見た名前）。

        索引に積んだもの・作業ツリーの変更・追跡していないファイルを含み、`.gitignore` で外したものは含めない。
        """
        completed = self._run("status", "--porcelain", "-z", "--untracked-files=all", "--", ".")
        if completed.returncode != 0:
            raise GitError("git の状態を読めなかった")
        names: list[str] = []
        entries = completed.stdout.split("\0")
        index = 0
        while index < len(entries):
            entry = entries[index]
            index += 1
            if len(entry) < 4:
                continue
            status, name = entry[:2], entry[3:]
            if "R" in status or "C" in status:
                # 名前を変えた変更は、元の名前が次の欄に続く。
                index += 1
            if name not in names:
                names.append(name)
        return names

    def has_head(self) -> bool:
        """コミットが 1 件以上あるか。"""
        return self._run("rev-parse", "--verify", "-q", "HEAD").returncode == 0

    def head_short(self) -> str:
        """最後のコミットの短い識別子。コミットが無ければ空文字。"""
        completed = self._run("rev-parse", "--short", "HEAD")
        return completed.stdout.strip() if completed.returncode == 0 else ""

    # ------------------------------------------------------------ 履歴

    def log(self, revisions: list[str]) -> list[CommitEntry]:
        """渡した範囲のコミットを、新しい順に返す。コミットが 1 件も無ければ空の一覧。"""
        if not self.has_head():
            return []
        completed = self._run("log", f"--format={LOG_FORMAT}", *revisions, "--")
        if completed.returncode != 0:
            raise GitError("git の履歴を読めなかった")
        entries: list[CommitEntry] = []
        for record in completed.stdout.split(RECORD_SEPARATOR):
            record = record.lstrip("\n")
            if not record.strip():
                continue
            full, short, parents, message = (record.split(FIELD_SEPARATOR, 3) + ["", "", "", ""])[:4]
            entries.append(
                CommitEntry(
                    full=full.strip(),
                    short=short.strip(),
                    parents=tuple(parents.split()),
                    message=message,
                )
            )
        return entries

    def root_commits(self) -> list[str]:
        """根のコミット（親を持たないコミット）の長い識別子。"""
        if not self.has_head():
            return []
        completed = self._run("rev-list", "--max-parents=0", "HEAD")
        if completed.returncode != 0:
            raise GitError("git の履歴を読めなかった")
        return completed.stdout.split()

    def resolve(self, identifier: str) -> str | None:
        """コミットの識別子（短くても長くてもよい）を長い識別子にする。当たらなければ None。"""
        completed = self._run("rev-parse", "--verify", "-q", f"{identifier}^{{commit}}")
        if completed.returncode != 0:
            return None
        return completed.stdout.strip() or None

    # ------------------------------------------------------------ 打ち消しと戻し

    def revert_without_commit(self, full: str) -> list[str]:
        """そのコミットの変更を打ち消す変更を、コミットせずに作業ツリーと索引に作る。

        ぶつかったら、作った変更を取りやめて置き場を元に戻し、ぶつかったファイルの名前を返す。
        ぶつからなければ空の一覧を返す（変更は索引に積んだまま残る）。
        """
        completed = self._run("revert", "--no-commit", full)
        if completed.returncode == 0:
            return []
        conflicted = self._run("diff", "--name-only", "--diff-filter=U").stdout.split()
        self.abort_revert()
        return conflicted or ["（ぶつかったファイルの名前を git から読めなかった）"]

    def staged_paths(self) -> list[str]:
        """索引に積んだ変更のあるファイルの名前。"""
        completed = self._run("diff", "--cached", "--name-only")
        if completed.returncode != 0:
            raise GitError("git の索引を読めなかった")
        return completed.stdout.split()

    def abort_revert(self) -> None:
        """打ち消しの途中の変更を取りやめ、作業ツリーと索引を最後のコミットの状態に戻す。"""
        if self._run("revert", "--abort").returncode != 0:
            self._run("reset", "-q", "--hard", "HEAD")

    def commit_staged(self, message: str) -> str:
        """索引に積んだ変更を 1 件のコミットにし、短い識別子を返す。変更が無くても 1 件作る。"""
        committed = self._run(*self._identity(), "commit", "-q", "--allow-empty", "-m", message)
        if committed.returncode != 0:
            raise GitError("git のコミットが通らなかった")
        return self.head_short()

    def uncommitted_diff(self) -> str:
        """未コミットの変更の差分。最後のコミットとの差分の文に、追跡していないファイルの名前と中身を足したもの。"""
        parts: list[str] = []
        if self.has_head():
            completed = self._run("diff", "--no-color", "HEAD", "--", ".")
            if completed.returncode != 0:
                raise GitError("git の差分を読めなかった")
            if completed.stdout:
                parts.append(completed.stdout.rstrip("\n"))
        untracked = self._run("ls-files", "--others", "--exclude-standard", "-z", "--", ".")
        if untracked.returncode != 0:
            raise GitError("git の状態を読めなかった")
        for name in [item for item in untracked.stdout.split("\0") if item]:
            path = self.work_dir / name
            try:
                content = path.read_bytes().decode("utf-8", errors="replace")
            except OSError:
                content = ""
            parts.append(f"追跡していないファイル: {name}\n{content.rstrip(chr(10))}")
        return "\n".join(parts) + ("\n" if parts else "")

    def discard_uncommitted(self) -> None:
        """作業ツリーと索引を最後のコミットの状態に戻し、追跡していないファイルを消す（`.gitignore` で外したものは残す）。"""
        if self.has_head():
            if self._run("reset", "-q", "--hard", "HEAD").returncode != 0:
                raise GitError("作業ツリーを最後のコミットの状態に戻せなかった")
        if self._run("clean", "-f", "-d", "-q", "--", ".").returncode != 0:
            raise GitError("追跡していないファイルを消せなかった")

"""書き込みの記録。書き込みの操作が変えた正本のファイルを、書き込み 1 件につき 1 件の git のコミットにする。

正本のファイルは、人も AI のセッションも直接触らない。accord がコミットしなければ、正本の変更の
履歴が残らない。だから書いた操作の側で、書いたファイルだけをコミットする。accord を通さない変更が
まだコミットされずに残っているファイルには書かない。その変更を accord のコミットに混ぜて、
accord が書いたものとして履歴にしないためである。

コミットの説明には、操作の名前を示す行（`Accord-Operation: <操作の名前>`）を書く。accord が書いた
コミットと、accord を通さないコミットを、履歴から見分ける印である。置き場は起動のときに git の
作業ツリーの根であることを確かめてあるので、記録はいつも行う。
"""
from __future__ import annotations

from accord.models.results import NextAction, Rejection
from accord.repository.git_commits import GitCommits, GitError
from accord.vocabulary.settings import Settings

# 断りに名乗る名前。型の正本の制約ではなく、書き込みの記録が持つ決まりである。
UNCOMMITTED_CHANGE = "書く前の未コミットの変更"

# コミットの文の書き出し。
COMMIT_PREFIX = "accord"

# コミットの説明に置く、操作の名前を示す行の書き出し。accord のコミットの印になる。
OPERATION_TRAILER = "Accord-Operation"


class WriteRecorder:
    """書き込みの操作の前後で、書くファイルの git の状態を見てコミットする。"""

    def __init__(self, settings: Settings, git: GitCommits | None = None) -> None:
        self.settings = settings
        self._git = git

    @property
    def enabled(self) -> bool:
        """書き込みの記録が有効か。置き場はいつも git の作業ツリーの根なので、いつも有効。"""
        # spec: REQ-513
        return True

    def git(self) -> GitCommits:
        if self._git is None:
            self._git = GitCommits(self.settings.source_dir)
        return self._git

    def refusal(self, file_name: str, operation: str) -> Rejection | None:
        """書く前のファイルに未コミットの変更があれば、書かない理由を返す。無ければ None。"""
        path = self.settings.source_dir / file_name
        try:
            dirty = self.git().has_uncommitted_change(path)
        except GitError as error:
            # spec: REQ-500
            return Rejection(
                constraint=UNCOMMITTED_CHANGE,
                reason=f"{file_name} の git の状態を読めなかったので書かなかった（{error}）。",
                next_action=NextAction(
                    operation=operation,
                    example="git の状態を読めなかったことを依頼した人に伝え、もう一度呼ぶ。",
                ),
            )
        # spec: REQ-405
        if not dirty:
            return None
        # spec: REQ-500
        return Rejection(
            constraint=UNCOMMITTED_CHANGE,
            reason=(
                f"{file_name} に accord を通さない変更（まだコミットされていない変更）があるので、"
                "書かなかった。accord はその変更を自分のコミットに混ぜない。"
            ),
            next_action=NextAction(
                operation=operation,
                example=f"{file_name} に accord を通さない変更があることを、依頼した人に伝える。",
            ),
        )

    def record(self, file_name: str, operation: str, summary: str) -> list[str]:
        """書いたファイルだけを 1 件のコミットにし、知らせの行を返す。"""
        path = self.settings.source_dir / file_name
        # spec: REQ-513
        message = (
            f"{COMMIT_PREFIX}: {operation} {file_name}（{summary}）\n\n"
            f"{OPERATION_TRAILER}: {operation}"
        )
        try:
            commit = self.git().commit_file(path, message)
        except GitError as error:
            return [
                f"{file_name} に書いたが、git へのコミットが通らなかった（{error}）。"
                "この書き込みは履歴に残っていない。"
                "このことを依頼した人に伝える。"
            ]
        if not commit:
            return []
        return [f"{file_name} の変更を git にコミットした（{commit}）。"]

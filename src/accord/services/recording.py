"""書き込みの記録。設定で有効にしたとき、書き込みの操作が変えた正本のファイルを git にコミットする。

AI のセッションにデータの置き場を知らせない構成では、セッションは自分ではコミットできない。
accord がコミットしなければ、正本の変更の履歴が残らない。だから書いた操作の側で、書いたファイル
だけをコミットする。人の手の変更がまだコミットされていないファイルには書かない。その人の許可なしに、
人の手の変更を accord のコミットに混ぜて履歴にしないためである。

有効でないときは、git を 1 度も呼ばない。
"""

from __future__ import annotations

from accord.models.results import NextAction, Rejection
from accord.repository.git_commits import GitCommits, GitError
from accord.vocabulary.settings import COMMIT_WRITES_KEY, Settings

# 断りに名乗る名前。型の正本の制約ではなく、書き込みの記録の設定が持つ決まりである。
UNCOMMITTED_CHANGE = "書く前の未コミットの変更"

# コミットの文の書き出し。
COMMIT_PREFIX = "accord"


class WriteRecorder:
    """書き込みの操作の前後で、書くファイルの git の状態を見てコミットする。"""

    def __init__(self, settings: Settings, git: GitCommits | None = None) -> None:
        self.settings = settings
        self._git = git

    @property
    def enabled(self) -> bool:
        """書き込みの記録が有効か。"""
        return self.settings.commit_writes

    def git(self) -> GitCommits:
        if self._git is None:
            self._git = GitCommits(self.settings.source_dir)
        return self._git

    def refusal(self, file_name: str, operation: str) -> Rejection | None:
        """書く前のファイルに未コミットの変更があれば、書かない理由を返す。無ければ None。"""
        # spec: REQ-404
        if not self.enabled:
            return None
        path = self.settings.source_dir / file_name
        try:
            dirty = self.git().has_uncommitted_change(path)
        except GitError as error:
            return Rejection(
                constraint=UNCOMMITTED_CHANGE,
                reason=f"{file_name} の git の状態を読めなかったので書かなかった（{error}）。",
                next_action=NextAction(
                    operation=operation,
                    example="データの置き場の git の状態を確かめてから、もう一度呼ぶ。",
                ),
            )
        # spec: REQ-405
        if not dirty:
            return None
        return Rejection(
            constraint=UNCOMMITTED_CHANGE,
            reason=(
                f"{file_name} に、まだコミットしていない人の手の変更がある。"
                "accord はその変更を自分のコミットに混ぜないため、書かなかった。"
                f"先にその変更をコミットしてから、もう一度 {operation} を呼ぶ。"
            ),
            next_action=NextAction(
                operation=operation,
                example=f"データの置き場で {file_name} の変更をコミットしてから、同じ引数で呼び直す。",
            ),
        )

    def record(self, file_name: str, operation: str, summary: str) -> list[str]:
        """書いたファイルだけをコミットし、知らせの行を返す。無効なら何もしない。"""
        # spec: REQ-404
        if not self.enabled:
            return []
        path = self.settings.source_dir / file_name
        message = f"{COMMIT_PREFIX}: {operation} {file_name}（{summary}）"
        try:
            # spec: REQ-403
            commit = self.git().commit_file(path, message)
        except GitError as error:
            return [
                f"{file_name} に書いたが、git へのコミットが通らなかった（{error}）。"
                f"設定 {COMMIT_WRITES_KEY} が有効なので、データの置き場でこのファイルをコミットする。"
            ]
        if not commit:
            return []
        return [f"{file_name} の変更を git にコミットした（{commit}）。"]

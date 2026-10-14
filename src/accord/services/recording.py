"""書き込みの記録。書き込みの操作が変えた正本のファイルを、書き込み 1 件につき 1 件の git のコミットにする。

正本のファイルは、人も AI のセッションも直接触らない。accord がコミットしなければ、正本の変更の
履歴が残らない。だから書いた操作の側で、書いたファイルだけをコミットする。accord を通さない変更が
まだコミットされずに残っているファイルには書かない。その変更を accord のコミットに混ぜて、
accord が書いたものとして履歴にしないためである。

コミットの説明には、操作の名前を示す行（`Accord-Operation: <操作の名前>`）を書く。accord が書いた
コミットと、accord を通さないコミットを、履歴から見分ける印である。置き場は起動のときに git の
作業ツリーの根であることを確かめてあるので、記録はいつも行う。

移行の前の置き場（設定ファイル accord.toml があり、語彙のファイル vocabulary.md が無い置き場）では、
移行の操作のほかの操作を断り、移行の操作を指す。移行の操作は、設定ファイルの置き場の節と読み方の節が
accord の形と同じことを確かめてから、語彙の節から vocabulary.md を作り、accord.toml を消し、
その 2 つを 1 件のコミットにする。
"""
from __future__ import annotations

from accord.models.results import NextAction, Rejection, WriteResult
from accord.repository.git_commits import GitCommits, GitError
from accord.repository.markdown_repository import MarkdownRepository
from accord.vocabulary.settings import (
    LEGACY_CONFIG_FILE,
    LEGACY_PACKAGE_SKIP_KEY,
    VOCABULARY_FILE,
    Settings,
    SettingsError,
    legacy_form_differences,
    legacy_vocabulary,
    read_legacy_config,
)

# 断りに名乗る名前。型の正本の制約ではなく、書き込みの記録が持つ決まりである。
UNCOMMITTED_CHANGE = "書く前の未コミットの変更"
PRE_MIGRATION = "移行していない置き場"
ALREADY_MIGRATED = "移行済みの置き場"
FORM_DIFFERENCE = "accord の形との違い"

# 操作の名前。次の一手とコミットの印にそのまま載せる。
MIGRATE_OPERATION = "migrate_data"
LIST_OPERATION = "list_sections"

# コミットの文の書き出し。
COMMIT_PREFIX = "accord"

# コミットの説明に置く、操作の名前を示す行の書き出し。accord のコミットの印になる。
OPERATION_TRAILER = "Accord-Operation"


def commit_message(operation: str, subject: str, summary: str) -> str:
    """コミットの説明。1 行目に操作と要約、空行の後に操作の名前を示す行を置く。"""
    return f"{COMMIT_PREFIX}: {operation} {subject}（{summary}）\n\n{OPERATION_TRAILER}: {operation}"


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

    def migration_refusal(self, operation: str) -> Rejection | None:
        """置き場が移行の前なら、移行の操作を指す断りを返す。移行の後なら None。"""
        # spec: REQ-522
        if not self.settings.needs_migration:
            return None
        return Rejection(
            constraint=PRE_MIGRATION,
            reason=(
                f"置き場が移行の前（{LEGACY_CONFIG_FILE} があり {VOCABULARY_FILE} が無い）なので、"
                f"{operation} を行わなかった。先に移行の操作で、置き場を accord の形にする。"
            ),
            next_action=NextAction(
                operation=MIGRATE_OPERATION,
                example=f"{MIGRATE_OPERATION} を引数なしで呼ぶ。",
            ),
        )

    def refusal(self, file_name: str, operation: str) -> Rejection | None:
        """書く前の置き場が移行の前か、書くファイルに未コミットの変更があれば、書かない理由を返す。無ければ None。"""
        return self.migration_refusal(operation) or self.uncommitted_refusal(file_name, operation)

    def uncommitted_refusal(self, file_name: str, operation: str) -> Rejection | None:
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
        message = commit_message(operation, file_name, summary)
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

    def record_paths(
        self, added: list[str], removed: list[str], operation: str, subject: str, summary: str
    ) -> tuple[str, list[str]]:
        """足したファイルと消したファイルを 1 件のコミットにし、短い識別子と知らせの行を返す。

        コミットが通らなければ GitError をそのまま上げる。呼ぶ側（移行の操作）は置き場を元に戻さず、
        書いたものを残して警告を付けて返す（ほかの書き込みの前例と同じ。ステージした 2 ファイルは残る）。
        """
        root = self.settings.source_dir
        # spec: REQ-513
        commit = self.git().commit_paths(
            [root / name for name in added],
            [root / name for name in removed],
            commit_message(operation, subject, summary),
        )
        return commit, [f"{'・'.join([*added, *removed])} の変更を git にコミットした（{commit}）。"]


class MigrationService:
    """移行の操作。移行の前の置き場（設定ファイルがあり語彙のファイルが無い）を、accord の形の置き場にする。"""

    def __init__(self, settings: Settings, recorder: WriteRecorder | None = None) -> None:
        self.settings = settings
        self.recorder = recorder or WriteRecorder(settings)
        self.repository = MarkdownRepository(settings)

    @staticmethod
    def _refused(constraint: str, reason: str, operation: str, candidates: list[str] | None = None, example: str = "") -> WriteResult:
        return WriteResult(
            accepted=False,
            rejection=Rejection(
                constraint=constraint,
                reason=reason,
                next_action=NextAction(
                    operation=operation, candidates=list(candidates or []), example=example
                ),
            ),
        )

    def migrate_data(self) -> WriteResult:
        """accord.toml の語彙の節から vocabulary.md を作り、accord.toml を消し、1 件のコミットにする。"""
        config = self.settings.source_dir / LEGACY_CONFIG_FILE
        # spec: REQ-544
        if not self.settings.needs_migration or not config.is_file():
            return self._refused(
                ALREADY_MIGRATED,
                f"置き場は移行済み（{VOCABULARY_FILE} がある）なので、移行しなかった。",
                LIST_OPERATION,
                example="移行の後は、ほかの操作をそのまま呼べる。",
            )
        try:
            document = read_legacy_config(config)
        except SettingsError as error:
            return self._refused(
                FORM_DIFFERENCE,
                f"{error}。accord の形と同じかを確かめられないので、移行しなかった。",
                MIGRATE_OPERATION,
                example=f"{LEGACY_CONFIG_FILE} を読めなかったことを、依頼した人に伝える。",
            )
        differences, written_skip = legacy_form_differences(document)
        form_skip = self.repository.form_skipped_headings("packages")
        if written_skip != form_skip:
            differences.append(
                (
                    LEGACY_PACKAGE_SKIP_KEY,
                    "パッケージの型の欄を 1 つも持たない節を読み飛ばす"
                    f"（この置き場でその形が読み飛ばす節は {len(form_skip)} 件で、"
                    f"書かれた見出し {len(written_skip)} 件と並びが合わない）",
                )
            )
        # spec: REQ-524
        if differences:
            return self._refused(
                FORM_DIFFERENCE,
                f"{LEGACY_CONFIG_FILE} の置き場の節か読み方の節が accord の形と違うので、移行しなかった。"
                "違う鍵と、accord の形の値は候補のとおり。",
                MIGRATE_OPERATION,
                candidates=[f"{key}: {value}" for key, value in differences],
                example="違う鍵と accord の形の値を、依頼した人に伝える。",
            )
        # 移行が書く 2 つのファイルに accord を通さない未コミットの変更があれば、書かない。
        for name in (VOCABULARY_FILE, LEGACY_CONFIG_FILE):
            # spec: REQ-405
            refusal = self.recorder.uncommitted_refusal(name, MIGRATE_OPERATION)
            if refusal is not None:
                return WriteResult(accepted=False, rejection=refusal)

        vocabulary = legacy_vocabulary(document)
        # spec: REQ-523
        self.repository.write_vocabulary_file(self.repository.vocabulary_text(vocabulary))
        config.unlink()
        try:
            _, notes = self.recorder.record_paths(
                [VOCABULARY_FILE],
                [LEGACY_CONFIG_FILE],
                MIGRATE_OPERATION,
                f"{LEGACY_CONFIG_FILE} → {VOCABULARY_FILE}",
                f"{LEGACY_CONFIG_FILE} の語彙の節から {VOCABULARY_FILE} を作り、{LEGACY_CONFIG_FILE} を消す",
            )
        except GitError as error:
            # ほかの書き込みの操作と同じく、書いたものは残し、履歴に残っていないことを知らせる。
            notes = [
                f"{VOCABULARY_FILE} を作り {LEGACY_CONFIG_FILE} を消したが、git へのコミットが通らなかった"
                f"（{error}）。この移行は履歴に残っていない。このことを依頼した人に伝える。"
            ]
        self.settings.refresh_vocabulary()
        return WriteResult(
            accepted=True,
            recorded={
                "作ったファイル": VOCABULARY_FILE,
                "消したファイル": LEGACY_CONFIG_FILE,
                "語の数": {kind: len(words) for kind, words in vocabulary.items()},
            },
            warnings=notes,
        )

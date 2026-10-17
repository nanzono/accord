"""書き込みの記録と、accord を通さない変更の検出と、取り消しと語彙の操作と移行の操作。

正本のファイルは、人も AI のセッションも直接触らない。accord がコミットしなければ、正本の変更の
履歴が残らない。だから書いた操作の側で、書いたファイルだけをコミットする。コミットの説明には、
操作の名前を示す行（`Accord-Operation: <操作の名前>`）を書く。accord が書いたコミットと、accord を
通さないコミットを、履歴から見分ける印である。置き場は起動のときに git の作業ツリーの根であることを
確かめてあるので、記録はいつも行う。

書く前に、置き場の中のどれかのファイルに未コミットの変更があれば書かない（その変更を accord の
コミットに混ぜて、accord が書いたものとして履歴にしないため）。移行のコミットより後に、操作の名前を
示す行を持たないコミット（accord 以外のコミット）があっても書かない。移行のコミットは、
`Accord-Operation: migrate_data` の行を持つ最古のコミットで、無ければ根のコミットを起点にする。
accord の打ち消しのコミットが `Accord-Reverts: <長い識別子>` の行で名指ししたコミットは、
accord 以外のコミットに数えない。どちらの断りも、次の一手は git を直接叩くことではなく、未コミットの
変更を捨てる操作（discard_uncommitted）か、コミットを取り消す操作（revert_commit）を指す。

取り消しの 2 つの操作は、accord 以外のコミットがあっても呼べる（それを片づけるための操作だから）。
コミットを取り消す操作は、移行のコミットより後のコミット 1 件を打ち消すコミットを作り、後のコミットと
ぶつかるときと、打ち消した後に新しい違反が出るときは、置き場をそのままに戻して断る。未コミットの変更を
捨てる操作は、捨てる前の差分を返してから、作業ツリーを最後のコミットの状態に戻す。

語彙の操作は、vocabulary.md の種類の節に語を 1 行足すか、語の行を消す。使われている語は消さない。
媒体の語は、提示物の置き場に同じ名前のディレクトリがあるときも、使われている語として消さない。

移行の前の置き場（設定ファイル accord.toml があり、語彙のファイル vocabulary.md が無い置き場）では、
移行の操作のほかの操作を断り、移行の操作を指す。移行の操作は、設定ファイルの置き場の節と読み方の節が
accord の形と同じことを確かめてから、語彙の節から vocabulary.md を作り、accord.toml を消し、
その 2 つを 1 件のコミットにする。移行の操作は accord 以外のコミットでは断らず、未コミットの変更は
書く 2 つのファイルだけで見る。
"""
from __future__ import annotations

import re

from accord.models.constraints import CONSTRAINTS
from accord.models.results import NextAction, Rejection, Violation, WriteResult
from accord.repository.git_commits import CommitEntry, GitCommits, GitError
from accord.repository.markdown_repository import MarkdownRepository
from accord.vocabulary.settings import (
    CHANNELS_KIND,
    LEGACY_CONFIG_FILE,
    LEGACY_PACKAGE_SKIP_KEY,
    VOCABULARY_FILE,
    VOCABULARY_KINDS,
    Settings,
    SettingsError,
    legacy_form_differences,
    legacy_vocabulary,
    read_legacy_config,
)

# 断りに名乗る名前。型の正本の制約ではなく、書き込みの記録が持つ決まりである。
UNCOMMITTED_CHANGE = "書く前の未コミットの変更"
FOREIGN_COMMIT = "accord 以外のコミット"
PRE_MIGRATION = "移行していない置き場"
ALREADY_MIGRATED = "移行済みの置き場"
FORM_DIFFERENCE = "accord の形との違い"
REVERT_RANGE = "取り消せるコミットの範囲"
REVERT_CONFLICT = "取り消しのぶつかり"
REASON_REQUIRED = "書き換えの理由"
VOCABULARY_KIND = "語彙の種類"
TERM_FORMAT = "語彙に足す語の書き方"
TERM_MISSING = "語彙に無い語"
TERM_IN_USE = "使われている語は消さない"

# 操作の名前。次の一手とコミットの印にそのまま載せる。
MIGRATE_OPERATION = "migrate_data"
LIST_OPERATION = "list_sections"
REVERT_OPERATION = "revert_commit"
DISCARD_OPERATION = "discard_uncommitted"
ADD_TERM_OPERATION = "add_term"
REMOVE_TERM_OPERATION = "remove_term"
REVISE_OPERATION = "revise_section"

# 欄の名前。欠けた欄の断りに載せる。
REASON_FIELD = "理由"

# コミットの文の書き出し。
COMMIT_PREFIX = "accord"

# コミットの説明に置く、操作の名前を示す行の書き出し。accord のコミットの印になる。
OPERATION_TRAILER = "Accord-Operation"
# accord の打ち消しのコミットの説明に置く、打ち消したコミットの長い識別子を示す行の書き出し。
REVERTS_TRAILER = "Accord-Reverts"

OPERATION_LINE_RE = re.compile(rf"^{OPERATION_TRAILER}:\s*\S+", re.MULTILINE)
MIGRATION_LINE_RE = re.compile(rf"^{OPERATION_TRAILER}:\s*{MIGRATE_OPERATION}\s*$", re.MULTILINE)
REVERTS_LINE_RE = re.compile(rf"^{REVERTS_TRAILER}:\s*([0-9a-f]+)\s*$", re.MULTILINE)

# コミットの識別子として受ける書き方（16 進の 4〜64 字）。
COMMIT_ID_RE = re.compile(r"^[0-9a-fA-F]{4,64}$")

# 知らせと断りに名前を並べる数。残りは件数に畳む。
NAME_SAMPLE_COUNT = 10

# 写しの鮮度。書いた後の守りで断る理由にしない違反。
COPY_FRESHNESS = next(item.name for item in CONSTRAINTS if item.name == "写しの鮮度")


def commit_message(operation: str, subject: str, summary: str, extra: list[str] | None = None) -> str:
    """コミットの説明。1 行目に操作と要約、空行の後に操作の名前を示す行（と添える行）を置く。"""
    lines = [f"{OPERATION_TRAILER}: {operation}", *(extra or [])]
    return f"{COMMIT_PREFIX}: {operation} {subject}（{summary}）\n\n" + "\n".join(lines)


def is_accord_commit(entry: CommitEntry) -> bool:
    """コミットの説明に操作の名前を示す行があるか。"""
    return OPERATION_LINE_RE.search(entry.message) is not None


def reverted_by(entry: CommitEntry) -> list[str]:
    """accord の打ち消しのコミットが名指しした、打ち消したコミットの長い識別子。"""
    if not is_accord_commit(entry):
        return []
    return REVERTS_LINE_RE.findall(entry.message)


def folded(names: list[str]) -> str:
    """名前の並びを 1 つの文にする。多ければ件数に畳む。"""
    shown = "、".join(names[:NAME_SAMPLE_COUNT])
    rest = len(names) - NAME_SAMPLE_COUNT
    return shown + (f" ほか {rest} 件" if rest > 0 else "")


def new_violations(before: list[Violation], after: list[Violation]) -> list[Violation]:
    """書いた後の違反のうち、書く前に無かったものを返す。

    写しの鮮度は、直し先の文（変わった出典と指紋）まで比べる。書いたことで写しが新しく古くなったかを
    見るためである。ほかの違反は、制約・ファイル・場所で比べる。同じ場所の同じ違反の文の言い回しが
    変わっただけで、書き込みを止めないためである。
    """

    def key(item: Violation) -> tuple[str, ...]:
        if item.constraint == COPY_FRESHNESS:
            return (item.constraint, item.file, item.location, item.expected)
        return (item.constraint, item.file, item.location)

    seen = {key(item) for item in before}
    return [item for item in after if key(item) not in seen]


def _refused(
    constraint: str,
    reason: str,
    operation: str,
    candidates: list[str] | None = None,
    example: str = "",
    missing_fields: list[str] | None = None,
) -> WriteResult:
    """書かずに断る返り値を作る。"""
    return WriteResult(
        accepted=False,
        rejection=Rejection(
            constraint=constraint,
            reason=reason,
            next_action=NextAction(
                operation=operation,
                missing_fields=list(missing_fields or []),
                candidates=list(candidates or []),
                example=example,
            ),
        ),
    )


def missing_reason(reason: str, operation: str) -> WriteResult | None:
    """理由が空なら断りを返す。"""
    if str(reason or "").strip():
        return None
    return _refused(
        REASON_REQUIRED,
        f"欄「{REASON_FIELD}」が空なので、書かなかった。",
        operation,
        missing_fields=[REASON_FIELD],
        example="理由は、何をなぜ変えるかの 1 文（例「依頼した人の指示で、直前の書き込みを取り消す」）。",
    )


class WriteRecorder:
    """書き込みの操作の前後で、置き場の git の状態を見てコミットする。"""

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

    # ------------------------------------------------------------ 履歴と作業ツリーを読む

    def uncommitted_files(self) -> list[str]:
        """置き場の中の、未コミットの変更のあるファイルの名前。"""
        return self.git().uncommitted_paths()

    def history(self) -> tuple[list[CommitEntry], list[CommitEntry]]:
        """移行のコミット（無ければ根のコミット）より後のコミットと、それ以前のコミットを、新しい順に返す。"""
        git = self.git()
        every = git.log(["HEAD"])
        if not every:
            return [], []
        # spec: REQ-547
        migration = next(
            (entry for entry in reversed(every) if MIGRATION_LINE_RE.search(entry.message)), None
        )
        bases = [migration.full] if migration is not None else git.root_commits()
        after = git.log(["HEAD", *[f"^{base}" for base in bases]])
        later = {entry.full for entry in after}
        return after, [entry for entry in every if entry.full not in later]

    @staticmethod
    def _reverted(after: list[CommitEntry]) -> dict[str, CommitEntry]:
        """後の accord の打ち消しのコミットが名指ししたコミットの長い識別子から、その打ち消しのコミットへの対応。"""
        named: dict[str, CommitEntry] = {}
        for index, entry in enumerate(after):
            for full in reverted_by(entry):
                for target in after[index + 1 :]:
                    if target.full.startswith(full) and target.full not in named:
                        named[target.full] = entry
        return named

    def foreign_commits(self) -> list[CommitEntry]:
        """移行のコミットより後の、accord 以外のコミット（新しい順）。"""
        after, _ = self.history()
        reverted = self._reverted(after)
        # spec: REQ-515
        # spec: REQ-550
        return [
            entry for entry in after if not is_accord_commit(entry) and entry.full not in reverted
        ]

    # ------------------------------------------------------------ 書く前の断り

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
        """書く前の置き場が移行の前か、未コミットの変更か accord 以外のコミットがあれば、書かない理由を返す。

        file_name は書くファイルの名前で、断りの文には置き場全体の変更のあるファイルを載せる。
        """
        return (
            self.migration_refusal(operation)
            or self.tree_refusal(operation)
            or self.foreign_refusal(operation)
        )

    def git_unreadable(self, operation: str, error: GitError) -> Rejection:
        # spec: REQ-500
        return Rejection(
            constraint=UNCOMMITTED_CHANGE,
            reason=f"置き場の git の状態を読めなかったので書かなかった（{error}）。",
            next_action=NextAction(
                operation=operation,
                example="git の状態を読めなかったことを依頼した人に伝え、もう一度呼ぶ。",
            ),
        )

    def tree_refusal(self, operation: str) -> Rejection | None:
        """置き場の中に未コミットの変更があれば、書かない理由と、捨てる操作を返す。無ければ None。"""
        try:
            changed = self.uncommitted_files()
        except GitError as error:
            return self.git_unreadable(operation, error)
        if not changed:
            return None
        # spec: REQ-514
        # spec: REQ-500
        return Rejection(
            constraint=UNCOMMITTED_CHANGE,
            reason=(
                f"置き場に accord を通さない変更（まだコミットされていない変更）があるので、"
                f"{operation} を行わなかった。変更のあるファイル: {folded(changed)}。"
                "accord はその変更を自分のコミットに混ぜない。依頼した人に確かめてから、"
                f"未コミットの変更を捨てる操作 {DISCARD_OPERATION} で捨て、もう一度呼ぶ。"
            ),
            next_action=NextAction(
                operation=DISCARD_OPERATION,
                candidates=changed,
                example=(
                    f"{DISCARD_OPERATION} に理由を渡して呼ぶ。返る差分に、頼まれた直しが入っていれば、"
                    "捨てた後に accord の操作でやり直す。"
                ),
            ),
        )

    def uncommitted_refusal(self, file_name: str, operation: str) -> Rejection | None:
        """書く前のファイル 1 つに未コミットの変更があれば、書かない理由を返す。無ければ None。

        移行の操作が、書く 2 つのファイルだけを見るために使う。
        """
        path = self.settings.source_dir / file_name
        try:
            dirty = self.git().has_uncommitted_change(path)
        except GitError as error:
            return self.git_unreadable(operation, error)
        # spec: REQ-552
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

    def foreign_refusal(self, operation: str) -> Rejection | None:
        """移行のコミットより後に accord 以外のコミットがあれば、書かない理由と、取り消す操作を返す。"""
        try:
            foreign = self.foreign_commits()
        except GitError as error:
            return self.git_unreadable(operation, error)
        if not foreign:
            return None
        shorts = [entry.short for entry in foreign]
        # spec: REQ-515
        # spec: REQ-500
        return Rejection(
            constraint=FOREIGN_COMMIT,
            reason=(
                f"置き場の履歴に accord 以外のコミット（操作の名前を示す行を持たないコミット）があるので、"
                f"{operation} を行わなかった。accord 以外のコミット: {folded(shorts)}。"
                "依頼した人に確かめてから、コミットを取り消す操作 "
                f"{REVERT_OPERATION} で新しい順に取り消し、もう一度呼ぶ。"
            ),
            next_action=NextAction(
                operation=REVERT_OPERATION,
                candidates=shorts,
                example=f"{REVERT_OPERATION} に候補の短い識別子と理由を渡して呼ぶ。",
            ),
        )

    # ------------------------------------------------------------ 記録する

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


class VocabularyService:
    """語彙の操作。vocabulary.md の種類の節に語を足し、使われていない語を消す。"""

    def __init__(self, settings: Settings, recorder: WriteRecorder | None = None) -> None:
        self.settings = settings
        self.recorder = recorder or WriteRecorder(settings)
        self.repository = MarkdownRepository(settings)

    @staticmethod
    def _kinds() -> list[str]:
        return [kind for kind, _ in VOCABULARY_KINDS]

    def _bad_kind(self, kind: str, operation: str) -> WriteResult | None:
        """渡された種類が 6 つのどれでもなければ断りを返す。"""
        if kind in self._kinds():
            return None
        # spec: REQ-512
        return _refused(
            VOCABULARY_KIND,
            f"語彙の種類「{kind}」は、語彙の 6 つの種類のどれでもないので、書かなかった。",
            operation,
            candidates=self._kinds(),
            example="候補の種類の名前をそのまま kind に渡して、もう一度呼ぶ。",
        )

    def _blocked(self, operation: str) -> WriteResult | None:
        refusal = self.recorder.refusal(VOCABULARY_FILE, operation)
        return WriteResult(accepted=False, rejection=refusal) if refusal is not None else None

    def _written(self, kind: str, term: str, reason: str, text: str, operation: str, summary: str) -> WriteResult:
        self.repository.write_vocabulary_file(text)
        # spec: REQ-513
        notes = self.recorder.record(VOCABULARY_FILE, operation, f"{summary}: {' '.join(reason.split())}")
        self.settings.refresh_vocabulary()
        return WriteResult(
            accepted=True,
            recorded={
                "種類": kind,
                "語": term,
                "理由": reason,
                "語の一覧": self.settings.vocabulary()[kind],
            },
            warnings=notes,
        )

    def add_term(self, kind: str, term: str, reason: str) -> WriteResult:
        """語彙のその種類の節の末尾に、語を 1 行足す。"""
        operation = ADD_TERM_OPERATION
        if (blocked := self.recorder.migration_refusal(operation)) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        if (refused := self._bad_kind(kind, operation)) is not None:
            return refused
        words = self.settings.vocabulary()[kind]
        wanted = str(term or "").strip()
        # spec: REQ-509
        if not wanted or "\n" in str(term) or "\r" in str(term) or wanted in words:
            why = "既にその種類にある" if wanted in words and wanted else (
                "空" if not wanted else "改行を含む"
            )
            return _refused(
                TERM_FORMAT,
                f"足す語が{why}ので、書かなかった。「{kind}」のいまの語は候補のとおり。",
                operation,
                candidates=words,
                example="候補に無い語を、改行を含まない 1 行で term に渡す。",
            )
        if (refused := missing_reason(reason, operation)) is not None:
            return refused
        if (refused := self._blocked(operation)) is not None:
            return refused
        # spec: REQ-508
        text = self.repository.vocabulary_with_term(kind, wanted)
        return self._written(kind, wanted, reason, text, operation, f"{kind} に「{wanted}」を足す")

    def remove_term(self, kind: str, term: str, reason: str) -> WriteResult:
        """語彙のその種類の節から、語の行を消す。正本の節が使っている語は消さない。"""
        operation = REMOVE_TERM_OPERATION
        if (blocked := self.recorder.migration_refusal(operation)) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        if (refused := self._bad_kind(kind, operation)) is not None:
            return refused
        words = self.settings.vocabulary()[kind]
        wanted = str(term or "").strip()
        # spec: REQ-542
        if wanted not in words:
            return _refused(
                TERM_MISSING,
                f"語「{wanted}」は語彙の「{kind}」に無いので、書かなかった。いまの語は候補のとおり。",
                operation,
                candidates=words,
                example="候補の語のどれかをそのまま term に渡す。",
            )
        if (refused := missing_reason(reason, operation)) is not None:
            return refused
        if (refused := self._blocked(operation)) is not None:
            return refused
        users = self.repository.term_users(kind, wanted)
        directory = self.repository.presentation_directory(wanted) if kind == CHANNELS_KIND else None
        # 節での使用と提示物の置き場のディレクトリを両方確かめてから、1 つの断りにまとめる。
        # spec: REQ-511
        if users and directory is not None:
            # spec: REQ-554
            return _refused(
                TERM_IN_USE,
                f"語「{wanted}」は、正本の節が「{kind}」の語として使っているうえ、提示物の置き場に同じ名前の"
                f"ディレクトリ「{directory}」があり、そこの提示物の宛先の媒体としても使われているので、消さなかった。"
                f"使っている節: {folded(users)}。",
                REVISE_OPERATION,
                candidates=[*users, directory],
                example=(
                    f"{REVISE_OPERATION} で候補の節を読み直して書き換え、提示物の置き場からディレクトリ「{directory}」を"
                    f"無くしたことを依頼した人に確かめてから、もう一度 {operation} を呼ぶ。"
                ),
            )
        if users:
            return _refused(
                TERM_IN_USE,
                f"語「{wanted}」は、正本の節が「{kind}」の語として使っているので、消さなかった。"
                f"使っている節: {folded(users)}。語を直すときは、新しい語を足し、"
                f"使っている節を {REVISE_OPERATION} で直してから、この語を消す。",
                REVISE_OPERATION,
                candidates=users,
                example=f"{REVISE_OPERATION} で候補の節を読み直して書き換え、もう一度 {operation} を呼ぶ。",
            )
        # spec: REQ-554
        if directory is not None:
            return _refused(
                TERM_IN_USE,
                f"語「{wanted}」は、提示物の置き場に同じ名前のディレクトリ「{directory}」があり、"
                f"そこの提示物の宛先の媒体として使われているので、消さなかった。",
                operation,
                candidates=[directory],
                example=(
                    f"提示物の置き場からディレクトリ「{directory}」を無くしたことを依頼した人に確かめてから、"
                    f"もう一度 {operation} を呼ぶ。"
                ),
            )
        # spec: REQ-510
        text = self.repository.vocabulary_without_term(kind, wanted)
        return self._written(kind, wanted, reason, text, operation, f"{kind} から「{wanted}」を消す")


class HistoryService:
    """取り消しの 2 つの操作。コミット 1 件を打ち消すことと、未コミットの変更を捨てること。"""

    def __init__(self, settings: Settings, recorder: WriteRecorder | None = None) -> None:
        self.settings = settings
        self.recorder = recorder or WriteRecorder(settings)

    def _inspect(self) -> list[Violation]:
        # 整合の検査は決めと材料のサービスを読み込むので、輪にならないよう関数の中で読み込む。
        from accord.services.consistency import ConsistencyService

        return ConsistencyService(self.settings).inspect(None).violations

    def revert_commit(self, commit: str, reason: str) -> WriteResult:
        """移行のコミットより後のコミット 1 件の変更を打ち消すコミットを 1 件作る。"""
        operation = REVERT_OPERATION
        if (blocked := self.recorder.migration_refusal(operation)) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        git = self.recorder.git()
        try:
            after, before_base = self.recorder.history()
        except GitError as error:
            return WriteResult(accepted=False, rejection=self.recorder.git_unreadable(operation, error))
        reverted = WriteRecorder._reverted(after)
        revertible = [
            entry.short for entry in after if not entry.is_merge and entry.full not in reverted
        ]
        wanted = str(commit or "").strip()
        full = git.resolve(wanted) if COMMIT_ID_RE.match(wanted) else None
        known = {entry.full: entry for entry in after}
        earlier = {entry.full for entry in before_base}

        def out_of_range(why: str) -> WriteResult:
            return _refused(
                REVERT_RANGE,
                f"コミット「{wanted}」は{why}ので、取り消さなかった。取り消せるコミットは候補のとおり（新しい順）。",
                operation,
                candidates=revertible,
                example="候補の短い識別子のどれかと理由を渡して呼ぶ。",
            )

        if full is not None and full in earlier:
            # spec: REQ-518
            return out_of_range("移行のコミットそのものか、それより前のコミット（取り消す範囲の外）な")
        if full is None or full not in known:
            # spec: REQ-543
            return out_of_range("置き場の履歴に無い")
        target = known[full]
        if target.is_merge:
            # spec: REQ-543
            return out_of_range("合流のコミット（親が 2 つ以上）な")
        if full in reverted:
            # spec: REQ-553
            return out_of_range(f"後の打ち消しのコミット {reverted[full].short} が既に打ち消している")
        if (refused := missing_reason(reason, operation)) is not None:
            return refused
        if (refusal := self.recorder.tree_refusal(operation)) is not None:
            return WriteResult(accepted=False, rejection=refusal)

        violations_before = self._inspect()
        try:
            conflicted = git.revert_without_commit(full)
        except GitError as error:
            git.abort_revert()
            return WriteResult(accepted=False, rejection=self.recorder.git_unreadable(operation, error))
        if conflicted:
            index = next(i for i, entry in enumerate(after) if entry.full == full)
            later = [entry.short for entry in after[:index]]
            # spec: REQ-519
            return _refused(
                REVERT_CONFLICT,
                f"コミット「{target.short}」の打ち消しが、後のコミットの変更とぶつかるので、取り消さなかった"
                f"（置き場はそのまま）。ぶつかるファイル: {folded(conflicted)}。"
                "後のコミットから順に（新しい順に）取り消してから、もう一度呼ぶ。",
                operation,
                candidates=later,
                example="候補の短い識別子を新しい順に 1 件ずつ取り消す。",
            )
        self.settings.refresh_vocabulary()
        appeared = new_violations(violations_before, self._inspect())
        blocking = [item for item in appeared if item.constraint != COPY_FRESHNESS]
        if blocking:
            git.abort_revert()
            self.settings.refresh_vocabulary()
            # spec: REQ-520
            return _refused(
                blocking[0].constraint,
                f"コミット「{target.short}」を打ち消した後の正本に、取り消す前に無かった整合の検査の違反が出るので、"
                "取り消さなかった（置き場はそのまま）。"
                + " / ".join(item.as_note() for item in blocking),
                operation,
                candidates=[],
                example="違反の元になる後のコミットを先に取り消すか、違反が出ないことを確かめてから、もう一度呼ぶ。",
            )
        files: list[str] = []
        try:
            files = git.staged_paths()
            subject = target.short
            message = commit_message(
                operation,
                subject,
                f"{target.short} を打ち消す: {' '.join(reason.split())}",
                extra=[f"{REVERTS_TRAILER}: {target.full}"],
            )
            # spec: REQ-517
            # spec: REQ-513
            revert = git.commit_staged(message)
            notes = [f"{target.short} を打ち消す変更を git にコミットした（{revert}）。"]
        except GitError as error:
            revert = ""
            notes = [
                f"{target.short} を打ち消す変更を置き場に作ったが、git へのコミットが通らなかった（{error}）。"
                "この取り消しは履歴に残っていない。このことを依頼した人に伝える。"
            ]
        stale = [item for item in appeared if item.constraint == COPY_FRESHNESS]
        return WriteResult(
            accepted=True,
            recorded={
                "取り消したコミット": target.short,
                "打ち消しのコミット": revert,
                "ファイル": files,
                "理由": reason,
            },
            warnings=[item.as_note() for item in stale] + notes,
        )

    def discard_uncommitted(self, reason: str) -> WriteResult:
        """捨てる前の差分を返り値に載せ、置き場の作業ツリーを最後のコミットの状態に戻す。"""
        operation = DISCARD_OPERATION
        if (blocked := self.recorder.migration_refusal(operation)) is not None:
            return WriteResult(accepted=False, rejection=blocked)
        if (refused := missing_reason(reason, operation)) is not None:
            return refused
        git = self.recorder.git()
        try:
            files = self.recorder.uncommitted_files()
            if not files:
                # spec: REQ-548
                return WriteResult(
                    accepted=True,
                    recorded={"差分": "", "ファイル": [], "理由": reason},
                    warnings=["捨てる変更は無かった。置き場は最後のコミットの状態のまま。"],
                )
            # spec: REQ-521
            diff = git.uncommitted_diff()
            git.discard_uncommitted()
        except GitError as error:
            return WriteResult(accepted=False, rejection=self.recorder.git_unreadable(operation, error))
        self.settings.refresh_vocabulary()
        return WriteResult(
            accepted=True,
            recorded={"差分": diff, "ファイル": files, "理由": reason},
            warnings=[
                f"未コミットの変更を捨て、作業ツリーを最後のコミット（{git.head_short()}）の状態に戻した。"
                "頼まれた直しが差分に入っていれば、accord の操作でやり直す。"
            ],
        )


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
        # ほかのファイルの変更と accord 以外のコミットは見ない（移行の後に、捨てる操作と取り消す操作で片づける）。
        # spec: REQ-551
        for name in (VOCABULARY_FILE, LEGACY_CONFIG_FILE):
            # spec: REQ-552
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

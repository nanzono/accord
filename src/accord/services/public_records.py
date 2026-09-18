"""公開記録を登記する操作。制約を執行し、拒否のときは次の一手を組み立てる。

公開記録は、リポジトリ・登壇・記事・書籍・第三者の掲載のように、本人の申告ではなく外から
確かめられる成果物 1 件である。提示物の本文に貼った URL が正本のどこにも無い、という食い違いを
止めるために、URL を持つ事実として正本に置く。

この文書は保管の仕方も通信の仕方も知らない。正本の読み書きはリポジトリに頼み、
判断に使う語彙（種類と役割の語）は設定から受け取る。
"""

from __future__ import annotations

from accord.models.constraints import CONSTRAINTS
from accord.models.ontology import field_example, missing_required_fields
from accord.models.results import (
    NextAction,
    PublicRecordDraft,
    Rejection,
    SourceSnapshot,
    WriteResult,
    close_names,
)
from accord.models.types import PublicRecord
from accord.repository.markdown_repository import EMPTY_WORDS, MarkdownRepository
from accord.vocabulary.settings import (
    PUBLIC_RECORD_KINDS_KEY,
    PUBLIC_RECORD_ROLES_KEY,
    PUBLIC_RECORDS_KEY,
    Settings,
)

# 制約は名前で参照する。名前を正本（ontology.yaml）で変えたら、ここで鍵が見つからず落ちる。
CONSTRAINT_BY_NAME = {constraint.name: constraint for constraint in CONSTRAINTS}
PUBLIC_RECORD_REQUIRED_FIELDS = CONSTRAINT_BY_NAME["公開記録の必須欄"].name
PUBLIC_RECORD_VOCABULARY = CONSTRAINT_BY_NAME["公開記録の種類と役割の語彙"].name
ORIGIN_SECTION_EXISTS = CONSTRAINT_BY_NAME["由来の節の実在"].name

# 次の 1 つは制約 11 つではなく、設定に置き場が書かれているかどうかである。
# 公開記録の置き場は書かなくてよい鍵なので、書いていない正本では登記そのものが成り立たない。
PUBLIC_RECORDS_FILE_SETTING = "公開記録の置き場の設定"

# 入力の欄を引くときの、型の名前。
PUBLIC_RECORD_TYPE_NAME = "PublicRecord"

# 操作の名前。次の一手にそのまま載せる。
REGISTER_OPERATION = "register_public_record"


class PublicRecordService:
    """公開記録を登記する。制約を先に全部見て、通ると決まってから 1 度だけ書き戻す。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)

    def register(self, draft: PublicRecordDraft) -> WriteResult:
        """公開記録を 1 ブロック足す。置き場・必須欄・語彙・由来の節を確かめ、通らなければ書かずに拒否する。"""
        rejection = self._rejection(draft)
        if rejection is not None:
            return WriteResult(accepted=False, rejection=rejection)

        record = PublicRecord(
            name=str(draft.name),
            kind=str(draft.kind),
            published_on=str(draft.published_on),
            url=_value(draft.url),
            publisher=str(draft.publisher),
            role=str(draft.role),
            origin_section=_value(draft.origin_section),
            source=_value(draft.source),
        )
        self.repository.append_public_record(record)

        return WriteResult(accepted=True, recorded={"公開記録": record.model_dump(mode="json")})

    # ------------------------------------------------------------ 登記の部品

    def _rejection(self, draft: PublicRecordDraft) -> Rejection | None:
        """入力を制約に当てる。通れば None を返し、通らなければ次の一手つきの拒否を返す。

        見る順は、置き場が設定にあるか、必須の欄、種類の語彙、役割の語彙、由来の節の実在である。
        1 つ目に当たった時点で返すので、正本は 1 バイトも変わらない。
        """
        if not self.settings.has_file(PUBLIC_RECORDS_KEY):
            return self._missing_file_rejection()

        missing = missing_required_fields(PUBLIC_RECORD_TYPE_NAME, draft)
        if missing:
            return Rejection(
                constraint=PUBLIC_RECORD_REQUIRED_FIELDS,
                reason=(
                    "公開記録の必須の欄"
                    + "、".join(f"「{field.label}」" for field in missing)
                    + "が無い。名前と種類と日付と発行元か主催と役割がそろって初めて、"
                    "外から確かめられる 1 件になる。"
                ),
                next_action=NextAction(
                    operation=REGISTER_OPERATION,
                    missing_fields=[field.label for field in missing],
                    example="\n".join(field_example(field) for field in missing),
                ),
            )

        vocabulary = self._vocabulary_rejection(draft)
        if vocabulary is not None:
            return vocabulary

        return self._origin_section_rejection(draft)

    def _missing_file_rejection(self) -> Rejection:
        """公開記録の置き場が設定に無いときの拒否。足す鍵 3 つを名前で返す。"""
        return Rejection(
            constraint=PUBLIC_RECORDS_FILE_SETTING,
            reason=(
                f"設定ファイル {self.settings.config_path.name} に公開記録の置き場が無いので、"
                "書き足す先が決まらない。この正本は公開記録を使わない正本として動いている。"
            ),
            next_action=NextAction(
                operation=REGISTER_OPERATION,
                example=(
                    f"設定の [source.files] に {PUBLIC_RECORDS_KEY} = "
                    '"public_records.md" を足し、[vocabulary] に '
                    f"{PUBLIC_RECORD_KINDS_KEY} と {PUBLIC_RECORD_ROLES_KEY} を"
                    "（それぞれ 1 語以上の一覧で）足してから、もう一度この操作を呼ぶ。"
                ),
            ),
        )

    def _vocabulary_rejection(self, draft: PublicRecordDraft) -> Rejection | None:
        """種類と役割が、設定の語の一覧にあるかを見る。種類を先に見る。"""
        for label, value, words, key in (
            ("種類", draft.kind, self.settings.public_record_kinds, PUBLIC_RECORD_KINDS_KEY),
            ("役割", draft.role, self.settings.public_record_roles, PUBLIC_RECORD_ROLES_KEY),
        ):
            if value in words:
                continue
            return Rejection(
                constraint=PUBLIC_RECORD_VOCABULARY,
                reason=(
                    f"{label}「{value}」は、設定ファイル {self.settings.config_path.name} の "
                    f"{key} が持つ語の一覧に無い。"
                ),
                next_action=NextAction(
                    operation=REGISTER_OPERATION,
                    candidates=list(words),
                    example=(
                        f"{label}には「{words[0]}」のように、上の候補のどれかをそのまま渡す。"
                        if words
                        else f"設定の [vocabulary] の {key} に、渡したい語を足してから呼び直す。"
                    ),
                ),
            )
        return None

    def _origin_section_rejection(self, draft: PublicRecordDraft) -> Rejection | None:
        """由来の節が、職歴の枠か受託案件の見出しとして実在するかを見る。空なら見ない。"""
        origin = _value(draft.origin_section)
        if origin is None:
            return None

        snapshot: SourceSnapshot = self.repository.load()
        headings = snapshot.section_headings()
        if origin in headings:
            return None

        return Rejection(
            constraint=ORIGIN_SECTION_EXISTS,
            reason=f"由来の節「{origin}」は、職歴の枠にも受託案件にも無い見出しである。",
            next_action=NextAction(
                operation=REGISTER_OPERATION,
                candidates=close_names(origin, headings),
                example=(
                    f"上の候補をそのまま由来の節に渡して、もう一度 {REGISTER_OPERATION} を呼ぶ。"
                    "元になった仕事が正本に無いなら、由来の節は空のままでよい。"
                ),
            ),
        )


def _value(text: str | None) -> str | None:
    """入力の任意の欄を、値か「持たない」にそろえる。空を表す語（「なし」など）も持たないとして読む。"""
    if text is None or text.strip() in EMPTY_WORDS:
        return None
    return text.strip()

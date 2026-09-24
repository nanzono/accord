"""正本どうしの結びを ID で行うことの受け入れ条件のテスト。

見るのは 5 つ。指された値が読めないときの言い分けを 4 つの指し方（機能の裏づけの節・
公開記録の由来の節・職務経歴書の台帳の出典の節・提示物の未反映の注記が指す節）ごとに確かめること、
正本全体での ID の形式と ID の一意性、見出しを書き換えても参照が切れないこと、材料の本文から ID の行が
落ちること、そして書きの操作が ID を書き込みの瞬間に断ることである。型の正本が 5 つの型に必須の
ID の欄を持つことは、型の正本の欄の定義なので tests/test_ontology.py が見る。

指された値が読めないときの言い分けは、指し方が 4 つあっても同じ約束が成り立つ。だから 4 つとも、
読めたとき・ID の形に合わないとき・照らす相手が 1 件も読めていないときの 3 通りを同じ形で確かめる。
書きの操作の ID の断りも、3 つの操作（機能の登記・パッケージの改訂・公開記録の登記）で同じなので、
1 つの表を場合分けで回す。その表が 3 つの操作を覆っていることは、型の正本が挙げる執行の一覧と
突き合わせて機械で見る。

違反はすべて、同梱のサンプルの一時的な写しに仕込む。リポジトリのサンプルそのものは整ったままにする。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from accord.models.constraints import CONSTRAINTS
from accord.models.results import (
    ID_FORMAT_TEXT,
    CapabilityDraft,
    MaterialRequest,
    PackageDraft,
    PublicRecordDraft,
    Rejection,
    WriteResult,
    is_id,
)
from accord.repository.markdown_repository import MarkdownRepository
from accord.services.consistency import ConsistencyService
from accord.services.material import MaterialService
from accord.services.offering import OfferingService
from accord.services.public_records import PublicRecordService
from accord.vocabulary.settings import Settings, load_settings
from conftest import source_digest

EVIDENCE_SECTION_EXISTS = "裏づけ節名の実在"
ID_FORMAT = "ID の形式"
ID_UNIQUENESS = "ID の一意性"
ORIGIN_SECTION_EXISTS = "由来の節の実在"

# 整合の検査の操作の名前。ID の形式と ID の一意性を執行する 4 つのうち、書きの操作でないのはこれだけ。
INSPECT_OPERATION = "check_consistency"

# 同梱のサンプルにある ID と、その表示名。
ENGAGEMENT_ID = "teramina-delivery"
ENGAGEMENT_HEADING = "テラミナ物流 配送データの置き場づくり"
CAREER_ID = "freelance-solo"
CAREER_HEADING = "2021-04〜現在 フリーランス"
PUBLISHING_ID = "nagisa-publishing"
PUBLISHING_HEADING = "ナギサ書房 刊行計画の進行管理"
HEADLINE_PACKAGE_ID = "requirements-and-progress"
HEADLINE_PACKAGE_NAME = "要件定義と進行管理"
KNOWN_CAPABILITY_ID = "requirements-forum"

# 職歴の枠の見出しを書き換えるときの、書き換えた後の見出し。
NEW_CAREER_HEADING = "2021-04〜 個人で受ける"

# ID の行を消す節と、その節にしか無い言い回し。落ちたことを本文の側でも確かめる。
CAREER_WITHOUT_ID = "agency-employee"
CAREER_WITHOUT_ID_MARK = "社内の集計基盤"

# 裏づけの 1 行を、区切りを取り違えた形に書き換える。全角の中黒は区切りとして読まれない。
WRONG_SEPARATOR = (
    "| teramina-delivery / yukinoha-quality |",
    "| teramina-delivery・yukinoha-quality |",
)

# 裏づけの 1 行を、形は合うが実在しない ID に書き換える。
DANGLING_ID = ("| nagisa-publishing |", "| nagisa-publishng |")

# 由来の節・出典の節・注記の指す先を、見出しをそのまま書いた形に書き換える。ID の形から外れる。
ORIGIN_OUT_OF_FORMAT = (
    f"- 由来の節: {PUBLISHING_ID}",
    f"- 由来の節: {PUBLISHING_HEADING}",
)
LEDGER_OUT_OF_FORMAT = (
    f"- 出典の節: {ENGAGEMENT_ID}",
    f"- 出典の節: {ENGAGEMENT_HEADING}",
)
NOTE_OUT_OF_FORMAT = (
    "- 未反映の注記: なし",
    f"- 未反映の注記: {PUBLISHING_HEADING} — 週 1 回の確認の場を隔週に変えた",
)

# 注記を、実在する ID を指す形と、形は合うが実在しない ID を指す形に書き換える。
READABLE_NOTE = (
    "- 未反映の注記: なし",
    f"- 未反映の注記: {PUBLISHING_ID} — 週 1 回の確認の場を隔週に変えた",
)
DANGLING_NOTE = (
    "- 未反映の注記: なし",
    "- 未反映の注記: nagisa-publishng — 週 1 回の確認の場を隔週に変えた",
)

# 公開記録の ID を、もう 1 件と同じ値にする（どちらも裏づけに使われていない 2 件を選ぶ）。
DUPLICATE_ID = ("- ID: magazine-column-data", "- ID: case-article-quality")

# 同じ 1 行を、形の外の値にする。重なりではなく形の違反が挙がる。
OUT_OF_FORMAT_ID_LINE = "- ID: Magazine_Column_Data"

# 重なりと形の違反の文に出る、公開記録 2 件の表示名。
DUPLICATED_RECORD_NAME = "分かれた数字を 1 か所に集める手順の寄稿"
OTHER_RECORD_NAME = "品質記録の集約を取り上げた導入事例の記事"

# 形の外の ID の 3 通り。大文字を含む、40 字を超える、先頭がハイフン。
OUT_OF_FORMAT_IDS = {
    "大文字を含む": "Magazine-Column-Data",
    "40 字を超える": "magazine-column-data-" + "x" * 20,
    "先頭がハイフン": "-magazine-column-data",
}

# 5 つの型それぞれの ID を 1 つずつ形の外に崩す組。置き場の鍵・崩す前の 1 行・崩した後の 1 行。
OUT_OF_FORMAT_BY_TYPE = {
    "career": ("- ID: agency-employee", "- ID: Agency_Employee"),
    "engagements": ("- ID: yukinoha-quality", "- ID: Yukinoha_Quality"),
    "public_records": ("- ID: magazine-column-data", "- ID: Magazine_Column_Data"),
    "capabilities": ("| collect-sales-data |", "| Collect_Sales_Data |"),
    "packages": ("- ID: data-platform-setup", "- ID: Data_Platform_Setup"),
}

# 5 つの型それぞれの ID を 1 つずつ、別の型の項目がすでに使っている ID に書き換える組。
# 置き場の鍵・書き換える前の 1 行・書き換えた後の 1 行。重なる相手は別の置き場にあるので、
# 書き換えた置き場に出る重なりの違反は 1 件になる。
DUPLICATE_BY_TYPE = {
    "career": ("- ID: agency-employee", "- ID: yukinoha-quality"),
    "engagements": ("- ID: yukinoha-quality", "- ID: agency-employee"),
    "public_records": ("- ID: magazine-column-data", "- ID: yukinoha-quality"),
    "capabilities": ("| collect-sales-data |", "| yukinoha-quality |"),
    "packages": ("- ID: data-platform-setup", "- ID: yukinoha-quality"),
}

# 書きの操作に渡す ID の 2 通り。形の外の値と、別の項目がすでに使っている値。
OUT_OF_FORMAT_ID = "Collect_Milestones"
TAKEN_ID = ENGAGEMENT_ID


def _rewrite(path: Path, old: str, new: str) -> None:
    """写しの 1 か所を書き換える。狙った文字列が無ければ、テストの前提が崩れたとして落とす。"""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"写しに「{old}」が無い: {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _unreadable_sources(
    settings: Settings,
    *,
    career: bool = False,
    engagements: bool = False,
    public_records: bool = False,
) -> Settings:
    """照らす相手の正本だけを読めない設定に書き換えて、読み直した設定を返す。

    指す側は読めたまま、照らす相手の母集団だけを空にする。書き間違いと「そもそも読めていない」を
    言い分けないと、正しい裏づけの側を書き換える誘導になるので、その言い分けをここで作る。
    """
    path: Path = settings.config_path
    lines = path.read_text(encoding="utf-8").splitlines()
    if public_records:
        lines = [
            line
            for line in lines
            if not line.startswith(
                ("public_records = ", "public_record_kinds = ", "public_record_roles = ")
            )
        ]
    text = "\n".join(lines) + "\n"
    if career:
        text = text.replace('career = "career.md"', 'career = "no_such_career.md"', 1)
    if engagements:
        text = text.replace(
            'engagements = "engagements.md"', 'engagements = "no_such_engagements.md"', 1
        )
    path.write_text(text, encoding="utf-8")
    return load_settings(path)


def _violations(settings: Settings, pick) -> list:
    """写しの正本に検査を当て、選び出した違反だけを返す。"""
    report = ConsistencyService(settings).inspect()
    return [item for item in report.violations if pick(item)]


def _one(violations: list):
    """違反が 1 件だけ挙がっていることを確かめ、その 1 件を返す。"""
    assert len(violations) == 1, [item.model_dump() for item in violations]
    return violations[0]


def _id_format_violations(settings: Settings) -> list:
    """写しの正本に検査を当て、ID の形式の違反だけを取り出す。"""
    return _violations(settings, lambda item: item.constraint == ID_FORMAT)


def _id_uniqueness_violations(settings: Settings) -> list:
    """写しの正本に検査を当て、ID の一意性の違反だけを取り出す。"""
    return _violations(settings, lambda item: item.constraint == ID_UNIQUENESS)


def _labels(settings: Settings) -> dict[str, str]:
    """写しの正本から、ID と表示名の対応を引く。"""
    return ConsistencyService(settings).repository.load().labels()


def _candidates_are_plain_ids(candidates: list[str]) -> bool:
    """候補が、そのまま渡し直せる ID だけになっているか（表示名や括弧が混ざっていないか）。"""
    return bool(candidates) and all(is_id(item) for item in candidates)


def _names_the_candidates(text: str, candidates: list[str], labels: dict[str, str]) -> bool:
    """文が候補の並びを「候補: id（表示名）…」の形で挙げているか。"""
    return "候補: " in text and all(
        f"{item}（{labels[item]}）" in text for item in candidates
    )


# ------------------------------------------------ 指し方 1: 機能の裏づけの節


def _evidence_violations(settings: Settings) -> list:
    """写しの正本に検査を当て、裏づけの違反だけを取り出す。"""
    return _violations(settings, lambda item: item.constraint == EVIDENCE_SECTION_EXISTS)


def _evidence_readable_violations(settings: Settings) -> list:
    """実在する ID を指したままの裏づけの節で、挙がった違反を返す。"""
    assert WRONG_SEPARATOR[0] in settings.path_for("capabilities").read_text(encoding="utf-8")
    return _evidence_violations(settings)


def _evidence_format_violations(settings: Settings) -> list:
    """裏づけの節を、区切りを取り違えた値に書き換えて、挙がった違反を返す。"""
    _rewrite(settings.path_for("capabilities"), *WRONG_SEPARATOR)
    return _evidence_violations(settings)


def _evidence_empty_pool_violations(settings: Settings) -> list:
    """裏づけが照らす職歴の枠・受託案件・公開記録を 1 件も読めなくして、挙がった違反を返す。"""
    empty = _unreadable_sources(settings, career=True, engagements=True, public_records=True)
    return _evidence_violations(empty)


# ------------------------------------------------ 指し方 2: 公開記録の由来の節


def _origin_violations(settings: Settings) -> list:
    """写しの正本に検査を当て、由来の節の違反だけを取り出す。"""
    return _violations(settings, lambda item: item.constraint == ORIGIN_SECTION_EXISTS)


def _origin_readable_violations(settings: Settings) -> list:
    """実在する ID を指したままの由来の節で、挙がった違反を返す。"""
    assert ORIGIN_OUT_OF_FORMAT[0] in settings.path_for("public_records").read_text(
        encoding="utf-8"
    )
    return _origin_violations(settings)


def _origin_format_violations(settings: Settings) -> list:
    """由来の節を、見出しをそのまま書いた値に書き換えて、挙がった違反を返す。"""
    _rewrite(settings.path_for("public_records"), *ORIGIN_OUT_OF_FORMAT)
    return _origin_violations(settings)


def _origin_empty_pool_violations(settings: Settings) -> list:
    """由来の節が照らす職歴の枠と受託案件を読めなくして、挙がった違反を返す。"""
    empty = _unreadable_sources(settings, career=True, engagements=True)
    return _origin_violations(empty)


# ------------------------------------------------ 指し方 3: 職務経歴書の台帳の出典の節


def _ledger_violations(settings: Settings) -> list:
    """写しの正本に検査を当て、職務経歴書の台帳で挙がった違反だけを取り出す。"""
    return _violations(settings, lambda item: item.file == settings.files["resume_ledger"])


def _ledger_readable_violations(settings: Settings) -> list:
    """実在する ID を指したままの出典の節で、挙がった違反を返す。"""
    assert LEDGER_OUT_OF_FORMAT[0] in settings.path_for("resume_ledger").read_text(
        encoding="utf-8"
    )
    return _ledger_violations(settings)


def _ledger_format_violations(settings: Settings) -> list:
    """出典の節を、見出しをそのまま書いた値に書き換えて、挙がった違反を返す。"""
    _rewrite(settings.path_for("resume_ledger"), *LEDGER_OUT_OF_FORMAT)
    return _ledger_violations(settings)


def _ledger_empty_pool_violations(settings: Settings) -> list:
    """出典の節が照らす受託案件を読めなくして、挙がった違反を返す。"""
    empty = _unreadable_sources(settings, engagements=True)
    return _ledger_violations(empty)


# ------------------------------------------------ 指し方 4: 提示物の未反映の注記が指す節


def _note_path(settings: Settings) -> Path:
    """注記を仕込む提示物の場所。"""
    return settings.path_for("presentations") / "nagiho" / "skill_sheet.md"


def _note_violations(settings: Settings) -> list:
    """写しの正本に検査を当て、提示物で挙がった違反だけを取り出す。"""
    return _violations(settings, lambda item: item.file.startswith("presentations/"))


def _note_readable_violations(settings: Settings) -> list:
    """実在する ID を指す注記を仕込んで、挙がった違反を返す。"""
    _rewrite(_note_path(settings), *READABLE_NOTE)
    return _note_violations(settings)


def _note_format_violations(settings: Settings) -> list:
    """見出しをそのまま書いた注記を仕込んで、挙がった違反を返す。"""
    _rewrite(_note_path(settings), *NOTE_OUT_OF_FORMAT)
    return _note_violations(settings)


def _note_empty_pool_violations(settings: Settings) -> list:
    """注記を仕込み、注記が照らす受託案件を読めなくして、挙がった違反を返す。"""
    _rewrite(_note_path(settings), *DANGLING_NOTE)
    empty = _unreadable_sources(settings, engagements=True)
    return _note_violations(empty)


# ------------------------------------------------ 書きの操作に ID を渡す 3 通り


def _register_capability_with_id(settings: Settings, identifier: str) -> WriteResult:
    """機能の登記を、ID だけ差し替えて呼ぶ。ほかの欄は通る値にする。"""
    return OfferingService(settings).register_capability(
        CapabilityDraft(
            id=identifier,
            name="工程の期日を 1 枚に集める",
            description="部署ごとに持っている予定を 1 枚にまとめ、遅れを早く見つける",
            category=settings.capability_categories[2],
            evidence_sections=[ENGAGEMENT_ID],
        )
    )


def _revise_package_with_id(settings: Settings, identifier: str) -> WriteResult:
    """パッケージの改訂を、ID だけ差し替えて呼ぶ。ほかの欄は通る値にする。"""
    return OfferingService(settings).revise_package(
        PackageDraft(
            id=identifier,
            name=HEADLINE_PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY_ID],
            buyer="専任の進行役を置けない会社の事業責任者",
            hypothesis_state=settings.package_hypothesis_states[1],
        )
    )


def _register_public_record_with_id(settings: Settings, identifier: str) -> WriteResult:
    """公開記録の登記を、ID だけ差し替えて呼ぶ。ほかの欄は通る値にする。"""
    return PublicRecordService(settings).register(
        PublicRecordDraft(
            id=identifier,
            name="配送データの集約を話した勉強会の発表",
            kind=settings.public_record_kinds[1],
            published_on="2026-03-14",
            url="https://example.com/events/report/data-meetup/",
            publisher="データの置き場づくりを持ち寄る勉強会（架空の催し）",
            role=settings.public_record_roles[0],
            origin_section=PUBLISHING_ID,
        )
    )


# ID を持つ項目を書く操作の表。鍵は操作の名前で、型の正本が挙げる執行の一覧と突き合わせる。
# 操作が 1 つ増えたらここに 1 行足す。足し忘れは、下の突き合わせのテストが落ちて分かる。
ID_WRITE_OPERATIONS = {
    "register_capability": _register_capability_with_id,
    "revise_package": _revise_package_with_id,
    "register_public_record": _register_public_record_with_id,
}


def _id_rejection(settings: Settings, operation: str, identifier: str) -> Rejection:
    """その書きの操作に ID を渡し、受け付けなかったことを確かめて断りを返す。"""
    result = ID_WRITE_OPERATIONS[operation](settings, identifier)
    assert result.accepted is False, operation
    assert result.rejection is not None, operation
    return result.rejection


# ---------------- 指された値が読めないとき 1: 機能の裏づけの節


def test_REQ_247_evidence_a_readable_id_is_not_a_violation(settings) -> None:
    """機能の裏づけの節が実在する ID を指しているなら、その参照は違反にならない。"""
    violations = _evidence_readable_violations(settings)

    assert [item.model_dump() for item in violations] == []


def test_REQ_248_evidence_a_value_out_of_the_id_format_is_a_violation(settings) -> None:
    """裏づけの節が ID の形から外れた値を指すと、違反が 1 件挙がる。"""
    violations = _evidence_format_violations(settings)

    assert len(violations) == 1, [item.model_dump() for item in violations]


def test_REQ_249_evidence_a_format_violation_names_the_id_shape(settings) -> None:
    """裏づけの節の形の誤りは、ID の形そのものを直し先に書く。"""
    violation = _one(_evidence_format_violations(settings))

    assert "ID の形に合わない" in violation.expected, violation.expected
    assert ID_FORMAT_TEXT in violation.expected, violation.expected


def test_REQ_250_evidence_a_format_violation_says_to_use_the_section_id(settings) -> None:
    """裏づけの節の形の誤りは、見出しや名前をその節の ID に置き換えることを書く。"""
    violation = _one(_evidence_format_violations(settings))

    assert "その節の ID に置き換える" in violation.expected, violation.expected


def test_REQ_251_evidence_a_format_violation_names_the_slash_separator(settings) -> None:
    """裏づけの節の形の誤りは、2 つ以上を書くときの区切りが半角のスラッシュであることを書く。"""
    violation = _one(_evidence_format_violations(settings))

    assert "半角のスラッシュ" in violation.expected, violation.expected


def test_REQ_252_evidence_a_format_violation_lists_existing_ids(settings) -> None:
    """裏づけの節の形の誤りは、そのまま渡し直せる実在の ID を候補に返す。"""
    violation = _one(_evidence_format_violations(settings))

    assert _candidates_are_plain_ids(violation.candidates), violation.candidates
    assert set(violation.candidates) <= set(_labels(settings)), violation.candidates


def test_REQ_253_evidence_a_format_violation_names_the_candidate_labels(settings) -> None:
    """裏づけの節の形の誤りは、候補の ID の表示名を文の側に添える。"""
    violation = _one(_evidence_format_violations(settings))

    assert _names_the_candidates(
        violation.expected, violation.candidates, _labels(settings)
    ), violation.expected


def test_REQ_254_evidence_an_empty_pool_says_there_is_no_material(settings) -> None:
    """裏づけの節を照らす相手が 1 件も読めていないときは、候補ではなく材料が無いことを書く。"""
    violations = _evidence_empty_pool_violations(settings)

    assert violations, "裏づけの節の違反が 1 件も出ていない"
    for violation in violations:
        assert "候補を出せる材料が無い" in violation.expected, violation.expected


def test_REQ_255_evidence_an_empty_pool_names_the_reading_narrowing(settings) -> None:
    """裏づけの節を照らす相手が 1 件も読めていないときは、設定と正本のどちらを見るかを書く。"""
    violations = _evidence_empty_pool_violations(settings)

    assert violations, "裏づけの節の違反が 1 件も出ていない"
    for violation in violations:
        assert "読み方の絞り" in violation.expected, violation.expected
        assert "正本の節の位置" in violation.expected, violation.expected


def test_REQ_256_evidence_an_empty_pool_returns_no_candidates(settings) -> None:
    """裏づけの節を照らす相手が 1 件も読めていないときは、候補を空で返す。"""
    violations = _evidence_empty_pool_violations(settings)

    assert violations, "裏づけの節の違反が 1 件も出ていない"
    for violation in violations:
        assert violation.candidates == [], violation.candidates


# ---------------- 指された値が読めないとき 2: 公開記録の由来の節


def test_REQ_257_origin_a_readable_id_is_not_a_violation(settings) -> None:
    """公開記録の由来の節が実在する ID を指しているなら、その参照は違反にならない。"""
    violations = _origin_readable_violations(settings)

    assert [item.model_dump() for item in violations] == []


def test_REQ_258_origin_a_value_out_of_the_id_format_is_a_violation(settings) -> None:
    """由来の節が ID の形から外れた値を指すと、違反が 1 件挙がる。"""
    violations = _origin_format_violations(settings)

    assert len(violations) == 1, [item.model_dump() for item in violations]


def test_REQ_259_origin_a_format_violation_names_the_id_shape(settings) -> None:
    """由来の節の形の誤りは、ID の形そのものを直し先に書く。"""
    violation = _one(_origin_format_violations(settings))

    assert "ID の形に合わない" in violation.expected, violation.expected
    assert ID_FORMAT_TEXT in violation.expected, violation.expected


def test_REQ_260_origin_a_format_violation_says_to_use_the_section_id(settings) -> None:
    """由来の節の形の誤りは、見出しや名前をその節の ID に置き換えることを書く。"""
    violation = _one(_origin_format_violations(settings))

    assert "その節の ID に置き換える" in violation.expected, violation.expected


def test_REQ_261_origin_a_format_violation_names_the_slash_separator(settings) -> None:
    """由来の節の形の誤りは、2 つ以上を書くときの区切りが半角のスラッシュであることを書く。"""
    violation = _one(_origin_format_violations(settings))

    assert "半角のスラッシュ" in violation.expected, violation.expected


def test_REQ_262_origin_a_format_violation_lists_existing_ids(settings) -> None:
    """由来の節の形の誤りは、そのまま渡し直せる実在の ID を候補に返す。"""
    violation = _one(_origin_format_violations(settings))

    assert _candidates_are_plain_ids(violation.candidates), violation.candidates
    assert set(violation.candidates) <= set(_labels(settings)), violation.candidates


def test_REQ_263_origin_a_format_violation_names_the_candidate_labels(settings) -> None:
    """由来の節の形の誤りは、候補の ID の表示名を文の側に添える。"""
    violation = _one(_origin_format_violations(settings))

    assert _names_the_candidates(
        violation.expected, violation.candidates, _labels(settings)
    ), violation.expected


def test_REQ_264_origin_an_empty_pool_says_there_is_no_material(settings) -> None:
    """由来の節を照らす相手が 1 件も読めていないときは、候補ではなく材料が無いことを書く。"""
    violations = _origin_empty_pool_violations(settings)

    assert violations, "由来の節の違反が 1 件も出ていない"
    for violation in violations:
        assert "候補を出せる材料が無い" in violation.expected, violation.expected


def test_REQ_265_origin_an_empty_pool_names_the_reading_narrowing(settings) -> None:
    """由来の節を照らす相手が 1 件も読めていないときは、設定と正本のどちらを見るかを書く。"""
    violations = _origin_empty_pool_violations(settings)

    assert violations, "由来の節の違反が 1 件も出ていない"
    for violation in violations:
        assert "読み方の絞り" in violation.expected, violation.expected
        assert "正本の節の位置" in violation.expected, violation.expected


def test_REQ_266_origin_an_empty_pool_returns_no_candidates(settings) -> None:
    """由来の節を照らす相手が 1 件も読めていないときは、候補を空で返す。"""
    violations = _origin_empty_pool_violations(settings)

    assert violations, "由来の節の違反が 1 件も出ていない"
    for violation in violations:
        assert violation.candidates == [], violation.candidates


# ---------------- 指された値が読めないとき 3: 職務経歴書の台帳の出典の節


def test_REQ_267_ledger_a_readable_id_is_not_a_violation(settings) -> None:
    """職務経歴書の台帳の出典の節が実在する ID を指しているなら、その参照は違反にならない。"""
    violations = _ledger_readable_violations(settings)

    assert [item.model_dump() for item in violations] == []


def test_REQ_268_ledger_a_value_out_of_the_id_format_is_a_violation(settings) -> None:
    """出典の節が ID の形から外れた値を指すと、違反が 1 件挙がる。"""
    violations = _ledger_format_violations(settings)

    assert len(violations) == 1, [item.model_dump() for item in violations]


def test_REQ_269_ledger_a_format_violation_names_the_id_shape(settings) -> None:
    """出典の節の形の誤りは、ID の形そのものを直し先に書く。"""
    violation = _one(_ledger_format_violations(settings))

    assert "ID の形に合わない" in violation.expected, violation.expected
    assert ID_FORMAT_TEXT in violation.expected, violation.expected


def test_REQ_270_ledger_a_format_violation_says_to_use_the_section_id(settings) -> None:
    """出典の節の形の誤りは、見出しや名前をその節の ID に置き換えることを書く。"""
    violation = _one(_ledger_format_violations(settings))

    assert "その節の ID に置き換える" in violation.expected, violation.expected


def test_REQ_271_ledger_a_format_violation_names_the_slash_separator(settings) -> None:
    """出典の節の形の誤りは、2 つ以上を書くときの区切りが半角のスラッシュであることを書く。"""
    violation = _one(_ledger_format_violations(settings))

    assert "半角のスラッシュ" in violation.expected, violation.expected


def test_REQ_272_ledger_a_format_violation_lists_existing_ids(settings) -> None:
    """出典の節の形の誤りは、そのまま渡し直せる実在の ID を候補に返す。"""
    violation = _one(_ledger_format_violations(settings))

    assert _candidates_are_plain_ids(violation.candidates), violation.candidates
    assert set(violation.candidates) <= set(_labels(settings)), violation.candidates


def test_REQ_273_ledger_a_format_violation_names_the_candidate_labels(settings) -> None:
    """出典の節の形の誤りは、候補の ID の表示名を文の側に添える。"""
    violation = _one(_ledger_format_violations(settings))

    assert _names_the_candidates(
        violation.expected, violation.candidates, _labels(settings)
    ), violation.expected


def test_REQ_274_ledger_an_empty_pool_says_there_is_no_material(settings) -> None:
    """出典の節を照らす相手が 1 件も読めていないときは、候補ではなく材料が無いことを書く。"""
    violations = _ledger_empty_pool_violations(settings)

    assert violations, "出典の節の違反が 1 件も出ていない"
    for violation in violations:
        assert "候補を出せる材料が無い" in violation.expected, violation.expected


def test_REQ_275_ledger_an_empty_pool_names_the_reading_narrowing(settings) -> None:
    """出典の節を照らす相手が 1 件も読めていないときは、設定と正本のどちらを見るかを書く。"""
    violations = _ledger_empty_pool_violations(settings)

    assert violations, "出典の節の違反が 1 件も出ていない"
    for violation in violations:
        assert "読み方の絞り" in violation.expected, violation.expected
        assert "正本の節の位置" in violation.expected, violation.expected


def test_REQ_276_ledger_an_empty_pool_returns_no_candidates(settings) -> None:
    """出典の節を照らす相手が 1 件も読めていないときは、候補を空で返す。"""
    violations = _ledger_empty_pool_violations(settings)

    assert violations, "出典の節の違反が 1 件も出ていない"
    for violation in violations:
        assert violation.candidates == [], violation.candidates


# ---------------- 指された値が読めないとき 4: 提示物の未反映の注記が指す節


def test_REQ_277_note_a_readable_id_is_not_a_violation(settings) -> None:
    """提示物の未反映の注記が指す節が実在する ID を指しているなら、その参照は違反にならない。"""
    violations = _note_readable_violations(settings)

    assert [item.model_dump() for item in violations] == []


def test_REQ_278_note_a_value_out_of_the_id_format_is_a_violation(settings) -> None:
    """注記が指す節が ID の形から外れた値を指すと、違反が 1 件挙がる。"""
    violations = _note_format_violations(settings)

    assert len(violations) == 1, [item.model_dump() for item in violations]


def test_REQ_279_note_a_format_violation_names_the_id_shape(settings) -> None:
    """注記が指す節の形の誤りは、ID の形そのものを直し先に書く。"""
    violation = _one(_note_format_violations(settings))

    assert "ID の形に合わない" in violation.expected, violation.expected
    assert ID_FORMAT_TEXT in violation.expected, violation.expected


def test_REQ_280_note_a_format_violation_says_to_use_the_section_id(settings) -> None:
    """注記が指す節の形の誤りは、見出しや名前をその節の ID に置き換えることを書く。"""
    violation = _one(_note_format_violations(settings))

    assert "その節の ID に置き換える" in violation.expected, violation.expected


def test_REQ_281_note_a_format_violation_names_the_slash_separator(settings) -> None:
    """注記が指す節の形の誤りは、2 つ以上を書くときの区切りが半角のスラッシュであることを書く。"""
    violation = _one(_note_format_violations(settings))

    assert "半角のスラッシュ" in violation.expected, violation.expected


def test_REQ_282_note_a_format_violation_lists_existing_ids(settings) -> None:
    """注記が指す節の形の誤りは、そのまま渡し直せる実在の ID を候補に返す。"""
    violation = _one(_note_format_violations(settings))

    assert _candidates_are_plain_ids(violation.candidates), violation.candidates
    assert set(violation.candidates) <= set(_labels(settings)), violation.candidates


def test_REQ_283_note_a_format_violation_names_the_candidate_labels(settings) -> None:
    """注記が指す節の形の誤りは、候補の ID の表示名を文の側に添える。"""
    violation = _one(_note_format_violations(settings))

    assert _names_the_candidates(
        violation.expected, violation.candidates, _labels(settings)
    ), violation.expected


def test_REQ_284_note_an_empty_pool_says_there_is_no_material(settings) -> None:
    """注記が指す節を照らす相手が 1 件も読めていないときは、候補ではなく材料が無いことを書く。"""
    violations = _note_empty_pool_violations(settings)

    assert violations, "注記が指す節の違反が 1 件も出ていない"
    for violation in violations:
        assert "候補を出せる材料が無い" in violation.expected, violation.expected


def test_REQ_285_note_an_empty_pool_names_the_reading_narrowing(settings) -> None:
    """注記が指す節を照らす相手が 1 件も読めていないときは、設定と正本のどちらを見るかを書く。"""
    violations = _note_empty_pool_violations(settings)

    assert violations, "注記が指す節の違反が 1 件も出ていない"
    for violation in violations:
        assert "読み方の絞り" in violation.expected, violation.expected
        assert "正本の節の位置" in violation.expected, violation.expected


def test_REQ_286_note_an_empty_pool_returns_no_candidates(settings) -> None:
    """注記が指す節を照らす相手が 1 件も読めていないときは、候補を空で返す。"""
    violations = _note_empty_pool_violations(settings)

    assert violations, "注記が指す節の違反が 1 件も出ていない"
    for violation in violations:
        assert violation.candidates == [], violation.candidates


# ---------------------------------------------- どこにも無い ID（4 つの指し方に共通）


def _dangling_violations(settings: Settings) -> list:
    """裏づけの節を、形は合うが実在しない ID に書き換えて、挙がった違反を返す。"""
    _rewrite(settings.path_for("capabilities"), *DANGLING_ID)
    return _evidence_violations(settings)


def test_REQ_287_a_dangling_id_is_a_violation(settings) -> None:
    """形は合うが正本のどこにも無い ID を指すと、違反が 1 件挙がる。"""
    violations = _dangling_violations(settings)

    assert len(violations) == 1, [item.model_dump() for item in violations]


def test_REQ_288_a_dangling_id_is_named_as_missing(settings) -> None:
    """どこにも無い ID は、形の誤りではなく「読めている ID に無い」として挙げる。"""
    violation = _one(_dangling_violations(settings))

    assert "無い ID" in violation.expected, violation.expected
    assert "ID の形に合わない" not in violation.expected, violation.expected


def test_REQ_289_a_dangling_id_lists_close_ids(settings) -> None:
    """どこにも無い ID には、綴りの近い実在の ID を候補に返す。"""
    violation = _one(_dangling_violations(settings))

    assert _candidates_are_plain_ids(violation.candidates), violation.candidates
    assert PUBLISHING_ID in violation.candidates, violation.candidates


def test_REQ_290_a_dangling_id_names_the_candidate_labels(settings) -> None:
    """どこにも無い ID の違反は、候補の表示名を文の側に添える。"""
    violation = _one(_dangling_violations(settings))

    # 表示名は候補の欄ではなく、違反の文の側に添えて出る。
    assert PUBLISHING_HEADING in violation.expected, violation.expected


# ---------------------------------------------------------------- ID の形式と ID の一意性


def _out_of_format_id_violations(settings: Settings) -> list:
    """公開記録 1 件の ID を形の外の値に書き換えて、ID の形式の違反を返す。"""
    _rewrite(settings.path_for("public_records"), DUPLICATE_ID[0], OUT_OF_FORMAT_ID_LINE)
    return _id_format_violations(settings)


def _duplicate_id_violations(settings: Settings) -> list:
    """公開記録 1 件の ID を、もう 1 件と同じ値に書き換えて、ID の一意性の違反を返す。"""
    _rewrite(settings.path_for("public_records"), *DUPLICATE_ID)
    return _id_uniqueness_violations(settings)


def test_REQ_364_the_id_format_check_covers_five_types(settings) -> None:
    """5 つの型のどの ID を形の外に崩しても、その置き場を名指しした形式の違反が挙がる。

    崩すのは 1 つの型ずつで、崩した後は写しを元に戻す。どれか 1 つの型を検査から外しても、
    その型の回で違反が 0 件になって落ちる。
    """
    for key, (before, after) in OUT_OF_FORMAT_BY_TYPE.items():
        copy = load_settings(settings.config_path)
        path = copy.path_for(key)
        text = path.read_text(encoding="utf-8")
        assert before in text, key
        path.write_text(text.replace(before, after, 1), encoding="utf-8")

        violations = [item for item in _id_format_violations(copy) if item.file == copy.files[key]]
        assert len(violations) == 1, (key, [item.model_dump() for item in violations])

        path.write_text(text, encoding="utf-8")


def test_REQ_365_the_id_uniqueness_check_covers_five_types(settings) -> None:
    """5 つの型のどの ID を別の型の ID と重ねても、その置き場を名指しした一意性の違反が挙がる。

    重ねるのは 1 つの型ずつで、重ねた後は写しを元に戻す。どれか 1 つの型を検査から外しても、
    その型の回で違反が 0 件になって落ちる。
    """
    for key, (before, after) in DUPLICATE_BY_TYPE.items():
        copy = load_settings(settings.config_path)
        path = copy.path_for(key)
        text = path.read_text(encoding="utf-8")
        assert before in text, key
        path.write_text(text.replace(before, after, 1), encoding="utf-8")

        violations = [
            item for item in _id_uniqueness_violations(copy) if item.file == copy.files[key]
        ]
        assert len(violations) == 1, (key, [item.model_dump() for item in violations])

        path.write_text(text, encoding="utf-8")


def test_REQ_292_an_id_out_of_format_raises_one_violation(settings) -> None:
    """大文字・40 字超・先頭のハイフンのどれでも、違反が 1 件挙がる。"""
    for label, written in OUT_OF_FORMAT_IDS.items():
        copy = load_settings(settings.config_path)
        path = copy.path_for("public_records")
        text = path.read_text(encoding="utf-8")
        assert DUPLICATE_ID[0] in text, label
        path.write_text(text.replace(DUPLICATE_ID[0], f"- ID: {written}", 1), encoding="utf-8")

        violations = _id_format_violations(copy)
        assert len(violations) == 1, (label, [item.model_dump() for item in violations])
        assert "形に合わない" in violations[0].expected, label

        path.write_text(text, encoding="utf-8")


def test_REQ_293_an_id_out_of_format_names_the_id_field(settings) -> None:
    """形の外の ID の違反は、その項目の ID の欄を場所に書く。"""
    violation = _one(_out_of_format_id_violations(settings))

    assert violation.location.endswith("の「ID」"), violation.location
    assert DUPLICATED_RECORD_NAME in violation.location, violation.location


def test_REQ_294_an_id_out_of_format_says_to_fix_the_referring_side(settings) -> None:
    """形の外の ID の違反は、その ID を指している側も同じ値に直すことを書く。"""
    violation = _one(_out_of_format_id_violations(settings))

    assert "指している側も同じ値に直す" in violation.expected, violation.expected


def test_REQ_295_a_duplicate_id_raises_one_violation_for_each_place(settings) -> None:
    """同じ ID を 2 つの項目に付けると、項目ごとに違反が 1 件ずつ挙がる。"""
    violations = _duplicate_id_violations(settings)

    assert len(violations) == 2, [item.model_dump() for item in violations]
    for violation in violations:
        assert violation.file == settings.files["public_records"]


def test_REQ_296_a_duplicate_id_names_the_count_and_the_places(settings) -> None:
    """重なりの違反には、使われている数と、2 つの場所の表示名が入る。"""
    violations = _duplicate_id_violations(settings)

    assert violations
    for violation in violations:
        assert "2 か所で使われている" in violation.expected, violation.expected
        assert DUPLICATED_RECORD_NAME in violation.expected, violation.expected
        assert OTHER_RECORD_NAME in violation.expected, violation.expected


def test_REQ_297_a_duplicate_id_says_to_rename_one_side(settings) -> None:
    """重なりの違反は、一方を別の値に直し、指している側も直すことを書く。"""
    violations = _duplicate_id_violations(settings)

    assert violations
    for violation in violations:
        assert "どちらか一方を別の値に直し" in violation.expected, violation.expected
        assert "指している側も同じ値に直す" in violation.expected, violation.expected


def test_REQ_366_public_records_are_left_out_of_the_format_check_when_the_file_is_unset(
    settings,
) -> None:
    """設定に公開記録の置き場が無ければ、公開記録の ID は形式の検査に入らない。

    置き場があるときは同じ書き換えで形式の違反が出ることを先に確かめ、見ていないだけで
    合格しているのではないことを押さえる。
    """
    _rewrite(settings.path_for("public_records"), DUPLICATE_ID[0], OUT_OF_FORMAT_ID_LINE)
    assert _id_format_violations(settings), "置き場があるときに形式の違反が出ていない"
    plain = _unreadable_sources(settings, public_records=True)

    violations = _id_format_violations(plain)

    assert [item.model_dump() for item in violations] == []


def test_REQ_367_public_records_are_left_out_of_the_uniqueness_check_when_the_file_is_unset(
    settings,
) -> None:
    """設定に公開記録の置き場が無ければ、公開記録の ID は一意性の検査に入らない。

    置き場があるときは同じ書き換えで重なりの違反が出ることを先に確かめ、見ていないだけで
    合格しているのではないことを押さえる。
    """
    _rewrite(settings.path_for("public_records"), *DUPLICATE_ID)
    assert _id_uniqueness_violations(settings), "置き場があるときに重なりの違反が出ていない"
    plain = _unreadable_sources(settings, public_records=True)

    violations = _id_uniqueness_violations(plain)

    assert [item.model_dump() for item in violations] == []


# ---------------------------------------------------------------- 見出しの書き換え


def test_REQ_299_renaming_a_heading_adds_no_violation(settings) -> None:
    """職歴の枠の見出しを書き換えても、ID がそのままなら違反は増えない。

    見出しの文字を写して結んでいたときは、改名が参照の切れになった。ID で結ぶと切れない。
    """
    before = len(ConsistencyService(settings).inspect().violations)
    assert before == 0

    _rewrite(settings.path_for("career"), f"## {CAREER_HEADING}", f"## {NEW_CAREER_HEADING}")

    report = ConsistencyService(settings).inspect()
    assert [item.model_dump() for item in report.violations] == []


def test_REQ_300_renaming_a_heading_shows_the_new_heading_in_material(settings) -> None:
    """見出しを書き換えた節は、ID で引けたまま、書き換えた後の見出しで材料に載る。"""
    _rewrite(settings.path_for("career"), f"## {CAREER_HEADING}", f"## {NEW_CAREER_HEADING}")

    material = MaterialService(settings).assemble(MaterialRequest(channel="tsukikusa"))

    listed = {entry["ID"]: entry["見出し"] for entry in material.evidence}
    assert listed.get(CAREER_ID) == NEW_CAREER_HEADING, listed


# ---------------------------------------------------------------- 裏づけの本文


def test_REQ_301_the_evidence_body_drops_the_id_line(settings, alt_settings) -> None:
    """裏づけの本文から、ID の欄の行が落ちている。

    ID は鍵としても欄としても別に返しているので、本文にも残すと同じ値を 2 か所で受け取る。
    """
    for target in (settings, alt_settings):
        material = MaterialService(target).assemble(MaterialRequest(channel="tsukikusa"))
        assert material.evidence, target.config_path.name

        for entry in material.evidence:
            body = entry["本文"]
            name = target.config_path.name
            assert entry["ID"] not in body, (name, body)
            assert "- ID:" not in body, (name, body)


def test_REQ_302_the_evidence_body_keeps_the_other_fields(settings, alt_settings) -> None:
    """裏づけの本文から落ちるのは ID の行だけで、ほかの欄の行は残っている。"""
    for target in (settings, alt_settings):
        material = MaterialService(target).assemble(MaterialRequest(channel="tsukikusa"))
        assert material.evidence, target.config_path.name

        for entry in material.evidence:
            body = entry["本文"]
            name = target.config_path.name
            assert "公開可否" in body, (name, body)
            assert "やったこと" in body or "内容" in body, (name, body)
            assert body.strip(), name


def test_REQ_303_the_evidence_body_drops_a_relabelled_id_line(settings, alt_settings) -> None:
    """ID のラベルを読み替える正本でも、読み替えた後のラベルの行が本文から落ちている。"""
    for target in (settings, alt_settings):
        material = MaterialService(target).assemble(MaterialRequest(channel="tsukikusa"))
        assert material.evidence, target.config_path.name

        for entry in material.evidence:
            body = entry["本文"]
            name = target.config_path.name
            assert "- 識別子:" not in body, (name, body)


def test_REQ_304_a_section_without_an_id_is_not_referable(settings) -> None:
    """ID の行を持たない節は、裏づけとして指せる節に入らない。"""
    before = MarkdownRepository(settings).evidence_bodies()
    assert CAREER_WITHOUT_ID in before, sorted(before)

    _rewrite(settings.path_for("career"), f"- ID: {CAREER_WITHOUT_ID}\n", "")

    after = MarkdownRepository(settings).evidence_bodies()
    assert CAREER_WITHOUT_ID not in after, sorted(after)
    assert len(after) == len(before) - 1, (sorted(before), sorted(after))
    assert all(CAREER_WITHOUT_ID_MARK not in body for body in after.values())


# ------------------------------------------- 書きの操作が ID を断る（3 つの操作で回す）


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_305_an_id_out_of_format_is_not_written(settings, operation: str) -> None:
    """形の外の ID を渡した項目は、正本のバイト列を 1 つも変えずに断る。"""
    before = source_digest(settings.source_dir)

    result = ID_WRITE_OPERATIONS[operation](settings, OUT_OF_FORMAT_ID)

    assert result.accepted is False, operation
    assert source_digest(settings.source_dir) == before, operation


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_306_an_id_out_of_format_rejection_names_the_constraint(settings, operation: str) -> None:
    """形の外の ID の断りは、当たった制約の名前を返す。"""
    rejection = _id_rejection(settings, operation, OUT_OF_FORMAT_ID)

    assert rejection.constraint == ID_FORMAT, operation


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_307_an_id_out_of_format_rejection_names_the_id_shape(settings, operation: str) -> None:
    """形の外の ID の断りは、渡された ID と ID の形を理由に書く。"""
    rejection = _id_rejection(settings, operation, OUT_OF_FORMAT_ID)

    assert f"ID「{OUT_OF_FORMAT_ID}」" in rejection.reason, rejection.reason
    assert ID_FORMAT_TEXT in rejection.reason, rejection.reason


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_308_an_id_out_of_format_rejection_shows_existing_ids(settings, operation: str) -> None:
    """形の外の ID の断りは、正本にすでにある ID を例として理由に書く。"""
    rejection = _id_rejection(settings, operation, OUT_OF_FORMAT_ID)

    assert "正本にすでにある ID を例にすると" in rejection.reason, rejection.reason
    assert ENGAGEMENT_ID in rejection.reason, rejection.reason


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_309_an_id_out_of_format_rejection_names_the_next_operation(settings, operation: str) -> None:
    """形の外の ID の断りは、呼ばれた操作の名前を次に呼ぶ操作として返す。"""
    rejection = _id_rejection(settings, operation, OUT_OF_FORMAT_ID)

    assert rejection.next_action.operation == operation


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_310_an_id_out_of_format_rejection_lists_existing_ids(settings, operation: str) -> None:
    """形の外の ID の断りは、正本にすでにある ID を候補に返す。"""
    rejection = _id_rejection(settings, operation, OUT_OF_FORMAT_ID)

    candidates = rejection.next_action.candidates
    assert _candidates_are_plain_ids(candidates), candidates
    assert set(candidates) <= set(_labels(settings)), candidates


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_311_an_id_out_of_format_rejection_carries_an_example(settings, operation: str) -> None:
    """形の外の ID の断りは、ID の書き方の例を返す。"""
    rejection = _id_rejection(settings, operation, OUT_OF_FORMAT_ID)

    example = rejection.next_action.example
    assert example, operation
    assert "ハイフン" in example, example


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_312_a_taken_id_is_not_written(settings, operation: str) -> None:
    """すでに使われている ID を渡した項目は、正本のバイト列を 1 つも変えずに断る。"""
    before = source_digest(settings.source_dir)

    result = ID_WRITE_OPERATIONS[operation](settings, TAKEN_ID)

    assert result.accepted is False, operation
    assert source_digest(settings.source_dir) == before, operation


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_313_a_taken_id_rejection_names_the_constraint(settings, operation: str) -> None:
    """すでに使われている ID の断りは、当たった制約の名前を返す。"""
    rejection = _id_rejection(settings, operation, TAKEN_ID)

    assert rejection.constraint == ID_UNIQUENESS, operation


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_314_a_taken_id_rejection_names_the_holder(settings, operation: str) -> None:
    """すでに使われている ID の断りは、その ID を使っている項目の表示名を理由に書く。"""
    rejection = _id_rejection(settings, operation, TAKEN_ID)

    assert ENGAGEMENT_HEADING in rejection.reason, rejection.reason


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_315_a_taken_id_rejection_says_ids_are_unique(settings, operation: str) -> None:
    """すでに使われている ID の断りは、ID が 1 つの項目にしか付かないことを理由に書く。"""
    rejection = _id_rejection(settings, operation, TAKEN_ID)

    assert "1 つの項目にしか付けられない" in rejection.reason, rejection.reason


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_316_a_taken_id_rejection_names_the_next_operation(settings, operation: str) -> None:
    """すでに使われている ID の断りは、呼ばれた操作の名前を次に呼ぶ操作として返す。"""
    rejection = _id_rejection(settings, operation, TAKEN_ID)

    assert rejection.next_action.operation == operation


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_317_a_taken_id_rejection_returns_no_candidates(settings, operation: str) -> None:
    """すでに使われている ID の断りは、渡し直せる代わりの値が無いので候補を空で返す。"""
    rejection = _id_rejection(settings, operation, TAKEN_ID)

    assert rejection.next_action.candidates == [], rejection.next_action.candidates


@pytest.mark.parametrize("operation", sorted(ID_WRITE_OPERATIONS))
def test_REQ_318_a_taken_id_rejection_carries_an_example(settings, operation: str) -> None:
    """すでに使われている ID の断りは、まだ使われていない ID で呼び直す例を返す。"""
    rejection = _id_rejection(settings, operation, TAKEN_ID)

    example = rejection.next_action.example
    assert "使っていない ID" in example, example
    assert "呼び直す" in example, example


def test_REQ_319_revising_a_package_keeps_its_own_id(settings) -> None:
    """改訂で、差し替える節が前から持っている ID を渡しても、重なりとして断らない。"""
    result = _revise_package_with_id(settings, HEADLINE_PACKAGE_ID)

    assert result.rejection is None, result.rejection
    assert result.accepted is True


def test_the_id_rejection_table_covers_every_write_operation() -> None:
    """番号なし: ID の断りを回す操作の表が、型の正本が挙げる執行の一覧（検査を除く）と一致するかを試す。accord の振る舞いではなく、テストの表と型の正本の食い違いを見張るものなので、要件に結ばない。

    ID の断りを回す操作の表が、型の正本が挙げる執行の一覧（検査を除く）と一致する。

    表を手で書いたまま、型の正本の側で操作が増えても気づけない、という穴を塞ぐ。操作が一覧から
    消えても、表から 1 行消えても、このテストが落ちる。
    """
    for name in (ID_FORMAT, ID_UNIQUENESS):
        constraint = next(item for item in CONSTRAINTS if item.name == name)

        enforced = set(constraint.enforced_by) - {INSPECT_OPERATION}

        assert set(ID_WRITE_OPERATIONS) == enforced, (name, sorted(enforced))

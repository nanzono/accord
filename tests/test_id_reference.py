"""正本どうしの結びを ID で行うことの受け入れ条件のテスト。

見るのは 7 つ。型の正本が 5 つの型に必須の ID の欄を持つこと、区切りを取り違えた値を
「ID の形に合わない」と断定すること、形は合うが実在しない ID を「どこにも無い」と言い分けること、
ID の重なりと形の外れを検査が挙げること、見出しを書き換えても参照が切れないこと、
照らす相手が 1 件も読めていないときに候補の代わりに材料が無いことを言うこと、
そして機能を登記する操作が ID を書き込みの瞬間に拒否することである。

違反はすべて、同梱のサンプルの一時的な写しに仕込む。リポジトリのサンプルそのものは整ったままにする。
"""

from __future__ import annotations

from pathlib import Path

from accord.models.ontology import load_ontology
from accord.models.results import CapabilityDraft, MaterialRequest, is_id
from accord.services.consistency import ConsistencyService
from accord.services.material import MaterialService
from accord.services.offering import OfferingService
from accord.vocabulary.settings import load_settings
from conftest import source_digest

# ID を持つ 5 つの型。指される側だけがこの欄を持つ。
ID_BEARING_TYPES = ("CareerFrame", "Engagement", "PublicRecord", "Capability", "Package")

EVIDENCE_SECTION_EXISTS = "裏づけ節名の実在"
ID_FORMAT_AND_UNIQUENESS = "ID の形式と一意性"

# 同梱のサンプルにある ID と、その表示名。
ENGAGEMENT_ID = "teramina-delivery"
ENGAGEMENT_HEADING = "テラミナ物流 配送データの置き場づくり"
CAREER_ID = "freelance-solo"
CAREER_HEADING = "2021-04〜現在 フリーランス"

# 裏づけの 1 行を、区切りを取り違えた形に書き換える。全角の中黒は区切りとして読まれない。
WRONG_SEPARATOR = (
    "| teramina-delivery / yukinoha-quality |",
    "| teramina-delivery・yukinoha-quality |",
)

# 裏づけの 1 行を、形は合うが実在しない ID に書き換える。
DANGLING_ID = ("| nagisa-publishing |", "| nagisa-publishng |")

# 公開記録の ID を、もう 1 件と同じ値にする（どちらも裏づけに使われていない 2 件を選ぶ）。
DUPLICATE_ID = ("- ID: magazine-column-data", "- ID: case-article-quality")

# 形の外の ID の 3 通り。大文字を含む、40 字を超える、先頭がハイフン。
OUT_OF_FORMAT_IDS = {
    "大文字を含む": "Magazine-Column-Data",
    "40 字を超える": "magazine-column-data-" + "x" * 20,
    "先頭がハイフン": "-magazine-column-data",
}


def _rewrite(path: Path, old: str, new: str) -> None:
    """写しの 1 か所を書き換える。狙った文字列が無ければ、テストの前提が崩れたとして落とす。"""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"写しに「{old}」が無い: {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _evidence_violations(settings) -> list:
    """写しの正本に検査を当て、裏づけの違反だけを取り出す。"""
    report = ConsistencyService(settings).inspect()
    return [v for v in report.violations if v.constraint == EVIDENCE_SECTION_EXISTS]


def _id_violations(settings) -> list:
    """写しの正本に検査を当て、ID の形式と一意性の違反だけを取り出す。"""
    report = ConsistencyService(settings).inspect()
    return [v for v in report.violations if v.constraint == ID_FORMAT_AND_UNIQUENESS]


def _labels(settings) -> dict[str, str]:
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


# ---------------------------------------------------------------- 型の正本


def test_five_types_require_an_id_field() -> None:
    """指される側の 5 つの型が、必須の text の欄 id を持ち、制約は 12 件ある。"""
    ontology = load_ontology()

    for name in ID_BEARING_TYPES:
        entry = ontology.type_named(name)
        assert entry is not None, name
        field = next((item for item in entry.fields if item.name == "id"), None)
        assert field is not None, f"{name} に欄 id が無い"
        assert field.required is True, name
        assert field.type == "text", name
        assert field.label == "ID", name

    assert len(ontology.constraints) == 12
    assert any(item.name == ID_FORMAT_AND_UNIQUENESS for item in ontology.constraints)


# ---------------------------------------------------------------- 参照の値の言い分け


def test_wrong_separator_is_named_as_a_format_error(settings) -> None:
    """半角のスラッシュ以外でつないだ裏づけは、「どこにも無い」ではなく形の誤りとして挙がる。

    区切りを取り違えた値は、文字列としては正しい見出しの並びに見える。ID の形で見れば、
    つないだ全体が 1 つの値として形から外れるので、推測ではなく形式の検査で断定できる。
    """
    _rewrite(settings.path_for("capabilities"), *WRONG_SEPARATOR)

    violations = _evidence_violations(settings)

    assert len(violations) == 1, [v.model_dump() for v in violations]
    violation = violations[0]
    assert "ID の形に合わない" in violation.expected, violation.expected
    assert "半角のスラッシュ" in violation.expected, violation.expected
    assert _candidates_are_plain_ids(violation.candidates), violation.candidates
    assert _names_the_candidates(
        violation.expected, violation.candidates, _labels(settings)
    ), violation.expected


def test_dangling_id_is_named_as_missing_everywhere(settings) -> None:
    """形は合うが実在しない ID は、「どこにも無い」として挙げ、実在する ID を候補に返す。"""
    _rewrite(settings.path_for("capabilities"), *DANGLING_ID)

    violations = _evidence_violations(settings)

    assert len(violations) == 1, [v.model_dump() for v in violations]
    violation = violations[0]
    assert "無い ID" in violation.expected, violation.expected
    assert "ID の形に合わない" not in violation.expected, violation.expected
    assert _candidates_are_plain_ids(violation.candidates), violation.candidates
    assert "nagisa-publishing" in violation.candidates, violation.candidates
    # 表示名は候補の欄ではなく、違反の文の側に添えて出る。
    assert "ナギサ書房 刊行計画の進行管理" in violation.expected, violation.expected


# ---------------------------------------------------------------- ID の形式と一意性


def test_duplicate_id_names_both_places(settings) -> None:
    """同じ ID を 2 つの項目に付けると、どちらの違反にも 2 つの場所が入る。"""
    _rewrite(settings.path_for("public_records"), *DUPLICATE_ID)

    violations = _id_violations(settings)

    assert len(violations) == 2, [v.model_dump() for v in violations]
    for violation in violations:
        assert violation.file == settings.files["public_records"]
        assert "分かれた数字を 1 か所に集める手順の寄稿" in violation.expected, violation.expected
        assert "品質記録の集約を取り上げた導入事例の記事" in violation.expected, violation.expected


def test_id_outside_the_format_is_one_violation(settings) -> None:
    """大文字・40 字超・先頭のハイフンのどれでも、違反が 1 件挙がる。"""
    for label, written in OUT_OF_FORMAT_IDS.items():
        copy = load_settings(settings.config_path)
        path = copy.path_for("public_records")
        text = path.read_text(encoding="utf-8")
        assert DUPLICATE_ID[0] in text, label
        path.write_text(text.replace(DUPLICATE_ID[0], f"- ID: {written}", 1), encoding="utf-8")

        violations = _id_violations(copy)
        assert len(violations) == 1, (label, [v.model_dump() for v in violations])
        assert "形に合わない" in violations[0].expected, label

        path.write_text(text, encoding="utf-8")


def test_renaming_a_heading_does_not_break_the_references(settings) -> None:
    """職歴の枠の見出しを書き換えても、ID がそのままなら違反は増えない。

    見出しの文字を写して結んでいたときは、改名が参照の切れになった。ID で結ぶと切れない。
    """
    before = len(ConsistencyService(settings).inspect().violations)
    assert before == 0

    _rewrite(settings.path_for("career"), f"## {CAREER_HEADING}", "## 2021-04〜 個人で受ける")

    report = ConsistencyService(settings).inspect()
    assert [v.model_dump() for v in report.violations] == []

    # 見出しを書き換えた節は、ID で引けたまま材料にも載る。
    material = MaterialService(settings).assemble(MaterialRequest(channel="tsukikusa"))
    listed = {entry["ID"]: entry["見出し"] for entry in material.evidence}
    assert listed.get(CAREER_ID) == "2021-04〜 個人で受ける", listed


def test_evidence_body_does_not_repeat_the_id_line(settings, alt_settings) -> None:
    """裏づけの本文から ID の行が落ちていて、ほかの欄の行は残っている。

    ID は鍵としても欄としても別に返しているので、本文にも残すと同じ値を 2 か所で受け取る。
    欄のラベルの言い方が違う 2 組目の見本でも、同じ 1 行が落ちることを見る。
    """
    for target in (settings, alt_settings):
        material = MaterialService(target).assemble(MaterialRequest(channel="tsukikusa"))
        assert material.evidence, target.config_path.name

        for entry in material.evidence:
            body = entry["本文"]
            name = target.config_path.name
            # ID の欄の行だけが落ちている（ラベルの言い方は正本ごとに違う）。
            assert entry["ID"] not in body, (name, body)
            for label in ("ID", "識別子"):
                assert f"- {label}:" not in body, (name, body)
            # ほかの欄の行は 1 つも落ちていない。
            assert "公開可否" in body, (name, body)
            assert "やったこと" in body or "内容" in body, (name, body)
            assert body.strip(), name


# ---------------------------------------------------------------- 候補の母集団が空


def test_no_candidate_material_when_nothing_is_readable(settings) -> None:
    """照らす相手が 1 件も読めていないときは、候補を出さずに材料が無いことを言う。

    ここで作るのは、設定の置き場がずれて職歴の枠も受託案件も 1 つも読めず、公開記録も
    使っていない正本である。書き間違いと「そもそも読めていない」を言い分けないと、
    正しい裏づけの側を書き換える誘導になる。
    """
    path: Path = settings.config_path
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [
        line
        for line in lines
        if not line.startswith(
            ("public_records = ", "public_record_kinds = ", "public_record_roles = ")
        )
    ]
    text = "\n".join(kept) + "\n"
    text = text.replace('career = "career.md"', 'career = "no_such_career.md"', 1)
    text = text.replace(
        'engagements = "engagements.md"', 'engagements = "no_such_engagements.md"', 1
    )
    path.write_text(text, encoding="utf-8")
    empty = load_settings(path)

    violations = _evidence_violations(empty)

    assert violations, "裏づけの違反が 1 件も出ていない"
    for violation in violations:
        assert "候補を出せる材料が無い" in violation.expected, violation.expected
        assert "読み方の絞り" in violation.expected, violation.expected
        assert violation.candidates == [], violation.candidates


# ---------------------------------------------------------------- 書きの操作の拒否


def test_register_capability_rejects_three_kinds_of_id(settings) -> None:
    """形の外の ID・既にある ID・実在しない裏づけの ID は、どれも書かずに拒否する。"""
    before = source_digest(settings.source_dir)
    service = OfferingService(settings)

    def draft(**changes) -> CapabilityDraft:
        values = {
            "id": "collect-milestones",
            "name": "工程の期日を 1 枚に集める",
            "description": "部署ごとに持っている予定を 1 枚にまとめ、遅れを早く見つける",
            "category": settings.capability_categories[2],
            "evidence_sections": [ENGAGEMENT_ID],
        }
        values.update(changes)
        return CapabilityDraft(**values)

    outside = service.register_capability(draft(id="Collect_Milestones"))
    assert outside.accepted is False
    assert outside.rejection is not None
    assert outside.rejection.constraint == ID_FORMAT_AND_UNIQUENESS
    assert "形に合わない" in outside.rejection.reason

    taken = service.register_capability(draft(id=ENGAGEMENT_ID))
    assert taken.accepted is False
    assert taken.rejection is not None
    assert taken.rejection.constraint == ID_FORMAT_AND_UNIQUENESS
    assert ENGAGEMENT_HEADING in taken.rejection.reason

    unknown = service.register_capability(draft(evidence_sections=["teramina-deliver"]))
    assert unknown.accepted is False
    assert unknown.rejection is not None
    assert unknown.rejection.constraint == EVIDENCE_SECTION_EXISTS

    # 候補はそのまま渡し直せる ID だけで、どの項目のことかは拒否の文が表示名で示す。
    for result in (outside, unknown):
        candidates = result.rejection.next_action.candidates
        assert _candidates_are_plain_ids(candidates), candidates
        assert "候補" in result.rejection.reason or "例にすると" in result.rejection.reason
        assert ENGAGEMENT_HEADING in result.rejection.reason, result.rejection.reason
    # 既にある ID は、渡し直せる代わりの値が無いので候補を出さず、使っている項目を文で言う。
    assert taken.rejection.next_action.candidates == []
    assert taken.rejection.next_action.example

    # どの拒否でも、正本のバイト列は 1 つも変わらない。
    assert source_digest(settings.source_dir) == before

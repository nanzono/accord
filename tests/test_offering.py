"""機能を登記する操作と、パッケージを改訂する操作のテスト。

要件 REQ-109〜156 を、1 本につき 1 件ずつ確かめる。通る道は、受け付ける語の出どころ、
裏づけにできる相手、通ったときに返り値へ入るもの、正本のどこが書き換わるかを見る。
断りは、返り値の欄ごとに 1 本ずつ——受け付けないこと、当たった制約の名前、理由、
次に呼ぶ操作の名前、候補（必須の欄だけは欠けた欄の名前）、書き方の例を見る。
すべて同梱のサンプルの一時的な写しの上で走らせる。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from accord.models.results import (
    CapabilityDraft,
    PackageDraft,
    Rejection,
    WriteResult,
)
from accord.repository.markdown_repository import MarkdownRepository
from accord.services.offering import OfferingService
from accord.vocabulary.settings import load_settings
from conftest import source_digest

# 設定を書き換えたときに使う、別人の語彙。コードには 1 行も現れない語にしてある。
OTHER_CATEGORIES = [
    "土台をならす",
    "見えるようにする",
    "段取りをつくる",
    "渡せるようにする",
    "人を増やす",
]

# 同梱のサンプルにある名前と ID。改訂のテストはこの節を土台にする。
# 節を探すのは見出し（表示名）、束ねる相手を指すのは ID なので、両方を持つ。
PACKAGE_NAME = "要件定義と進行管理"
PACKAGE_ID = "requirements-and-progress"
KNOWN_CAPABILITY = "requirements-forum"
KNOWN_CAPABILITY_NAME = "要件を決める場をつくる"
BUYER = "専任の進行役を置けない、従業員 100 名前後の会社の事業責任者"

# 公開記録を裏づけにするときの ID。公開記録は節ではないので、公開可否の欄を持たない。
PUBLIC_RECORD_ID = "meetup-talk-publishing"

# 受託案件の 1 件を公開不可にする書き換えと、その節の ID と表示名。
PRIVATE_SECTION_ID = "nagisa-publishing"
PRIVATE_SECTION_NAME = "ナギサ書房 刊行計画の進行管理"
MAKE_PRIVATE = (
    "- 公開可否: 公開可\n- 出所: 契約書と、月次の議事録（2025-04 以降）",
    "- 公開可否: 公開不可（先方の求めで、この案件は対外の文面に出さない）\n"
    "- 出所: 契約書と、月次の議事録（2025-04 以降）",
)

# 形は ID だが、正本のどこにも無い裏づけの節。近い節の表示名も持つ。
UNKNOWN_EVIDENCE_ID = "teramina-deliver"
CLOSE_EVIDENCE_NAME = "テラミナ物流"

# 機能の台帳に無い束ねる機能と、その近くにある実在の機能。
UNREGISTERED_CAPABILITY = "plan-from-decision"
CLOSE_CAPABILITY = "plan-from-decisions"
CLOSE_CAPABILITY_NAME = "決まったことを段取りに落とす"

# 渡した値が理由に書かれることだけを見るときに渡す、実在しない ID。
# 実在する ID の一部にならない綴りにする。一部になっていると、理由に値を書く行が無くなっても、
# 同じ理由に並ぶ候補の ID の中で当たってしまい、その行が消えたことに気づけない。
QUOTED_EVIDENCE_ID = "teramina-warehouse"
QUOTED_CAPABILITY = "plan-from-sketches"

# 設定の語の一覧に無い、仮説の状態。
UNKNOWN_HYPOTHESIS_STATE = "だいたい実績あり"

CONFIG_TEMPLATE = """[source]
directory = "source"

[source.files]
positioning = "positioning.md"
packages = "packages.md"
capabilities = "capabilities.md"
career = "career.md"
engagements = "engagements.md"
resume_ledger = "resume_ledger.md"
presentations = "presentations"
presentation_rules = "presentation_rules.md"

[vocabulary]
channels = ["tsukikusa", "nagiho"]
capability_categories = [{categories}]
package_hypothesis_states = ["仮説のみ", "検証中", "実績あり"]
"""


def _rewrite(path: Path, old: str, new: str) -> None:
    """写しの 1 か所を書き換える。狙った文字列が無ければ、テストの前提が崩れたとして落とす。"""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"写しに「{old}」が無い: {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _rewrite_categories(config_path: Path, categories: list[str]) -> None:
    """設定ファイルの分類の 5 節を、別の語に差し替える。"""
    listed = ", ".join(f'"{name}"' for name in categories)
    config_path.write_text(CONFIG_TEMPLATE.format(categories=listed), encoding="utf-8")


def _rejection_of(result: WriteResult) -> Rejection:
    """断りの欄を 1 つずつ見るテストが、返り値から断りを取り出す。"""
    assert result.accepted is False
    assert result.rejection is not None
    return result.rejection


def _record_evidence_draft(settings, **overrides) -> CapabilityDraft:
    """公開記録を裏づけにして機能を登記するときの入力。"""
    fields = {
        "id": "turn-talk-into-steps",
        "name": "話した内容を手順に落とす",
        "description": "勉強会で話した進め方を、そのまま使える手順に直す",
        "category": settings.capability_categories[2],
        "evidence_sections": [PUBLIC_RECORD_ID],
    }
    fields.update(overrides)
    return CapabilityDraft(**fields)


def _delivery_draft(settings, evidence: list[str]) -> CapabilityDraft:
    """裏づけの節だけを差し替えられる、登記の入力。"""
    return CapabilityDraft(
        id="collect-delivery-records",
        name="配送の実績を 1 か所に集める",
        description="拠点ごとに分かれた実績を 1 つの置き場に入れる",
        category=settings.capability_categories[0],
        evidence_sections=evidence,
    )


def _missing_fields_result(settings) -> WriteResult:
    """機能名と説明を空にして登記を試み、その返り値を返す。"""
    heading = MarkdownRepository(settings).load().section_headings()[0]
    return OfferingService(settings).register_capability(
        CapabilityDraft(
            id="collect-milestones",
            name="",
            description="",
            category=settings.capability_categories[0],
            evidence_sections=[heading],
        )
    )


def _old_category_result(sample_copy: Path) -> tuple[WriteResult, str]:
    """設定の分類を差し替えた後に、差し替え前の分類で登記を試み、返り値とその分類を返す。"""
    config_path = sample_copy / "accord.toml"
    before = load_settings(config_path)
    old_category = before.capability_categories[0]
    _rewrite_categories(config_path, OTHER_CATEGORIES)
    after = load_settings(config_path)
    heading = MarkdownRepository(after).load().section_headings()[-1]
    result = OfferingService(after).register_capability(
        CapabilityDraft(
            id="align-storage",
            name="置き場をそろえる",
            description="分かれている数字を 1 か所に集める",
            category=old_category,
            evidence_sections=[heading],
        )
    )
    return result, old_category


def _unknown_evidence_result(settings) -> WriteResult:
    """正本のどこにも無い ID を裏づけにして登記を試み、その返り値を返す。"""
    return OfferingService(settings).register_capability(
        _delivery_draft(settings, [UNKNOWN_EVIDENCE_ID])
    )


def _revise_the_known_package(settings) -> WriteResult:
    """同梱の見本にある束を、束ねる機能を 1 つ足して改訂する。"""
    return OfferingService(settings).revise_package(
        PackageDraft(
            id=PACKAGE_ID,
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY, CLOSE_CAPABILITY],
            buyer=BUYER,
            hypothesis_state=settings.package_hypothesis_states[2],
            basis="受注 2 件がどちらも継続している。",
        )
    )


def _known_package(settings):
    """パッケージ定義を読み直し、見本にある束の節を返す。"""
    return next(
        item
        for item in MarkdownRepository(settings).load().packages
        if item.name == PACKAGE_NAME
    )


def _unregistered_capability_result(settings) -> WriteResult:
    """機能の台帳に無い ID を束ねて改訂を試み、その返り値を返す。"""
    return OfferingService(settings).revise_package(
        PackageDraft(
            id=PACKAGE_ID,
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY, UNREGISTERED_CAPABILITY],
            buyer=BUYER,
            hypothesis_state=settings.package_hypothesis_states[1],
        )
    )


def _hypothesis_state_result(settings) -> WriteResult:
    """設定の語の一覧に無い仮説の状態で改訂を試み、その返り値を返す。"""
    return OfferingService(settings).revise_package(
        PackageDraft(
            id=PACKAGE_ID,
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY],
            buyer=BUYER,
            hypothesis_state=UNKNOWN_HYPOTHESIS_STATE,
        )
    )


# ---------------------------------------------------------------- 登記が通る道


def test_REQ_109_capability_categories_come_from_settings(sample_copy: Path) -> None:
    """分類の 5 節を設定で差し替えると、受け付ける分類もコードを直さずに変わる。"""
    config_path = sample_copy / "accord.toml"
    before = load_settings(config_path)
    old_category = before.capability_categories[0]
    assert old_category not in OTHER_CATEGORIES

    _rewrite_categories(config_path, OTHER_CATEGORIES)
    after = load_settings(config_path)
    assert after.capability_categories == OTHER_CATEGORIES

    heading = MarkdownRepository(after).load().section_headings()[-1]
    accepted = OfferingService(after).register_capability(
        CapabilityDraft(
            id="collect-milestones",
            name="工程の期日を 1 枚に集める",
            description="部署ごとに持っている予定を 1 枚にまとめ、遅れを早く見つける",
            category=OTHER_CATEGORIES[2],
            evidence_sections=[heading],
        )
    )
    assert accepted.accepted is True, accepted.model_dump()
    assert OTHER_CATEGORIES[2] in after.path_for("capabilities").read_text(encoding="utf-8")


def test_REQ_110_register_capability_accepts_a_public_record_as_evidence(settings) -> None:
    """機能を登記する操作は、公開記録の ID を裏づけに取る。"""
    accepted = OfferingService(settings).register_capability(_record_evidence_draft(settings))

    assert accepted.accepted is True, accepted.model_dump()


def test_REQ_111_rejected_candidate_is_accepted_when_passed_back(settings) -> None:
    """返ってきた候補をそのまま裏づけに渡し直すと、今度は受け付けられる。"""
    rejected = _unknown_evidence_result(settings)
    assert rejected.rejection is not None

    retried = OfferingService(settings).register_capability(
        _delivery_draft(settings, [rejected.rejection.next_action.candidates[0]])
    )

    assert retried.accepted is True, retried.model_dump()


def test_REQ_112_accepted_capability_records_the_disclosure_of_its_evidence(settings) -> None:
    """登記が通ると、裏づけの節ごとの公開可否が返り値に入る。"""
    rejected = _unknown_evidence_result(settings)
    assert rejected.rejection is not None

    retried = OfferingService(settings).register_capability(
        _delivery_draft(settings, [rejected.rejection.next_action.candidates[0]])
    )

    assert "裏づけの節の公開可否" in retried.recorded


def test_REQ_113_public_record_evidence_is_named_as_such_in_the_disclosure(settings) -> None:
    """裏づけが公開記録の節は、公開可否の欄に公開記録であることが書かれる。"""
    accepted = OfferingService(settings).register_capability(_record_evidence_draft(settings))

    assert accepted.accepted is True, accepted.model_dump()
    disclosure = accepted.recorded["裏づけの節の公開可否"]
    assert len(disclosure) == 1, disclosure
    # 公開記録は公開可否の欄を持たないので、「不明」ではなく公開記録であることを書く。
    assert "公開記録" in next(iter(disclosure.values())), disclosure


def test_REQ_114_private_evidence_of_a_registered_capability_is_named_in_a_warning(
    settings,
) -> None:
    """公開不可の節を裏づけに登記すると、対外の文面に出せないことを節の名前つきで断る。"""
    _rewrite(settings.path_for("engagements"), *MAKE_PRIVATE)

    accepted = OfferingService(settings).register_capability(
        _record_evidence_draft(settings, evidence_sections=[PRIVATE_SECTION_ID])
    )

    assert accepted.accepted is True, accepted.model_dump()
    listed = "\n".join(accepted.warnings)
    assert PRIVATE_SECTION_NAME in listed, listed
    assert "出せない" in listed, listed


# ---------------------------------------------------------------- 登記の断り（必須の欄）


def test_REQ_115_missing_required_fields_are_not_registered(settings) -> None:
    """機能名と説明を空にすると、その機能を登記しない。"""
    before = source_digest(settings.source_dir)

    result = _missing_fields_result(settings)

    assert result.accepted is False
    assert result.rejection is not None
    # 拒否のときは正本のバイト列が 1 つも変わらない。
    assert source_digest(settings.source_dir) == before


def test_REQ_116_missing_required_fields_rejection_names_the_constraint(settings) -> None:
    """必須の欄が空のときの断りは、当たった制約の名前を返す。"""
    rejection = _rejection_of(_missing_fields_result(settings))

    assert rejection.constraint == "機能の必須欄"


def test_REQ_117_missing_required_fields_rejection_names_them_in_the_reason(settings) -> None:
    """必須の欄が空のときの断りは、欠けた欄の名前を理由に書く。"""
    rejection = _rejection_of(_missing_fields_result(settings))

    assert "機能名" in rejection.reason, rejection.reason
    assert "説明" in rejection.reason, rejection.reason


def test_REQ_118_missing_required_fields_rejection_names_the_next_operation(settings) -> None:
    """必須の欄が空のときの断りは、次に呼ぶ操作の名前を返す。"""
    next_action = _rejection_of(_missing_fields_result(settings)).next_action

    assert next_action.operation == "register_capability"


def test_REQ_119_missing_required_fields_rejection_lists_the_missing_fields(settings) -> None:
    """必須の欄が空のときの断りは、欠けた欄の名前の一覧を返す。"""
    next_action = _rejection_of(_missing_fields_result(settings)).next_action

    assert next_action.missing_fields == ["機能名", "説明"]


def test_REQ_120_missing_required_fields_rejection_shows_how_to_write_them(settings) -> None:
    """必須の欄が空のときの断りは、欠けた欄の書き方の例を返す。"""
    next_action = _rejection_of(_missing_fields_result(settings)).next_action

    assert "機能名" in next_action.example
    assert "説明" in next_action.example


# ---------------------------------------------------------------- 登記の断り（分類）


def test_REQ_121_category_outside_the_settings_is_not_registered(sample_copy: Path) -> None:
    """設定の分類の一覧に無い分類では、その機能を登記しない。"""
    rejected, _ = _old_category_result(sample_copy)

    assert rejected.accepted is False
    assert rejected.rejection is not None


def test_REQ_122_category_rejection_names_the_constraint(sample_copy: Path) -> None:
    """分類が設定の一覧に無いときの断りは、当たった制約の名前を返す。"""
    rejected, _ = _old_category_result(sample_copy)

    assert _rejection_of(rejected).constraint == "機能の分類の列挙"


def test_REQ_123_category_rejection_quotes_the_given_category(sample_copy: Path) -> None:
    """分類が設定の一覧に無いときの断りは、渡された分類を理由に書く。"""
    rejected, old_category = _old_category_result(sample_copy)

    assert old_category in _rejection_of(rejected).reason


def test_REQ_124_category_rejection_names_the_next_operation(sample_copy: Path) -> None:
    """分類が設定の一覧に無いときの断りは、次に呼ぶ操作の名前を返す。"""
    rejected, _ = _old_category_result(sample_copy)

    assert _rejection_of(rejected).next_action.operation == "register_capability"


def test_REQ_125_category_rejection_lists_the_settings_categories(sample_copy: Path) -> None:
    """分類が設定の一覧に無いときの断りは、設定の分類の一覧を候補に返す。"""
    rejected, _ = _old_category_result(sample_copy)

    assert rejected.rejection is not None
    assert rejected.rejection.next_action.candidates == OTHER_CATEGORIES


def test_REQ_126_category_rejection_shows_how_to_pass_a_candidate(sample_copy: Path) -> None:
    """分類が設定の一覧に無いときの断りは、候補をそのまま渡す書き方の例を返す。"""
    rejected, _ = _old_category_result(sample_copy)

    assert OTHER_CATEGORIES[0] in _rejection_of(rejected).next_action.example


# ---------------------------------------------------------------- 登記の断り（裏づけの節）


def test_REQ_127_unknown_evidence_section_is_not_registered(settings) -> None:
    """実在しない ID を裏づけにすると、その機能を登記しない。"""
    before = source_digest(settings.source_dir)

    result = _unknown_evidence_result(settings)

    assert result.accepted is False
    assert result.rejection is not None
    # 拒否のときは正本のバイト列が 1 つも変わらない。
    assert source_digest(settings.source_dir) == before


def test_REQ_128_unknown_evidence_rejection_names_the_constraint(settings) -> None:
    """裏づけの節が実在しないときの断りは、当たった制約の名前を返す。"""
    rejection = _rejection_of(_unknown_evidence_result(settings))

    assert rejection.constraint == "裏づけ節名の実在"


def test_REQ_129_unknown_evidence_rejection_quotes_the_given_id(settings) -> None:
    """裏づけの節が実在しないときの断りは、渡された ID を理由に書く。"""
    rejection = _rejection_of(
        OfferingService(settings).register_capability(
            _delivery_draft(settings, [QUOTED_EVIDENCE_ID])
        )
    )

    assert QUOTED_EVIDENCE_ID in rejection.reason, rejection.reason


def test_REQ_130_unknown_evidence_rejection_names_the_candidates_in_words(settings) -> None:
    """裏づけの節が実在しないときの断りは、候補の表示名を理由に書く。"""
    rejection = _rejection_of(_unknown_evidence_result(settings))

    assert CLOSE_EVIDENCE_NAME in rejection.reason, rejection.reason


def test_REQ_131_unknown_evidence_rejection_names_the_public_records(settings) -> None:
    """どこにも無い ID を裏づけにしたときの断りは、公開記録にも無いことを理由に書く。"""
    rejected = OfferingService(settings).register_capability(
        _record_evidence_draft(settings, evidence_sections=["nowhere-at-all"])
    )

    assert rejected.accepted is False
    assert rejected.rejection is not None
    assert "公開記録" in rejected.rejection.reason


def test_REQ_132_unknown_evidence_rejection_names_the_next_operation(settings) -> None:
    """裏づけの節が実在しないときの断りは、次に呼ぶ操作の名前を返す。"""
    rejection = _rejection_of(_unknown_evidence_result(settings))

    assert rejection.next_action.operation == "register_capability"


def test_REQ_133_unknown_evidence_rejection_lists_existing_ids(settings) -> None:
    """裏づけの節が実在しないときの断りは、そのまま渡せる実在の ID を候補に返す。"""
    headings = MarkdownRepository(settings).load().section_headings()

    candidates = _rejection_of(_unknown_evidence_result(settings)).next_action.candidates

    assert candidates, "近い ID の候補が 1 つ以上返ること"
    # 候補はそのまま渡せる ID だけで、どの節かは拒否の文が表示名で示す。
    assert all(candidate in headings for candidate in candidates), "候補はそのまま渡せる ID"


def test_REQ_134_unknown_evidence_rejection_shows_how_to_pass_a_candidate(settings) -> None:
    """裏づけの節が実在しないときの断りは、候補を渡して呼び直す書き方の例を返す。"""
    example = _rejection_of(_unknown_evidence_result(settings)).next_action.example

    assert "裏づけの節" in example, example
    assert "register_capability" in example, example


# ---------------------------------------------------------------- 改訂が通る道


def test_REQ_135_revise_package_replaces_the_section_of_the_same_name(settings) -> None:
    """既にある名前の改訂は、節を増やさずにその名前の節の中身を差し替える。"""
    packages = settings.path_for("packages")
    before_sections = packages.read_text(encoding="utf-8").count("\n## ")

    result = _revise_the_known_package(settings)

    assert result.accepted is True, result.model_dump()
    assert result.recorded["新しい節か"] is False
    # 節は増えず、中身が差し替わる。
    text = packages.read_text(encoding="utf-8")
    assert text.count("\n## ") == before_sections
    assert text.count(f"\n## {PACKAGE_NAME}\n") == 1


def test_REQ_136_revise_package_adds_a_section_for_a_new_name(settings) -> None:
    """その名前の節が無いときは、新しい節を足す。"""
    packages = settings.path_for("packages")
    before_sections = packages.read_text(encoding="utf-8").count("\n## ")

    result = OfferingService(settings).revise_package(
        PackageDraft(
            id="handover-in-one",
            name="引き継ぎまでを 1 本で受ける",
            capabilities=[KNOWN_CAPABILITY],
            buyer="担当者が 1 人で回している会社の事業責任者",
            hypothesis_state=settings.package_hypothesis_states[0],
        )
    )

    assert result.accepted is True, result.model_dump()
    assert result.recorded["新しい節か"] is True
    assert packages.read_text(encoding="utf-8").count("\n## ") == before_sections + 1
    names = [item.name for item in MarkdownRepository(settings).load().packages]
    assert "引き継ぎまでを 1 本で受ける" in names


def test_REQ_137_revise_package_writes_the_id_state_and_capabilities(settings) -> None:
    """通る改訂は、渡された ID と仮説の状態と束ねる機能を、パッケージ定義に書く。"""
    result = _revise_the_known_package(settings)

    assert result.accepted is True, result.model_dump()
    package = _known_package(settings)
    assert package.hypothesis_state == settings.package_hypothesis_states[2]
    assert package.id == PACKAGE_ID
    assert package.capabilities == [KNOWN_CAPABILITY, CLOSE_CAPABILITY]


def test_REQ_138_revise_package_advances_the_update_date(settings) -> None:
    """通る改訂は、そのパッケージの最終更新日を今日に進める。"""
    result = _revise_the_known_package(settings)

    assert result.accepted is True, result.model_dump()
    assert result.recorded["最終更新"] == date.today().isoformat()
    assert _known_package(settings).updated_on == date.today()


def test_REQ_139_revise_package_carries_over_the_breaking_condition(settings) -> None:
    """入力が持たない欄（崩れる条件）は、前の定義の値をそのまま残す。"""
    result = _revise_the_known_package(settings)

    assert result.accepted is True, result.model_dump()
    assert _known_package(settings).breaks_when


def test_REQ_140_carried_over_breaking_condition_is_named_in_a_warning(settings) -> None:
    """崩れる条件を前の定義から残したことを、警告に書く。"""
    result = _revise_the_known_package(settings)

    assert result.accepted is True, result.model_dump()
    assert any("崩れる条件" in warning for warning in result.warnings), result.warnings


def test_REQ_141_revise_package_carries_over_the_basis_and_the_source(settings) -> None:
    """判定根拠と出典を渡さない改訂は、前の定義のその欄の値をそのまま残す。"""
    before = _known_package(settings)
    assert before.basis and before.source

    result = OfferingService(settings).revise_package(
        PackageDraft(
            id=PACKAGE_ID,
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY],
            buyer=BUYER,
            hypothesis_state=settings.package_hypothesis_states[2],
        )
    )

    assert result.accepted is True, result.model_dump()
    after = _known_package(settings)
    assert after.basis == before.basis
    assert after.source == before.source


def test_REQ_142_carried_over_basis_and_source_are_named_in_a_warning(settings) -> None:
    """判定根拠と出典を前の定義から残したことを、その欄の名前を添えて警告に書く。"""
    result = OfferingService(settings).revise_package(
        PackageDraft(
            id=PACKAGE_ID,
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY],
            buyer=BUYER,
            hypothesis_state=settings.package_hypothesis_states[2],
        )
    )

    assert result.accepted is True, result.model_dump()
    listed = "\n".join(result.warnings)
    assert "判定根拠" in listed, listed
    assert "出典" in listed, listed


def test_REQ_143_revised_package_accepts_the_returned_candidate(settings) -> None:
    """返ってきた候補をそのまま束ねる機能に渡し直すと、今度は受け付けられる。"""
    rejected = _unregistered_capability_result(settings)
    assert rejected.rejection is not None

    # 返ってきた候補をそのまま渡し直すと、今度は受け付けられる。
    retried = OfferingService(settings).revise_package(
        PackageDraft(
            id=PACKAGE_ID,
            name=PACKAGE_NAME,
            capabilities=[KNOWN_CAPABILITY, rejected.rejection.next_action.candidates[0]],
            buyer=BUYER,
            hypothesis_state=settings.package_hypothesis_states[1],
        )
    )

    assert retried.accepted is True, retried.model_dump()


# ---------------------------------------------------------------- 改訂の断り（束ねる機能）


def test_REQ_144_unregistered_capability_is_not_revised(settings) -> None:
    """機能の台帳に無い名前を束ねると、そのパッケージを改訂しない。"""
    before = source_digest(settings.source_dir)

    result = _unregistered_capability_result(settings)

    assert result.accepted is False
    assert result.rejection is not None
    # 拒否のときは正本のバイト列が 1 つも変わらない。
    assert source_digest(settings.source_dir) == before


def test_REQ_145_unregistered_capability_rejection_names_the_constraint(settings) -> None:
    """束ねる機能が台帳に無いときの断りは、当たった制約の名前を返す。"""
    rejection = _rejection_of(_unregistered_capability_result(settings))

    assert rejection.constraint == "束ねる機能名の一致"


def test_REQ_146_unregistered_capability_rejection_quotes_the_given_id(settings) -> None:
    """束ねる機能が台帳に無いときの断りは、渡された ID を理由に書く。"""
    rejection = _rejection_of(
        OfferingService(settings).revise_package(
            PackageDraft(
                id=PACKAGE_ID,
                name=PACKAGE_NAME,
                capabilities=[KNOWN_CAPABILITY, QUOTED_CAPABILITY],
                buyer=BUYER,
                hypothesis_state=settings.package_hypothesis_states[1],
            )
        )
    )

    assert QUOTED_CAPABILITY in rejection.reason, rejection.reason


def test_REQ_147_unregistered_capability_rejection_names_the_candidates_in_words(
    settings,
) -> None:
    """束ねる機能が台帳に無いときの断りは、候補の表示名を理由に書く。"""
    rejection = _rejection_of(_unregistered_capability_result(settings))

    assert CLOSE_CAPABILITY_NAME in rejection.reason, rejection.reason


def test_REQ_148_unregistered_capability_rejection_names_the_next_operation(settings) -> None:
    """束ねる機能が台帳に無いときの断りは、次に呼ぶ操作の名前を返す。"""
    rejection = _rejection_of(_unregistered_capability_result(settings))

    assert rejection.next_action.operation == "revise_package"


def test_REQ_149_unregistered_capability_rejection_lists_close_ids(settings) -> None:
    """束ねる機能が台帳に無いときの断りは、台帳にある近い ID を候補に返す。"""
    next_action = _rejection_of(_unregistered_capability_result(settings)).next_action

    assert CLOSE_CAPABILITY in next_action.candidates, next_action.candidates


def test_REQ_150_unregistered_capability_rejection_says_to_register_first(settings) -> None:
    """束ねる機能が台帳に無いときの断りは、先に機能を登記する操作の名前を書き方の例に入れる。"""
    next_action = _rejection_of(_unregistered_capability_result(settings)).next_action

    assert "register_capability" in next_action.example, next_action.example


# ---------------------------------------------------------------- 改訂の断り（仮説の状態）


def test_REQ_151_hypothesis_state_outside_the_settings_is_not_revised(settings) -> None:
    """仮説の状態が設定の語に無いときは、そのパッケージを改訂しない。"""
    before = source_digest(settings.source_dir)

    result = _hypothesis_state_result(settings)

    assert result.accepted is False
    assert result.rejection is not None
    assert source_digest(settings.source_dir) == before


def test_REQ_152_hypothesis_state_rejection_names_the_constraint(settings) -> None:
    """仮説の状態が設定の語に無いときの断りは、当たった制約の名前を返す。"""
    rejection = _rejection_of(_hypothesis_state_result(settings))

    assert rejection.constraint == "仮説の状態の列挙"


def test_REQ_153_hypothesis_state_rejection_quotes_the_given_word(settings) -> None:
    """仮説の状態が設定の語に無いときの断りは、渡された語を理由に書く。"""
    rejection = _rejection_of(_hypothesis_state_result(settings))

    assert UNKNOWN_HYPOTHESIS_STATE in rejection.reason, rejection.reason


def test_REQ_154_hypothesis_state_rejection_names_the_next_operation(settings) -> None:
    """仮説の状態が設定の語に無いときの断りは、次に呼ぶ操作の名前を返す。"""
    rejection = _rejection_of(_hypothesis_state_result(settings))

    assert rejection.next_action.operation == "revise_package"


def test_REQ_155_hypothesis_state_rejection_lists_the_settings_words(settings) -> None:
    """仮説の状態が設定の語に無いときの断りは、設定の語の一覧を候補に返す。"""
    result = _hypothesis_state_result(settings)

    assert result.rejection is not None
    assert result.rejection.next_action.candidates == settings.package_hypothesis_states


def test_REQ_156_hypothesis_state_rejection_shows_how_to_pass_a_candidate(settings) -> None:
    """仮説の状態が設定の語に無いときの断りは、候補をそのまま渡す書き方の例を返す。"""
    example = _rejection_of(_hypothesis_state_result(settings)).next_action.example

    assert settings.package_hypothesis_states[0] in example, example


# ---------------------------------------------------------------- 制約を見る順


# 制約を同時に崩すときに渡す、形の外の ID と、設定の節に無い分類。
OUT_OF_FORMAT_ID = "Collect_Milestones"
UNKNOWN_CATEGORY = "思いつきの分類"


def test_REQ_320_only_the_first_broken_rule_is_returned_when_registering_a_capability(
    settings,
) -> None:
    """機能の登記は、必須の欄・分類・ID・裏づけの節の順で、先に当たった 1 件だけを返す。

    後ろの段から 1 つずつ前の段を崩していき、返る断りが前の段のものに入れ替わることを見る。
    順を入れ替えると、崩した段より後ろの断りが返って落ちる。
    """
    service = OfferingService(settings)

    def draft(**changes) -> CapabilityDraft:
        values = {
            "id": "collect-milestones",
            "name": "工程の期日を 1 枚に集める",
            "description": "部署ごとに持っている予定を 1 枚にまとめ、遅れを早く見つける",
            "category": settings.capability_categories[2],
            "evidence_sections": [UNKNOWN_EVIDENCE_ID],
        }
        values.update(changes)
        return CapabilityDraft(**values)

    # 裏づけの節だけが正本に無い ID なら、いちばん後に見る裏づけの節の断りが返る。
    evidence_only = service.register_capability(draft())
    assert _rejection_of(evidence_only).constraint == "裏づけ節名の実在"

    # ID も形の外にすると、裏づけの節より先に見る ID の断りが返る。
    with_id = service.register_capability(draft(id=OUT_OF_FORMAT_ID))
    assert _rejection_of(with_id).constraint == "ID の形式と一意性"

    # 分類も設定の節の外にすると、ID より先に見る分類の断りが返る。
    with_category = service.register_capability(
        draft(id=OUT_OF_FORMAT_ID, category=UNKNOWN_CATEGORY)
    )
    assert _rejection_of(with_category).constraint == "機能の分類の列挙"

    # 必須の欄も欠くと、分類より先に見る必須の欄の断りが返る。
    with_missing = service.register_capability(
        draft(id=OUT_OF_FORMAT_ID, category=UNKNOWN_CATEGORY, name="", description="")
    )
    assert _rejection_of(with_missing).constraint == "機能の必須欄"


def test_REQ_321_only_the_first_broken_rule_is_returned_when_revising_a_package(
    settings,
) -> None:
    """パッケージの改訂は、必須の欄・ID・仮説の状態・束ねる機能の順で、先の 1 件だけを返す。"""
    service = OfferingService(settings)

    def draft(**changes) -> PackageDraft:
        values = {
            "id": PACKAGE_ID,
            "name": PACKAGE_NAME,
            "capabilities": [UNREGISTERED_CAPABILITY],
            "buyer": BUYER,
            "hypothesis_state": settings.package_hypothesis_states[1],
        }
        values.update(changes)
        return PackageDraft(**values)

    # 束ねる機能だけが台帳に無い ID なら、いちばん後に見る束ねる機能の断りが返る。
    capability_only = service.revise_package(draft())
    assert _rejection_of(capability_only).constraint == "束ねる機能名の一致"

    # 仮説の状態も設定の語の外にすると、束ねる機能より先に見る仮説の状態の断りが返る。
    with_state = service.revise_package(draft(hypothesis_state=UNKNOWN_HYPOTHESIS_STATE))
    assert _rejection_of(with_state).constraint == "仮説の状態の列挙"

    # ID も形の外にすると、仮説の状態より先に見る ID の断りが返る。
    with_id = service.revise_package(
        draft(id=OUT_OF_FORMAT_ID, hypothesis_state=UNKNOWN_HYPOTHESIS_STATE)
    )
    assert _rejection_of(with_id).constraint == "ID の形式と一意性"

    # 必須の欄も欠くと、ID より先に見る必須の欄の断りが返る。
    with_missing = service.revise_package(
        draft(id=OUT_OF_FORMAT_ID, hypothesis_state=UNKNOWN_HYPOTHESIS_STATE, buyer="")
    )
    assert _rejection_of(with_missing).constraint == "パッケージの必須欄"

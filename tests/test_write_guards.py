"""書きの操作 4 つに共通の、2 つの約束を確かめる。

1 つは、拒否の返り値が必ず「次に何をすべきか」を持つこと。何が悪いかだけを返すと、
受け取った側は正本を読み直して直し方を自分で探す羽目になり、規則が行動の瞬間に効かない。
もう 1 つは、拒否のときに正本のバイト列が 1 つも変わらないこと。

到達できる拒否の経路を、4 つの操作ぶんすべて並べて回す。経路を 1 つ足したら、この表に 1 行足す。
"""

from __future__ import annotations

from datetime import date

import pytest

from accord.models.results import (
    CapabilityDraft,
    PackageDraft,
    PositioningDraft,
    PublicRecordDraft,
    WriteResult,
)
from accord.services.offering import OfferingService
from accord.services.positioning import PositioningService
from accord.services.public_records import PublicRecordService
from accord.vocabulary.settings import Settings
from conftest import source_digest

# 同梱のサンプルにある名前。通る入力の土台にして、1 か所だけ崩す。
HEADLINE_PACKAGE = "要件定義と進行管理"
KNOWN_CAPABILITY = "要件を決める場をつくる"
KNOWN_SECTION = "ナギサ書房 刊行計画の進行管理"
BUYER = "専任の進行役を置けない会社の事業責任者"
RATIONALE = "直近の引き合いが、作る前の整理に集中していたため。"


def _record(settings: Settings, **changes) -> WriteResult:
    """通る決めの入力を土台に、渡された欄だけを差し替えて登記を呼ぶ。"""
    draft = {
        "decided_on": date(2026, 9, 16),
        "scope": "全体",
        "headline_package": HEADLINE_PACKAGE,
        "rationale": RATIONALE,
    }
    draft.update(changes)
    return PositioningService(settings).record(PositioningDraft(**draft))


def _register(settings: Settings, **changes) -> WriteResult:
    """通る機能の入力を土台に、渡された欄だけを差し替えて登記を呼ぶ。"""
    draft = {
        "name": "工程の期日を 1 枚に集める",
        "description": "部署ごとに持っている予定を 1 枚にまとめ、遅れを早く見つける",
        "category": settings.capability_categories[2],
        "evidence_sections": [KNOWN_SECTION],
    }
    draft.update(changes)
    return OfferingService(settings).register_capability(CapabilityDraft(**draft))


def _register_record(settings: Settings, **changes) -> WriteResult:
    """通る公開記録の入力を土台に、渡された欄だけを差し替えて登記を呼ぶ。"""
    draft = {
        "name": "配送データの集約を話した勉強会の発表",
        "kind": settings.public_record_kinds[1],
        "published_on": "2026-03-14",
        "url": "https://example.com/events/report/data-meetup/",
        "publisher": "データの置き場づくりを持ち寄る勉強会（架空の催し）",
        "role": settings.public_record_roles[0],
        "origin_section": KNOWN_SECTION,
    }
    draft.update(changes)
    return PublicRecordService(settings).register(PublicRecordDraft(**draft))


def _revise(settings: Settings, **changes) -> WriteResult:
    """通るパッケージの入力を土台に、渡された欄だけを差し替えて改訂を呼ぶ。"""
    draft = {
        "name": HEADLINE_PACKAGE,
        "capabilities": [KNOWN_CAPABILITY],
        "buyer": BUYER,
        "hypothesis_state": settings.package_hypothesis_states[1],
    }
    draft.update(changes)
    return OfferingService(settings).revise_package(PackageDraft(**draft))


# 到達できる拒否の経路の全部。名前は、何を崩したかで読めるようにする。
REJECTION_PATHS = {
    "決めの日付が無い": lambda settings: _record(settings, decided_on=None),
    "決めの根拠が無い": lambda settings: _record(settings, rationale=""),
    "決めの適用範囲が媒体でも全体でもない": lambda settings: _record(settings, scope="どこか"),
    "決めの束がパッケージ定義に無い": lambda settings: _record(
        settings, headline_package="要件定義と進こう管理"
    ),
    "機能の名前と説明が無い": lambda settings: _register(settings, name="", description=""),
    "機能の分類が設定の節に無い": lambda settings: _register(settings, category="思いつきの分類"),
    "機能の裏づけの節が 1 つも無い": lambda settings: _register(settings, evidence_sections=[]),
    "機能の裏づけの節が実在しない": lambda settings: _register(
        settings, evidence_sections=["ナギサ書房 刊行計画の進こう管理"]
    ),
    "パッケージの想定買い手が無い": lambda settings: _revise(settings, buyer=""),
    "パッケージが束ねる機能が 1 つも無い": lambda settings: _revise(settings, capabilities=[]),
    "パッケージの仮説の状態が設定の語に無い": lambda settings: _revise(
        settings, hypothesis_state="だいたい実績あり"
    ),
    "パッケージが束ねる機能が台帳に無い": lambda settings: _revise(
        settings, capabilities=["要件を決める場をつくらない"]
    ),
    "公開記録の名前と役割が無い": lambda settings: _register_record(settings, name="", role=""),
    "公開記録の種類が設定の語に無い": lambda settings: _register_record(
        settings, kind="ポッドキャスト"
    ),
    "公開記録の役割が設定の語に無い": lambda settings: _register_record(settings, role="司会"),
    "公開記録の由来の節が実在しない": lambda settings: _register_record(
        settings, origin_section="ナギサ書房 刊行計画の進こう管理"
    ),
}


@pytest.mark.parametrize("path", sorted(REJECTION_PATHS))
def test_every_rejection_names_the_next_action(settings: Settings, path: str) -> None:
    """どの拒否も、次に何をすべきかの欄を持ち、その欄が空でない。"""
    result = REJECTION_PATHS[path](settings)

    assert result.accepted is False, path
    assert result.rejection is not None, path

    next_action = result.rejection.next_action
    assert next_action.operation, f"{path}: 次に呼ぶ操作の名前が空"
    # 欠けた欄・候補・書き方の例のうち、少なくとも 1 つは埋まっていること。
    # 3 つとも空だと「次に何をすべきか」が操作の名前だけになり、呼び直せない。
    assert (
        next_action.missing_fields or next_action.candidates or next_action.example
    ), f"{path}: 次の一手の中身が空"
    assert result.rejection.reason, f"{path}: 何が通らなかったかが空"


@pytest.mark.parametrize("path", sorted(REJECTION_PATHS))
def test_rejected_write_leaves_source_untouched(settings: Settings, path: str) -> None:
    """拒否のあと、正本のディレクトリ配下の全ファイルのバイト列が呼び出しの前と一致する。"""
    before = source_digest(settings.source_dir)

    result = REJECTION_PATHS[path](settings)

    assert result.accepted is False, path
    assert source_digest(settings.source_dir) == before, path

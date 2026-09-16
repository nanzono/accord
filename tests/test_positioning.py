"""いまの決めを読む操作と、決めを登記する操作のテスト。

読みは、どの決めが当たるか、決めが 1 件も無いとき、媒体の名前が実在しないときの 3 つを見る。
書きは、必須欄の拒否、通る登記でブロックが 1 つ増えて 2 つの検査が返ること、束の名前が
実在しないときの候補を見る。すべて同梱のサンプルの一時的な写しの上で走らせる。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from accord.models.results import PositioningDraft
from accord.services.positioning import PositioningService
from conftest import source_digest

# 同梱のサンプルが持つ決め。日付の新しいほうが、いまの看板になる。
LATEST_DECISION = "2026-09-10"
LATEST_HEADLINE = "要件定義と進行管理"
OLDER_HEADLINE = "データの置き場づくり"

# 写しに足す、媒体を名指しした決め。「全体」より優先される。
CHANNEL_DECISION = """
## 2026-09-11 nagiho

- 日付: 2026-09-11
- 適用範囲: nagiho
- 前面に出す束: データの置き場づくり
- 根拠: この媒体は数字の置き場づくりの相談が多く、進行の側では引き合いが付かなかったため。
- 例外: なし
"""


def _view(settings, channel: str | None = None):
    """写しの正本から、いまの決めを読む。"""
    return PositioningService(settings).current(channel)


def test_get_positioning_returns_the_latest_whole_scope_decision(settings) -> None:
    """媒体を省くと、適用範囲「全体」の最新の 1 件と、その束のパッケージが返る。"""
    before = source_digest(settings.source_dir)

    view = _view(settings)

    assert view.positioning is not None
    assert str(view.positioning.decided_on) == LATEST_DECISION
    assert view.positioning.headline_package == LATEST_HEADLINE
    # 束のパッケージが、想定買い手つきで添えられている。
    assert view.package is not None
    assert view.package.name == LATEST_HEADLINE
    assert view.package.buyer
    assert view.warnings == []
    # 読みの操作なので、正本は 1 バイトも変わらない。
    assert source_digest(settings.source_dir) == before


def test_get_positioning_prefers_the_decision_named_for_the_channel(settings) -> None:
    """媒体を名指しした決めがあればそれを返し、無ければ「全体」の決めを返す。"""
    positioning = settings.path_for("positioning")
    positioning.write_text(
        positioning.read_text(encoding="utf-8") + CHANNEL_DECISION, encoding="utf-8"
    )

    named = _view(settings, "nagiho")
    assert named.positioning is not None
    assert named.positioning.scope == "nagiho"
    assert named.positioning.headline_package == OLDER_HEADLINE

    # 名指しの決めが無い媒体は、「全体」の決めに落ちる。落ちたことを断りに書く。
    fallback = _view(settings, "tsukikusa")
    assert fallback.positioning is not None
    assert fallback.positioning.scope == "全体"
    assert fallback.positioning.headline_package == LATEST_HEADLINE
    assert any("全体" in warning for warning in fallback.warnings), fallback.warnings


def test_get_positioning_says_the_decision_is_unrecorded(settings) -> None:
    """決めが 1 件も無いときは、未登記であることと、先に登記することを返す。"""
    positioning = settings.path_for("positioning")
    header, _, _ = positioning.read_text(encoding="utf-8").partition("## 2026-06-01 全体")
    positioning.write_text(header, encoding="utf-8")

    view = _view(settings)

    assert view.positioning is None
    assert view.package is None
    listed = "\n".join(view.warnings)
    assert "未登記" in listed, listed
    assert "record_positioning" in listed, listed
    # 登記の操作の入力の型（欄の名前と必須の別）が添えられている。
    for label in ["日付", "適用範囲", "前面に出す束", "根拠", "例外"]:
        assert label in listed, listed


def test_get_positioning_lists_existing_channels_for_an_unknown_name(settings) -> None:
    """媒体の名前が実在しないときは、拒否ではなく実在する媒体の一覧を返す。"""
    view = _view(settings, "shiokaze")

    assert view.positioning is None
    listed = "\n".join(view.warnings)
    for name in settings.channels:
        assert name in listed, listed
    assert "get_positioning" in listed, listed


def test_get_positioning_warns_when_the_headline_package_is_missing(settings) -> None:
    """看板の束がパッケージ定義に無いときは、実在する束の名前を断りに並べる。"""
    positioning: Path = settings.path_for("positioning")
    text = positioning.read_text(encoding="utf-8")
    head, _, tail = text.rpartition("- 前面に出す束: 要件定義と進行管理")
    positioning.write_text(head + "- 前面に出す束: 要件定義と進こう管理" + tail, encoding="utf-8")

    view = _view(settings)

    assert view.positioning is not None
    assert view.package is None
    listed = "\n".join(view.warnings)
    assert OLDER_HEADLINE in listed, listed
    assert "record_positioning" in listed, listed


def test_record_positioning_rejects_missing_date(settings) -> None:
    """日付の欄を欠いた決めは受け付けず、欄の名前と書き方の例と操作の名前を返す。"""
    before = source_digest(settings.source_dir)

    result = PositioningService(settings).record(
        PositioningDraft(
            scope="全体",
            headline_package=LATEST_HEADLINE,
            rationale="直近の引き合いが、作る前の整理に集中していたため。",
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.constraint == "決めの必須欄"

    next_action = result.rejection.next_action
    assert next_action.missing_fields == ["日付"]
    assert next_action.operation == "record_positioning"
    # 書き方の例は、型の正本の欄の定義から組み立てる（欄の名前と日付の形が入る）。
    assert "日付" in next_action.example
    assert "2026-09-16" in next_action.example

    # 拒否のときは正本のバイト列が 1 つも変わらない。
    assert source_digest(settings.source_dir) == before


def test_record_positioning_appends_a_block_and_runs_two_checks(settings) -> None:
    """通る登記は決めを 1 ブロック足し、鮮度と旧い束の宣言の 2 つの結果を返す。"""
    # 定義を決めより古くして、鮮度の違反が出る状態を作る。
    packages = settings.path_for("packages")
    packages.write_text(
        packages.read_text(encoding="utf-8").replace(
            f"## {OLDER_HEADLINE}\n\n- 最終更新: 2026-09-12",
            f"## {OLDER_HEADLINE}\n\n- 最終更新: 2026-08-01",
        ),
        encoding="utf-8",
    )
    service = PositioningService(settings)
    positioning_file = settings.path_for("positioning")
    before_blocks = positioning_file.read_text(encoding="utf-8").count("- 日付: ")

    result = service.record(
        PositioningDraft(
            decided_on=date(2026, 9, 16),
            scope="全体",
            headline_package=OLDER_HEADLINE,
            rationale="直近の引き合いが、散らばった数字を 1 か所に集める話に戻ったため。",
        )
    )

    assert result.accepted is True, result.model_dump()

    # 決めのブロックが 1 つだけ増え、読み直すと登記した決めが看板になる。
    text = positioning_file.read_text(encoding="utf-8")
    assert text.count("- 日付: ") == before_blocks + 1
    view = service.current()
    assert view.positioning is not None
    assert str(view.positioning.decided_on) == "2026-09-16"
    assert view.positioning.headline_package == OLDER_HEADLINE

    # その場で走った 2 つの検査の結果が返る。
    freshness = result.recorded["パッケージ定義の鮮度"]
    assert any("2026-08-01" in note and "2026-09-16" in note for note in freshness), freshness
    assert any(settings.files["packages"] in note for note in freshness), freshness

    claims = result.recorded["提示物の宣言と看板の一致"]
    assert claims["件数"] == 2, claims
    # ファイル名つきで返る（旧い束を宣言したままの提示物 2 件）。
    assert sorted(claims["ファイル"]) == [
        "presentations/nagiho/skill_sheet.md",
        "presentations/tsukikusa/profile.md",
    ], claims


def test_record_positioning_suggests_a_close_package_name(settings) -> None:
    """束の名前が実在しないときは、書かずに拒否して近い名前の候補を返す。"""
    before = source_digest(settings.source_dir)
    service = PositioningService(settings)

    rejected = service.record(
        PositioningDraft(
            decided_on=date(2026, 9, 16),
            scope="全体",
            headline_package="要件定義と進こう管理",
            rationale="直近の引き合いが、作る前の整理に集中していたため。",
        )
    )

    assert rejected.accepted is False
    assert rejected.rejection is not None
    candidates = rejected.rejection.next_action.candidates
    assert LATEST_HEADLINE in candidates, candidates
    assert source_digest(settings.source_dir) == before

    # 返ってきた候補をそのまま渡し直すと、今度は受け付けられる。
    retried = service.record(
        PositioningDraft(
            decided_on=date(2026, 9, 16),
            scope="全体",
            headline_package=candidates[0],
            rationale="直近の引き合いが、作る前の整理に集中していたため。",
        )
    )
    assert retried.accepted is True, retried.model_dump()


def test_record_positioning_lists_the_scopes_it_accepts(settings) -> None:
    """適用範囲が媒体の名前でも「全体」でもないときは、渡せる範囲の一覧を返す。"""
    result = PositioningService(settings).record(
        PositioningDraft(
            decided_on=date(2026, 9, 16),
            scope="どこか",
            headline_package=LATEST_HEADLINE,
            rationale="直近の引き合いが、作る前の整理に集中していたため。",
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    candidates = result.rejection.next_action.candidates
    assert candidates[0] == "全体"
    for name in settings.channels:
        assert name in candidates, candidates

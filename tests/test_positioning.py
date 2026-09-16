"""いまの決めを読む操作のテスト。

どの決めが当たるか、決めが 1 件も無いとき、媒体の名前が実在しないときの 3 つを見る。
すべて同梱のサンプルの一時的な写しの上で走らせ、読みの操作が正本を 1 バイトも変えないことも確かめる。
"""

from __future__ import annotations

from pathlib import Path

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

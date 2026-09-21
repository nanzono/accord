"""いまの決めを読む操作と、決めを登記する操作のテスト。

読みは、どの決めが当たるか、決めが 1 件も無いとき、媒体の名前が実在しないとき、当たる決めが
1 件も無いときの 4 つを見る。書きは、通る登記が返すものと、必須の欄・適用範囲・前面に出す束の
3 つの断りが返すものを見る。どちらも、返り値に現れる欄 1 つにつきテストを 1 本置き、
関数名の番号で docs/specs/positioning.md の要件を指す。
すべて同梱のサンプルの一時的な写しの上で走らせる。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from accord.models.results import PositioningDraft
from accord.repository.markdown_repository import MarkdownRepository
from accord.services.positioning import PositioningService
from conftest import source_digest

# 同梱のサンプルが持つ決め。日付の新しいほうが、いまの看板になる。
# 決めが指すのはパッケージの ID なので、見出し（表示名）とは別に持つ。
LATEST_DECISION = "2026-09-10"
LATEST_HEADLINE = "requirements-and-progress"
OLDER_HEADLINE = "data-platform-setup"
OLDER_HEADING = "データの置き場づくり"

# 登記の入力に使う値。断りの側のテストは、ここから 1 か所だけを崩す。
RECORD_DATE = date(2026, 9, 16)
RATIONALE = "直近の引き合いが、作る前の整理に集中していたため。"
STALE_RATIONALE = "直近の引き合いが、散らばった数字を 1 か所に集める話に戻ったため。"

# 候補の外にある適用範囲と、パッケージ定義に無い束の ID。どちらも断りを起こすための値。
UNKNOWN_SCOPE = "どこか"
MISSPELLED_HEADLINE = "要件定義と進こう管理"

# 写しに足す、媒体を名指しした決め。「全体」より優先される。
CHANNEL_DECISION = """
## 2026-09-11 nagiho

- 日付: 2026-09-11
- 適用範囲: nagiho
- 前面に出す束: data-platform-setup
- 根拠: この媒体は数字の置き場づくりの相談が多く、進行の側では引き合いが付かなかったため。
- 例外: なし
"""

# 写しに足す、同じ媒体を名指しした 2 件目の決め。適用範囲の一覧が重ならないことを見るために使う。
SECOND_CHANNEL_DECISION = """
## 2026-09-12 nagiho

- 日付: 2026-09-12
- 適用範囲: nagiho
- 前面に出す束: data-platform-setup
- 根拠: 同じ媒体の決めが 2 件並んでも、適用範囲の並びに同じ名前が 2 回出ないことを見るため。
- 例外: なし
"""

# 写しに足す、いちばん新しい決めと日付も適用範囲も同じ決め。前面に出す束だけが違う。
SAME_DATE_DECISION = """
## 2026-09-10 全体

- 日付: 2026-09-10
- 適用範囲: 全体
- 前面に出す束: data-platform-setup
- 根拠: 同じ日付の決めが並んだときに、正本の後ろにあるブロックが返ることを見るための 2 件目。
- 例外: なし
"""


def _view(settings, channel: str | None = None):
    """写しの正本から、いまの決めを読む。"""
    return PositioningService(settings).current(channel)


def _append(settings, block: str) -> None:
    """写しの決めの正本の末尾に、ブロックを 1 つ足す。"""
    positioning = settings.path_for("positioning")
    positioning.write_text(positioning.read_text(encoding="utf-8") + block, encoding="utf-8")


def _header_only(settings) -> str:
    """写しの決めの正本から、決めのブロックをすべて取り除き、前書きだけにして返す。"""
    positioning = settings.path_for("positioning")
    header, _, _ = positioning.read_text(encoding="utf-8").partition("## 2026-06-01 全体")
    positioning.write_text(header, encoding="utf-8")
    return header


def _only_channel_positionings(settings) -> None:
    """写しの決めを、ある媒体を名指ししたものだけにする。「全体」の決めは 1 件も残らない。"""
    header = _header_only(settings)
    settings.path_for("positioning").write_text(
        header + CHANNEL_DECISION.lstrip("\n") + SECOND_CHANNEL_DECISION, encoding="utf-8"
    )


def _break_the_headline_package(settings) -> None:
    """写しの決めの前面に出す束を、パッケージ定義に無い ID に 1 字だけ崩す。"""
    positioning: Path = settings.path_for("positioning")
    text = positioning.read_text(encoding="utf-8")
    head, _, tail = text.rpartition(f"- 前面に出す束: {LATEST_HEADLINE}")
    positioning.write_text(
        head + "- 前面に出す束: requirements-and-progres" + tail, encoding="utf-8"
    )


def _make_the_package_stale(settings) -> None:
    """写しのパッケージ定義で、旧い束の最終更新を決めの日付より前に戻す。

    登記のあとに走る鮮度の検査が違反を返す状態を作る。割った先のテストは、どれもここから始める。
    """
    packages = settings.path_for("packages")
    packages.write_text(
        packages.read_text(encoding="utf-8").replace(
            f"## {OLDER_HEADING}\n\n- ID: {OLDER_HEADLINE}\n- 最終更新: 2026-09-12",
            f"## {OLDER_HEADING}\n\n- ID: {OLDER_HEADLINE}\n- 最終更新: 2026-08-01",
        ),
        encoding="utf-8",
    )


def _record_the_older_headline(settings):
    """旧い束を前面に出す決めを 1 件登記する。"""
    return PositioningService(settings).record(
        PositioningDraft(
            decided_on=RECORD_DATE,
            scope="全体",
            headline_package=OLDER_HEADLINE,
            rationale=STALE_RATIONALE,
        )
    )


def _record_without_the_date(settings):
    """日付の欄だけを欠いた決めを登記しにいく。"""
    return PositioningService(settings).record(
        PositioningDraft(
            scope="全体",
            headline_package=LATEST_HEADLINE,
            rationale=RATIONALE,
        )
    )


def _record_with_an_unknown_scope(settings):
    """適用範囲が媒体の名前でも「全体」でもない決めを登記しにいく。"""
    return PositioningService(settings).record(
        PositioningDraft(
            decided_on=RECORD_DATE,
            scope=UNKNOWN_SCOPE,
            headline_package=LATEST_HEADLINE,
            rationale=RATIONALE,
        )
    )


def _record_with_a_missing_bundle(settings):
    """前面に出す束がパッケージ定義に無い決めを登記しにいく。"""
    return PositioningService(settings).record(
        PositioningDraft(
            decided_on=RECORD_DATE,
            scope="全体",
            headline_package=MISSPELLED_HEADLINE,
            rationale=RATIONALE,
        )
    )


# ------------------------------------------------------------ 決めを読む


def test_REQ_157_positioning_without_a_channel_returns_the_latest_whole_scope_decision(
    settings,
) -> None:
    """媒体を省くと、適用範囲「全体」の決めのうちいちばん新しい 1 件が返る。"""
    view = _view(settings)

    assert view.positioning is not None
    assert str(view.positioning.decided_on) == LATEST_DECISION
    assert view.positioning.headline_package == LATEST_HEADLINE
    assert view.warnings == []


def test_REQ_158_positioning_for_a_channel_returns_the_latest_decision_named_for_it(
    settings,
) -> None:
    """媒体を名指しした決めがあれば、「全体」の決めではなくそちらが返る。"""
    _append(settings, CHANNEL_DECISION)

    named = _view(settings, "nagiho")

    assert named.positioning is not None
    assert named.positioning.scope == "nagiho"
    assert named.positioning.headline_package == OLDER_HEADLINE


def test_REQ_159_positioning_carries_the_package_of_the_headline_bundle(settings) -> None:
    """返る決めには、その決めが前面に出す束のパッケージが想定買い手つきで添う。"""
    view = _view(settings)

    assert view.package is not None
    assert view.package.id == LATEST_HEADLINE
    assert view.package.buyer


def test_REQ_160_positionings_with_the_same_date_are_ordered_by_their_place_in_the_source(
    settings,
) -> None:
    """日付が同じ決めが並ぶと、正本の後ろにあるブロックが新しいほうとして返る。"""
    _append(settings, SAME_DATE_DECISION)

    view = _view(settings)

    assert view.positioning is not None
    assert str(view.positioning.decided_on) == LATEST_DECISION
    assert view.positioning.headline_package == OLDER_HEADLINE


def test_REQ_161_reading_the_positioning_leaves_the_source_untouched(settings) -> None:
    """読みの操作なので、正本のバイト列は 1 つも変わらない。"""
    before = source_digest(settings.source_dir)

    _view(settings)

    assert source_digest(settings.source_dir) == before


def test_REQ_162_a_channel_without_its_own_decision_falls_back_to_the_whole_scope(
    settings,
) -> None:
    """名指しの決めが無い媒体は、適用範囲「全体」の最新の決めに落ちる。"""
    _append(settings, CHANNEL_DECISION)

    fallback = _view(settings, "tsukikusa")

    assert fallback.positioning is not None
    assert fallback.positioning.scope == "全体"
    assert fallback.positioning.headline_package == LATEST_HEADLINE


def test_REQ_163_falling_back_to_the_whole_scope_is_named_in_a_warning(settings) -> None:
    """「全体」に落ちたときは、落ちたことを媒体の名前つきで警告に書く。"""
    _append(settings, CHANNEL_DECISION)

    fallback = _view(settings, "tsukikusa")

    assert any("全体" in warning for warning in fallback.warnings), fallback.warnings


def test_REQ_164_unrecorded_positioning_yields_no_decision(settings) -> None:
    """決めが 1 件も無いときは、決めもパッケージも返らない。"""
    _header_only(settings)

    view = _view(settings)

    assert view.positioning is None
    assert view.package is None


def test_REQ_165_unrecorded_positioning_is_named_in_a_warning(settings) -> None:
    """決めが 1 件も無いときは、未登記であることを警告に書く。"""
    _header_only(settings)

    view = _view(settings)

    listed = "\n".join(view.warnings)
    assert "未登記" in listed, listed


def test_REQ_166_unrecorded_positioning_names_the_operation_that_records_it(settings) -> None:
    """決めが 1 件も無いときは、決めを登記する操作の名前を警告に書く。"""
    _header_only(settings)

    view = _view(settings)

    listed = "\n".join(view.warnings)
    assert "record_positioning" in listed, listed


def test_REQ_167_unrecorded_positioning_names_the_input_fields(settings) -> None:
    """決めが 1 件も無いときは、登記の入力の欄の名前と必須の別を警告に書く。"""
    _header_only(settings)

    view = _view(settings)

    listed = "\n".join(view.warnings)
    for label in ["日付", "適用範囲", "前面に出す束", "根拠", "例外"]:
        assert label in listed, listed


def test_REQ_168_unknown_channel_yields_no_decision(settings) -> None:
    """媒体の名前が実在しないときは、拒否ではないが決めもパッケージも返らない。"""
    view = _view(settings, "shiokaze")

    assert view.positioning is None
    assert view.package is None


def test_REQ_169_unknown_channel_names_the_settings_file(settings) -> None:
    """媒体の名前が実在しないときは、どの設定ファイルの一覧に無いのかを警告に書く。"""
    view = _view(settings, "shiokaze")

    listed = "\n".join(view.warnings)
    assert settings.config_path.name in listed, listed


def test_REQ_170_unknown_channel_lists_every_existing_channel(settings) -> None:
    """媒体の名前が実在しないときは、実在する媒体の名前をすべて警告に並べる。"""
    view = _view(settings, "shiokaze")

    listed = "\n".join(view.warnings)
    for name in settings.channels:
        assert name in listed, listed


def test_REQ_171_unknown_channel_names_the_next_operation(settings) -> None:
    """媒体の名前が実在しないときは、次に呼ぶ操作の名前を警告に書く。"""
    view = _view(settings, "shiokaze")

    listed = "\n".join(view.warnings)
    assert "get_positioning" in listed, listed


def test_REQ_172_unknown_channel_says_the_whole_scope_is_returned_without_a_channel(
    settings,
) -> None:
    """媒体の名前が実在しないときは、媒体を省けば「全体」の決めが返ることを警告に書く。"""
    view = _view(settings, "shiokaze")

    listed = "\n".join(view.warnings)
    assert "媒体を省いて呼ぶと" in listed, listed
    assert "全体" in listed, listed


def test_REQ_173_no_applicable_decision_yields_no_decision(settings) -> None:
    """渡された媒体にも「全体」にも当たる決めが無いときは、決めもパッケージも返らない。"""
    _only_channel_positionings(settings)

    view = _view(settings, "tsukikusa")

    assert view.positioning is None
    assert view.package is None


def test_REQ_174_no_applicable_decision_lists_the_recorded_scopes(settings) -> None:
    """当たる決めが無いときは、登記されている適用範囲を重ねずに警告へ並べる。"""
    _only_channel_positionings(settings)

    view = _view(settings, "tsukikusa")

    scopes = next(line for line in view.warnings if "登記されている決めの適用範囲" in line)
    assert "nagiho" in scopes, scopes
    assert scopes.count("nagiho") == 1, scopes


def test_REQ_175_no_applicable_decision_says_to_record_one_first(settings) -> None:
    """当たる決めが無いときは、決めを登記する操作の名前と入力の欄を警告に書く。"""
    _only_channel_positionings(settings)

    view = _view(settings, "tsukikusa")

    listed = "\n".join(view.warnings)
    assert "record_positioning" in listed, listed
    for label in ["日付", "適用範囲", "前面に出す束", "根拠", "例外"]:
        assert label in listed, listed


def test_REQ_176_a_headline_bundle_missing_from_the_packages_yields_no_package(
    settings,
) -> None:
    """看板の束がパッケージ定義に無いときは、決めは返るがパッケージは返らない。"""
    _break_the_headline_package(settings)

    view = _view(settings)

    assert view.positioning is not None
    assert view.package is None


def test_REQ_177_a_headline_bundle_missing_from_the_packages_lists_the_existing_bundles(
    settings,
) -> None:
    """看板の束がパッケージ定義に無いときは、実在する束を表示名つきで警告に並べる。"""
    _break_the_headline_package(settings)

    view = _view(settings)

    listed = "\n".join(view.warnings)
    assert OLDER_HEADLINE in listed, listed


def test_REQ_178_a_headline_bundle_missing_from_the_packages_names_the_next_operation(
    settings,
) -> None:
    """看板の束がパッケージ定義に無いときは、決めを登記し直す操作の名前を警告に書く。"""
    _break_the_headline_package(settings)

    view = _view(settings)

    listed = "\n".join(view.warnings)
    assert "record_positioning" in listed, listed


# ------------------------------------------------------------ 決めを登記する


def test_REQ_179_an_accepted_positioning_is_appended_as_one_block(settings) -> None:
    """通る登記は、決めのブロックを 1 つだけ増やし、読み直すとその決めが看板になる。"""
    _make_the_package_stale(settings)
    service = PositioningService(settings)
    positioning_file = settings.path_for("positioning")
    before_blocks = positioning_file.read_text(encoding="utf-8").count("- 日付: ")

    result = _record_the_older_headline(settings)

    assert result.accepted is True, result.model_dump()
    text = positioning_file.read_text(encoding="utf-8")
    assert text.count("- 日付: ") == before_blocks + 1
    view = service.current()
    assert view.positioning is not None
    assert str(view.positioning.decided_on) == "2026-09-16"
    assert view.positioning.headline_package == OLDER_HEADLINE


def test_REQ_180_an_accepted_positioning_is_returned_in_the_result(settings) -> None:
    """通る登記は、登記した決めそのものを返り値に入れる。"""
    _make_the_package_stale(settings)

    result = _record_the_older_headline(settings)

    recorded = result.recorded["登記した決め"]
    assert recorded["decided_on"] == "2026-09-16", recorded
    assert recorded["scope"] == "全体", recorded
    assert recorded["headline_package"] == OLDER_HEADLINE, recorded


def test_REQ_181_recording_a_positioning_returns_the_package_freshness_violations(
    settings,
) -> None:
    """通る登記は、その場で走った鮮度の検査の違反を返り値に入れる。"""
    _make_the_package_stale(settings)

    result = _record_the_older_headline(settings)

    freshness = result.recorded["パッケージ定義の鮮度"]
    assert any("2026-08-01" in note and "2026-09-16" in note for note in freshness), freshness
    assert any(settings.files["packages"] in note for note in freshness), freshness


def test_REQ_182_a_fresh_package_definition_is_said_to_be_no_older_than_the_decision(
    settings,
) -> None:
    """鮮度の違反が 1 件も無いときは、定義が決めの日付より古くないことを返り値に書く。"""
    packages = settings.path_for("packages")
    packages.write_text(
        packages.read_text(encoding="utf-8").replace(
            f"- ID: {LATEST_HEADLINE}\n- 最終更新: 2026-09-12",
            f"- ID: {LATEST_HEADLINE}\n- 最終更新: 2026-09-20",
        ),
        encoding="utf-8",
    )

    result = PositioningService(settings).record(
        PositioningDraft(
            decided_on=RECORD_DATE,
            scope="全体",
            headline_package=LATEST_HEADLINE,
            rationale=RATIONALE,
        )
    )

    assert result.accepted is True, result.model_dump()
    freshness = result.recorded["パッケージ定義の鮮度"]
    assert len(freshness) == 1, freshness
    assert "古くない" in freshness[0], freshness
    assert "2026-09-16" in freshness[0], freshness


def test_REQ_183_recording_a_positioning_counts_the_outdated_offering_claims(settings) -> None:
    """通る登記は、旧い束を宣言したままの提示物の件数を返り値に入れる。"""
    _make_the_package_stale(settings)

    result = _record_the_older_headline(settings)

    claims = result.recorded["提示物の宣言と看板の一致"]
    assert claims["件数"] == 2, claims


def test_REQ_184_recording_a_positioning_names_the_files_of_the_outdated_claims(
    settings,
) -> None:
    """通る登記は、旧い束を宣言したままの提示物のファイル名を返り値に入れる。"""
    _make_the_package_stale(settings)

    result = _record_the_older_headline(settings)

    claims = result.recorded["提示物の宣言と看板の一致"]
    assert sorted(claims["ファイル"]) == [
        "presentations/nagiho/skill_sheet.md",
        "presentations/tsukikusa/profile.md",
    ], claims


def test_REQ_185_the_violations_found_after_recording_are_returned_as_warnings(
    settings,
) -> None:
    """通る登記は、登記の後に走った 2 つの検査が見つけた違反を警告にも返す。"""
    _make_the_package_stale(settings)

    result = _record_the_older_headline(settings)

    listed = "\n".join(result.warnings)
    assert "2026-08-01" in listed, listed
    assert "presentations/nagiho/skill_sheet.md" in listed, listed


def test_REQ_186_a_rationale_with_newlines_reads_back_unchanged(settings) -> None:
    """根拠に改行を含めて登記しても、書き戻して読み直すと同じ文字列に戻る。

    1 欄 1 行の書き方を守るための書き戻しが、改行を空白に畳んで文字列を変えてしまわないかを見る。
    """
    rationale = "直近の引き合いが、\n散らばった数字を 1 か所に集める話に戻ったため。"

    result = PositioningService(settings).record(
        PositioningDraft(
            decided_on=RECORD_DATE,
            scope="全体",
            headline_package=LATEST_HEADLINE,
            rationale=rationale,
        )
    )

    assert result.accepted is True, result.model_dump()

    positioning = MarkdownRepository(settings).load().positionings[-1]
    assert positioning.rationale == rationale


def test_REQ_187_rejected_candidate_is_accepted_when_passed_back(settings) -> None:
    """断りで返った候補をそのまま前面に出す束に渡し直すと、今度は登記される。"""
    service = PositioningService(settings)

    rejected = _record_with_a_missing_bundle(settings)
    assert rejected.rejection is not None
    candidates = rejected.rejection.next_action.candidates

    retried = service.record(
        PositioningDraft(
            decided_on=RECORD_DATE,
            scope="全体",
            headline_package=candidates[0],
            rationale=RATIONALE,
        )
    )

    assert retried.accepted is True, retried.model_dump()


def test_REQ_188_missing_required_fields_are_not_recorded(settings) -> None:
    """必須の欄を欠いた決めは受け付けず、正本のバイト列も変えない。"""
    before = source_digest(settings.source_dir)

    result = _record_without_the_date(settings)

    assert result.accepted is False
    assert result.rejection is not None
    assert source_digest(settings.source_dir) == before


def test_REQ_189_missing_required_fields_rejection_names_the_constraint(settings) -> None:
    """必須の欄を欠いた決めの断りは、当たった制約の名前を返す。"""
    result = _record_without_the_date(settings)

    assert result.rejection is not None
    assert result.rejection.constraint == "決めの必須欄"


def test_REQ_190_missing_required_fields_rejection_names_them_in_the_reason(settings) -> None:
    """必須の欄を欠いた決めの断りは、欠けた欄の名前を理由の文に書く。"""
    result = _record_without_the_date(settings)

    assert result.rejection is not None
    assert "日付" in result.rejection.reason, result.rejection.reason


def test_REQ_191_missing_required_fields_rejection_names_the_next_operation(settings) -> None:
    """必須の欄を欠いた決めの断りは、次に呼ぶ操作の名前を返す。"""
    result = _record_without_the_date(settings)

    assert result.rejection is not None
    next_action = result.rejection.next_action
    assert next_action.operation == "record_positioning"


def test_REQ_192_missing_required_fields_rejection_lists_the_missing_fields(settings) -> None:
    """必須の欄を欠いた決めの断りは、欠けた欄の名前の一覧を返す。"""
    result = _record_without_the_date(settings)

    assert result.rejection is not None
    next_action = result.rejection.next_action
    assert next_action.missing_fields == ["日付"]


def test_REQ_193_missing_required_fields_rejection_carries_an_example(settings) -> None:
    """必須の欄を欠いた決めの断りは、欠けた欄の書き方の例を返す。

    例は型の正本の欄の定義から組み立てるので、欄の名前と日付の形が入る。
    """
    result = _record_without_the_date(settings)

    assert result.rejection is not None
    next_action = result.rejection.next_action
    assert "日付" in next_action.example
    assert "2026-09-16" in next_action.example


def test_REQ_194_a_scope_outside_the_channels_is_not_recorded(settings) -> None:
    """適用範囲が媒体の名前でも「全体」でもない決めは受け付けない。"""
    result = _record_with_an_unknown_scope(settings)

    assert result.accepted is False
    assert result.rejection is not None


def test_REQ_195_a_scope_outside_the_channels_rejection_names_the_constraint(settings) -> None:
    """適用範囲が候補の外にある決めの断りは、当たった制約の名前を返す。"""
    result = _record_with_an_unknown_scope(settings)

    assert result.rejection is not None
    assert result.rejection.constraint == "適用範囲の列挙"


def test_REQ_196_a_scope_outside_the_channels_rejection_names_it_in_the_reason(
    settings,
) -> None:
    """適用範囲が候補の外にある決めの断りは、渡された範囲と設定ファイルの名前を理由に書く。"""
    result = _record_with_an_unknown_scope(settings)

    assert result.rejection is not None
    reason = result.rejection.reason
    assert UNKNOWN_SCOPE in reason, reason
    assert settings.config_path.name in reason, reason


def test_REQ_197_a_scope_outside_the_channels_rejection_names_the_next_operation(
    settings,
) -> None:
    """適用範囲が候補の外にある決めの断りは、次に呼ぶ操作の名前を返す。"""
    result = _record_with_an_unknown_scope(settings)

    assert result.rejection is not None
    assert result.rejection.next_action.operation == "record_positioning"


def test_REQ_198_a_scope_outside_the_channels_rejection_lists_the_accepted_scopes(
    settings,
) -> None:
    """適用範囲が候補の外にある決めの断りは、「全体」と媒体の名前を候補に返す。"""
    result = _record_with_an_unknown_scope(settings)

    assert result.rejection is not None
    candidates = result.rejection.next_action.candidates
    assert candidates[0] == "全体"
    for name in settings.channels:
        assert name in candidates, candidates


def test_REQ_199_a_scope_outside_the_channels_rejection_carries_an_example(settings) -> None:
    """適用範囲が候補の外にある決めの断りは、適用範囲の書き方の例を返す。"""
    result = _record_with_an_unknown_scope(settings)

    assert result.rejection is not None
    example = result.rejection.next_action.example
    assert "全体" in example, example
    assert "媒体" in example, example


def test_REQ_200_a_headline_bundle_outside_the_packages_is_not_recorded(settings) -> None:
    """前面に出す束がパッケージ定義に無い決めは受け付けず、正本のバイト列も変えない。"""
    before = source_digest(settings.source_dir)

    rejected = _record_with_a_missing_bundle(settings)

    assert rejected.accepted is False
    assert rejected.rejection is not None
    assert source_digest(settings.source_dir) == before


def test_REQ_201_a_headline_bundle_outside_the_packages_rejection_names_the_constraint(
    settings,
) -> None:
    """束が実在しない決めの断りは、当たった制約の名前を返す。"""
    rejected = _record_with_a_missing_bundle(settings)

    assert rejected.rejection is not None
    assert rejected.rejection.constraint == "前面に出す束の実在"


def test_REQ_202_a_headline_bundle_outside_the_packages_rejection_names_the_id_in_the_reason(
    settings,
) -> None:
    """束が実在しない決めの断りは、渡された ID を理由の文に書く。"""
    rejected = _record_with_a_missing_bundle(settings)

    assert rejected.rejection is not None
    assert MISSPELLED_HEADLINE in rejected.rejection.reason, rejected.rejection.reason


def test_REQ_203_a_headline_bundle_outside_the_packages_rejection_names_the_candidate_labels(
    settings,
) -> None:
    """束が実在しない決めの断りは、候補の表示名を理由の文に書く。"""
    rejected = _record_with_a_missing_bundle(settings)

    assert rejected.rejection is not None
    assert "要件定義と進行管理" in rejected.rejection.reason, rejected.rejection.reason


def test_REQ_204_a_headline_bundle_outside_the_packages_rejection_names_the_next_operation(
    settings,
) -> None:
    """束が実在しない決めの断りは、次に呼ぶ操作の名前を返す。"""
    rejected = _record_with_a_missing_bundle(settings)

    assert rejected.rejection is not None
    assert rejected.rejection.next_action.operation == "record_positioning"


def test_REQ_205_a_headline_bundle_outside_the_packages_rejection_lists_close_ids(
    settings,
) -> None:
    """束が実在しない決めの断りは、パッケージ定義にある近い ID を候補に返す。

    候補は ID だけで返り、表示名は拒否の文の側に添えて出る。
    """
    rejected = _record_with_a_missing_bundle(settings)

    assert rejected.rejection is not None
    candidates = rejected.rejection.next_action.candidates
    assert LATEST_HEADLINE in candidates, candidates


def test_REQ_206_a_headline_bundle_outside_the_packages_rejection_carries_an_example(
    settings,
) -> None:
    """束が実在しない決めの断りは、前面に出す束の書き方の例を返す。"""
    rejected = _record_with_a_missing_bundle(settings)

    assert rejected.rejection is not None
    example = rejected.rejection.next_action.example
    assert "前面に出す束" in example, example
    assert "revise_package" in example, example


def test_REQ_245_only_the_first_broken_rule_is_returned_when_recording(settings) -> None:
    """制約が同時に外れていても、必須の欄・適用範囲・前面に出す束の順で先の 1 件だけが返る。"""
    service = PositioningService(settings)

    # 3 つとも外した入力では、いちばん先に見る必須の欄の断りが返る。
    all_broken = service.record(
        PositioningDraft(
            scope=UNKNOWN_SCOPE,
            headline_package=MISSPELLED_HEADLINE,
            rationale=RATIONALE,
        )
    )
    assert all_broken.rejection is not None
    assert all_broken.rejection.constraint == "決めの必須欄"

    # 必須の欄だけを埋めると、次に見る適用範囲の断りが返る。
    scope_broken = service.record(
        PositioningDraft(
            decided_on=RECORD_DATE,
            scope=UNKNOWN_SCOPE,
            headline_package=MISSPELLED_HEADLINE,
            rationale=RATIONALE,
        )
    )
    assert scope_broken.rejection is not None
    assert scope_broken.rejection.constraint == "適用範囲の列挙"

    # 適用範囲も直すと、最後に見る前面に出す束の断りが返る。
    bundle_broken = service.record(
        PositioningDraft(
            decided_on=RECORD_DATE,
            scope="全体",
            headline_package=MISSPELLED_HEADLINE,
            rationale=RATIONALE,
        )
    )
    assert bundle_broken.rejection is not None
    assert bundle_broken.rejection.constraint == "前面に出す束の実在"

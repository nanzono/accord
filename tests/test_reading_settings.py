"""正本の読み方を設定から入れる仕組みのテスト。

見るのは 3 つ。書き方の節を持たない設定が第 1 版とまったく同じに読むこと、節を選ぶ鍵と欄を読む鍵が
1 つずつ効くこと、そして accord が書き戻した正本を、広げた読み方でそのまま読み直せることである。

節と欄の鍵は、正本のファイルではなく、その場で書いた小さな Markdown に当てる。どの鍵が何をするかを、
サンプルの中身と切り離して 1 つずつ見るためである。置き場と媒体ごとのファイルのように、実ファイルが
要る鍵だけを、第 2 のサンプルの写しの上で見る。
"""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

import pytest

from accord.models.results import PositioningDraft
from accord.repository.markdown_repository import MarkdownRepository
from accord.repository.sections import Section, read_fields, select_blocks, split_sections
from accord.services.positioning import PositioningService
from accord.vocabulary.settings import (
    CHANNEL_RULES_ONE_FILE,
    DEFAULT_BLOCK_RULE,
    PHRASES_FROM_BULLETS,
    TOP_LEVEL_KEYS,
    BlockRule,
    load_settings,
)

# 節の選び方を見るための、入れ子の見出しを持つ Markdown。
NESTED = """
## 職歴・案件（新しい順）

### 2021-04〜現在 フリーランス

- 期間: 2021-04〜現在

#### テラミナ物流 配送データの置き場づくり

- 業種: 物流

#### 2025 年から続いている案件

この見出しは案件を束ねるためだけに置いてあり、欄を持たない。

##### ナギサ書房 刊行計画の進行管理

- 業種: 出版

## 職歴の外の活動

### 社外の勉強会の運営

- 期間: 2019-04〜現在
"""

# 見出しの前置きと、読まない見出しを見るための Markdown。
LEDGER = """
## 台帳の使い方

- 案件の並びは新しい順にする。

## 案件12｜配送データの置き場づくり

- 出典の節: テラミナ物流 配送データの置き場づくり

## 出典の節の決め方

- 公開不可の節は出典にしない。
"""

# 欄の読み方を見るための、表と行頭の宣言を持つ節。
LEDGER_ENTRY = """
- 出典の節: テラミナ物流 配送データの置き場づくり

| 欄 | 中身 |
|---|---|
| 期間 | 2022-05〜2022-11 |
| 終わりの状態（誰に引き渡したか） | 先方だけで運用が続いている |

畳み行: 拠点ごとの項目のそろえ方は、面談で聞かれたときだけ話す
"""

CHANNEL = "tsukikusa"
FORBIDDEN_PHRASES = ["フルスタック", "幅広く対応可能", "〜に強みがあります"]
SECOND_TABLE_PHRASE = "言い回しの一覧は追記だけにする"


def _sections(text: str) -> list[Section]:
    return split_sections(text)


def _headings(sections: list[Section]) -> list[str]:
    return [section.heading for section in sections]


def _section(body: str) -> Section:
    """本文だけを持つ節を、その場で作る。"""
    return Section(level=2, heading="見本", body=body)


def _reload(settings, old: str, new: str):
    """写した設定ファイルの 1 行を書き換えて読み直す。"""
    path: Path = settings.config_path
    text = path.read_text(encoding="utf-8")
    assert old in text, f"写しの設定に「{old}」が無い: {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return load_settings(path)


def test_reading_rules_default_to_the_v1_behaviour(settings) -> None:
    """書き方の節を持たない設定は、すべての鍵が既定値になり、第 1 版と同じに読む。"""
    rules = settings.reading

    for key in settings.files:
        assert rules.rule_for(key) == DEFAULT_BLOCK_RULE, key
    assert rules.presentation_directories == ()
    assert rules.require_presentation_declaration is False
    assert rules.channel_rules_from == CHANNEL_RULES_ONE_FILE
    assert rules.forbidden_phrases_heading == "禁じた言い回し"
    assert rules.forbidden_phrases_any_level is False
    assert rules.forbidden_phrases_from == PHRASES_FROM_BULLETS

    # 既定の読み方は、深さ 2 の見出しの節だけをブロックにする。
    assert _headings(select_blocks(_sections(NESTED))) == [
        "職歴・案件（新しい順）",
        "職歴の外の活動",
    ]


def test_blocks_are_selected_by_level_and_parent_heading() -> None:
    """深さと、上位のどの節の下かで、ブロックを絞れる。"""
    sections = _sections(NESTED)

    by_level = select_blocks(sections, BlockRule(heading_levels=(3,)))
    assert _headings(by_level) == ["2021-04〜現在 フリーランス", "社外の勉強会の運営"]

    under = select_blocks(
        sections,
        BlockRule(heading_levels=(3,), under_headings=("職歴・案件（新しい順）",)),
    )
    assert _headings(under) == ["2021-04〜現在 フリーランス"]

    # 深さ 4 と 5 を同時に読むと、入れ子の案件が並びで返る。
    deep = select_blocks(
        sections,
        BlockRule(heading_levels=(4, 5), under_headings=("職歴・案件（新しい順）",)),
    )
    assert _headings(deep) == [
        "テラミナ物流 配送データの置き場づくり",
        "2025 年から続いている案件",
        "ナギサ書房 刊行計画の進行管理",
    ]


def test_blocks_are_selected_by_heading_prefix() -> None:
    """見出しの前置きで、同じ深さの節から案件だけを取り出せる。"""
    blocks = select_blocks(_sections(LEDGER), BlockRule(heading_prefix="案件"))

    assert _headings(blocks) == ["案件12｜配送データの置き場づくり"]


def test_blocks_listed_in_skip_headings_are_not_read() -> None:
    """読まない見出しに挙げた節は、ブロックにならない。"""
    blocks = select_blocks(
        _sections(LEDGER), BlockRule(skip_headings=("台帳の使い方", "出典の節の決め方"))
    )

    assert _headings(blocks) == ["案件12｜配送データの置き場づくり"]


def test_sections_without_fields_are_skipped() -> None:
    """欄を 1 つも持たない見出し（案件を束ねるだけの見出し）を読み飛ばせる。"""
    rule = BlockRule(
        heading_levels=(4, 5),
        under_headings=("職歴・案件（新しい順）",),
        skip_sections_without_fields=True,
    )

    assert _headings(select_blocks(_sections(NESTED), rule)) == [
        "テラミナ物流 配送データの置き場づくり",
        "ナギサ書房 刊行計画の進行管理",
    ]


def test_career_and_engagements_share_one_file_and_split_by_level(alt_settings) -> None:
    """職歴の枠と受託案件が 1 つのファイルに同居していても、深さで読み分けられる。"""
    assert alt_settings.files["career"] == alt_settings.files["engagements"]

    snapshot = MarkdownRepository(alt_settings).load()

    assert [item.heading for item in snapshot.career_frames] == [
        "2021-04〜現在 フリーランス",
        "2016-04〜2021-03 受託開発の会社",
    ]
    assert [item.heading for item in snapshot.engagements] == [
        "テラミナ物流 配送データの置き場づくり",
        "ユキノハ化成 品質記録の集約と見える化",
        "ナギサ書房 刊行計画の進行管理",
    ]
    # 同じ見出しが 2 つの型に重なって入っていない。
    assert not set(item.heading for item in snapshot.career_frames) & set(
        item.heading for item in snapshot.engagements
    )


def test_table_rows_are_read_as_fields() -> None:
    """2 列の表の行を、ラベルと値の欄として読める。表の見出しの行と区切りの行は落ちる。"""
    fields = read_fields(_section(LEDGER_ENTRY), BlockRule(fields_from_table=True))

    assert fields["期間"] == "2022-05〜2022-11"
    assert "欄" not in fields, fields

    # 鍵を立てなければ、表の行は欄として読まない（第 1 版の読み方）。
    assert "期間" not in read_fields(_section(LEDGER_ENTRY))


def test_table_fields_and_bullet_fields_are_merged() -> None:
    """表の欄と箇条書きの欄は、同じ 1 つの欄の集合になる。"""
    fields = read_fields(_section(LEDGER_ENTRY), BlockRule(fields_from_table=True))

    assert fields["出典の節"] == "テラミナ物流 配送データの置き場づくり"
    assert fields["期間"] == "2022-05〜2022-11"


def test_bare_declaration_lines_are_read_as_fields() -> None:
    """箇条書きの記号が無い行頭の宣言も、挙げたラベルだけは欄として読める。"""
    rule = BlockRule(fields_from_table=True, bare_labels=("畳み行",))

    fields = read_fields(_section(LEDGER_ENTRY), rule)
    assert fields["畳み行"] == "拠点ごとの項目のそろえ方は、面談で聞かれたときだけ話す"

    # 挙げていないラベルは、ただの地の文として読み飛ばす。
    assert "畳み行" not in read_fields(_section(LEDGER_ENTRY), BlockRule(fields_from_table=True))


def test_entry_number_is_read_from_the_heading(alt_settings) -> None:
    """案件番号の欄が無い台帳でも、見出しの前置きに続く数字から番号を読む。"""
    ledger = alt_settings.path_for("resume_ledger")
    assert "案件番号" not in ledger.read_text(encoding="utf-8")

    entries = MarkdownRepository(alt_settings).load().ledger_entries

    assert [item.entry_number for item in entries] == ["1", "2", "3"]


def test_label_note_is_stripped() -> None:
    """欄のラベルの末尾の括弧書きを落としてから読める。"""
    body = "- 成果（定量は本人の記録から）: 3 社とも運用が続いている"

    assert read_fields(_section(body), BlockRule(strip_label_note=True))["成果"] == (
        "3 社とも運用が続いている"
    )
    # 鍵を立てなければ、括弧書きごとのラベルとして読む（第 1 版の読み方）。
    assert "成果" not in read_fields(_section(body))


def test_label_alias_fills_every_field_it_maps_to() -> None:
    """1 つのラベルを複数の欄に読み替えると、同じ値がその欄すべてに入る。"""
    body = "- 期間 / 所属・立場: 2021-04〜現在 / フリーランス / 請負"
    rule = BlockRule(labels={"期間 / 所属・立場": ("期間", "所属", "立場")})

    fields = read_fields(_section(body), rule)

    assert fields["期間"] == fields["所属"] == fields["立場"]
    assert fields["期間"] == "2021-04〜現在 / フリーランス / 請負"
    assert "期間 / 所属・立場" not in fields


def test_presentations_are_read_from_every_declared_directory(alt_settings) -> None:
    """置き場に挙げたディレクトリのすべてから、提示物を読む。"""
    paths = [item.path for item in MarkdownRepository(alt_settings).load().presentations]
    assert paths == ["tsukikusa/profile.md", "nagiho/skill_sheet.md"]

    # 置き場を 1 つに減らすと、そのディレクトリの提示物だけになる。
    narrowed = _reload(
        alt_settings, 'directories = ["tsukikusa", "nagiho"]', 'directories = ["nagiho"]'
    )
    assert [item.path for item in MarkdownRepository(narrowed).load().presentations] == [
        "nagiho/skill_sheet.md"
    ]


def test_presentations_are_limited_to_the_declared_files(alt_settings) -> None:
    """宣言の行を持つ Markdown だけを提示物として読み、同居する控えは読まない。"""
    snapshot = MarkdownRepository(alt_settings).load()

    assert all("companies/" not in item.path for item in snapshot.presentations)
    # 読まなかった控えは、欄が足りないという断りにも出ない。
    assert [defect.model_dump() for defect in snapshot.defects] == []

    # 絞り込みをやめると、控えが提示物として読まれ、欄が足りない断りになる。
    wide = _reload(alt_settings, "require_declaration = true", "require_declaration = false")
    defects = MarkdownRepository(wide).load().defects
    assert [defect.file for defect in defects] == [
        "tsukikusa/channel.md",
        "tsukikusa/companies/teramina/log.md",
        "nagiho/channel.md",
        "nagiho/companies/nagisa/log.md",
    ]


def test_channel_rules_come_from_a_file_per_channel(alt_settings) -> None:
    """媒体の規約を、見せ方の正本の節ではなく、媒体ごとのファイルから読める。"""
    repository = MarkdownRepository(alt_settings)
    rules = repository.channel_rules(CHANNEL)

    assert any("400 字以内" in rule for rule in rules), rules
    # 他の媒体のファイルの中身は混ざらない。
    assert rules != repository.channel_rules("nagiho")
    # 見せ方の正本には、媒体の名前の節そのものが無い。
    assert CHANNEL not in alt_settings.path_for("presentation_rules").read_text(encoding="utf-8")
    # 実在しない媒体を渡すと、拒否ではなく空の一覧になる。
    assert repository.channel_rules("shiokaze") == []


def test_forbidden_phrases_are_found_by_name_at_any_level(alt_settings) -> None:
    """禁じた言い回しの節を、深さを問わず見出しの名前で探せる。"""
    assert MarkdownRepository(alt_settings).forbidden_phrases() == FORBIDDEN_PHRASES

    # 深さを問う設定に戻すと、深さ 3 に置かれたこの節は見つからない。
    fixed = _reload(
        alt_settings,
        "forbidden_phrases_any_level = true",
        "forbidden_phrases_any_level = false",
    )
    assert MarkdownRepository(fixed).forbidden_phrases() == []


def test_forbidden_phrases_heading_note_is_ignored_when_matching(alt_settings) -> None:
    """見出しの末尾の括弧書きは、名前を照らし合わせるときに見ない。"""
    rules_file = alt_settings.path_for("presentation_rules")
    text = rules_file.read_text(encoding="utf-8")
    assert "### 本人が禁じた言い回し（追記型。応募文を書く前にこの表と照合する）" in text
    rules_file.write_text(
        text.replace(
            "### 本人が禁じた言い回し（追記型。応募文を書く前にこの表と照合する）",
            "### 本人が禁じた言い回し（2026-09-16 に 1 行足した）",
        ),
        encoding="utf-8",
    )

    assert MarkdownRepository(alt_settings).forbidden_phrases() == FORBIDDEN_PHRASES


def test_forbidden_phrases_ignore_a_second_table_in_the_same_section(alt_settings) -> None:
    """同じ節に見出しの無い 2 つ目の表があっても、最初の表だけを読む。"""
    text = alt_settings.path_for("presentation_rules").read_text(encoding="utf-8")
    assert SECOND_TABLE_PHRASE in text, "2 つ目の表がサンプルから消えている"

    phrases = MarkdownRepository(alt_settings).forbidden_phrases()

    assert phrases == FORBIDDEN_PHRASES
    assert SECOND_TABLE_PHRASE not in phrases


def test_write_back_stays_readable_after_a_round_trip(alt_settings) -> None:
    """accord が第 1 版の書き方で書き足したブロックを、広げた読み方でそのまま読み直せる。"""
    service = PositioningService(alt_settings)
    rationale = "直近の引き合いが、散らばった数字を 1 か所に集める話に戻ったため。"

    result = service.record(
        PositioningDraft(
            decided_on=date(2026, 9, 16),
            scope="全体",
            headline_package="データの置き場づくり",
            rationale=rationale,
        )
    )
    assert result.accepted is True, result.model_dump()

    snapshot = MarkdownRepository(alt_settings).load()
    assert [defect.model_dump() for defect in snapshot.defects] == []
    latest = snapshot.positionings[-1]
    assert latest.decided_on == date(2026, 9, 16)
    assert latest.rationale == rationale
    assert service.current().positioning == latest


def test_unknown_top_level_section_is_rejected_with_its_name(settings) -> None:
    """最上位に綴りを間違えた節を書くと、書いた名前と書ける名前を添えて設定の読み込みが止まる。

    黙って読み飛ばすと、書いたつもりの読み方が 1 つも効かないままサーバーが立ち上がり、
    既定の読み方で読んだ結果が返り続ける。
    """
    path: Path = settings.config_path
    path.write_text(
        path.read_text(encoding="utf-8") + "\n[reeding]\nstrip_label_note = true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as caught:
        load_settings(path)

    message = str(caught.value)
    assert "reeding" in message, message
    for name in ("reading", "source", "vocabulary"):
        assert name in message, message


def test_the_three_known_top_level_sections_are_accepted(alt_settings) -> None:
    """最上位が source・vocabulary・reading の 3 つだけの設定は、いままでどおり読める。"""
    document = tomllib.loads(alt_settings.config_path.read_text(encoding="utf-8"))

    assert set(document) == {"source", "vocabulary", "reading"}
    assert set(document) <= set(TOP_LEVEL_KEYS)
    # 読み直しても例外にならず、同じ設定が返る。
    assert load_settings(alt_settings.config_path) == alt_settings


# ---------------------------------------------------------------- 公開記録の置き場と語彙


# 設定から抜くと、公開記録を使わない正本（この段より前の設定と同じ形）になる 3 行の書き出し。
PUBLIC_RECORD_SETTING_LINES = (
    "public_records = ",
    "public_record_kinds = ",
    "public_record_roles = ",
)


def _drop_lines(settings, prefixes: tuple[str, ...]) -> Path:
    """写しの設定から、書き出しの合う行を抜いて、その設定ファイルの場所を返す。"""
    path: Path = settings.config_path
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not line.startswith(prefixes)]
    assert len(kept) == len(lines) - len(prefixes), f"写しの設定に抜く行が無い: {prefixes}"
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("key", ["public_record_kinds", "public_record_roles"])
def test_config_with_the_public_record_file_but_without_its_vocabulary_is_rejected(
    settings, key: str
) -> None:
    """公開記録の置き場を書いたのに語彙を書いていない設定は、鍵の名前を添えて起動時に止まる。"""
    path = _drop_lines(settings, (f"{key} = ",))

    with pytest.raises(ValueError) as caught:
        load_settings(path)

    assert key in str(caught.value), str(caught.value)


def test_config_without_the_public_record_file_still_loads(settings) -> None:
    """置き場も語彙も書いていない設定は、例外にならず、公開記録を 0 件として読む。"""
    from accord.models.results import MaterialRequest
    from accord.services.material import MaterialService

    path = _drop_lines(settings, PUBLIC_RECORD_SETTING_LINES)

    plain = load_settings(path)

    assert plain.has_file("public_records") is False
    assert plain.public_record_kinds == []
    assert plain.public_record_roles == []
    snapshot = MarkdownRepository(plain).load()
    assert snapshot.public_records == []
    # 材料の取り出しも、公開記録を空で返すだけで壊れない。
    material = MaterialService(plain).assemble(MaterialRequest(channel=CHANNEL))
    assert material.public_records == []

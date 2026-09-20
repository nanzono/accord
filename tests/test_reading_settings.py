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
    CHANNEL_RULES_CHOICES,
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

- 出典の節: teramina-delivery

## 出典の節の決め方

- 公開不可の節は出典にしない。
"""

# 欄の読み方を見るための、表と行頭の宣言を持つ節。
LEDGER_ENTRY = """
- 出典の節: teramina-delivery

| 欄 | 中身 |
|---|---|
| 期間 | 2022-05〜2022-11 |
| 終わりの状態（誰に引き渡したか） | 先方だけで運用が続いている |

畳み行: 拠点ごとの項目のそろえ方は、面談で聞かれたときだけ話す
"""

CHANNEL = "tsukikusa"
FORBIDDEN_PHRASES = ["フルスタック", "幅広く対応可能", "〜に強みがあります"]
SECOND_TABLE_PHRASE = "言い回しの一覧は追記だけにする"
# 禁じた言い回しの節の末尾に、空行を挟んで足す別の箇条書き（最初の塊で切れることを見る）。
SECOND_BULLET_BLOCK = (
    "\nこの節に足すときの決めごと。\n\n"
    "- 言い回しを足すときは、足した日付を添える。\n"
    "- 言い回しを消すときは、消した理由を添える。\n"
)


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


def test_REQ_046_default_reading_reads_only_level_two_sections(settings) -> None:
    """書き方の節を持たない設定は、正本のどの種類でも深さ 2 の節だけをブロックとして読む。"""
    rules = settings.reading

    for key in settings.files:
        assert rules.rule_for(key) == DEFAULT_BLOCK_RULE, key

    # 既定の読み方は、深さ 2 の見出しの節だけをブロックにする。
    assert _headings(select_blocks(_sections(NESTED))) == [
        "職歴・案件（新しい順）",
        "職歴の外の活動",
    ]


def test_REQ_047_presentation_directories_default_to_the_whole_presentation_tree(
    settings,
) -> None:
    """提示物の置き場を書かない設定では、置き場の一覧が空になり、指されたディレクトリの下を全部たどる。"""
    assert settings.reading.presentation_directories == ()


def test_REQ_048_files_without_a_declaration_are_read_by_default(settings) -> None:
    """宣言の行での絞りを書かない設定では、絞りが無効なので、宣言の行が無い Markdown も読もうとする。"""
    assert settings.reading.require_presentation_declaration is False


def test_REQ_049_channel_rules_default_to_the_section_in_one_file(settings) -> None:
    """媒体の規約の置き場を書かない設定は、見せ方の正本の中の媒体の名前の節から規約を読む。"""
    assert settings.reading.channel_rules_from == CHANNEL_RULES_ONE_FILE


def test_REQ_050_forbidden_phrases_heading_defaults_to_its_plain_name(settings) -> None:
    """禁じた言い回しの節の見出しを書かない設定は、その節を「禁じた言い回し」の名前で探す。"""
    assert settings.reading.forbidden_phrases_heading == "禁じた言い回し"


def test_REQ_051_forbidden_phrases_are_searched_only_in_the_selected_headings_by_default(
    settings,
) -> None:
    """深さを問わず探す設定を書かなければ、禁じた言い回しの節は選ばれる見出しの中だけから探す。"""
    assert settings.reading.forbidden_phrases_any_level is False


def test_REQ_052_forbidden_phrases_default_to_the_bullets_in_the_section(settings) -> None:
    """禁じた言い回しの読み方を書かない設定は、節の箇条書きから言い回しを読む。"""
    assert settings.reading.forbidden_phrases_from == PHRASES_FROM_BULLETS


def test_REQ_053_blocks_are_selected_by_level() -> None:
    """書いた深さの見出しの節だけがブロックになる。深さを 2 つ書けば、両方が並びで返る。"""
    sections = _sections(NESTED)

    by_level = select_blocks(sections, BlockRule(heading_levels=(3,)))
    assert _headings(by_level) == ["2021-04〜現在 フリーランス", "社外の勉強会の運営"]

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


def test_REQ_054_blocks_are_selected_by_parent_heading() -> None:
    """上位の見出しを書くと、その見出しの下にある節だけがブロックになる。"""
    sections = _sections(NESTED)

    under = select_blocks(
        sections,
        BlockRule(heading_levels=(3,), under_headings=("職歴・案件（新しい順）",)),
    )
    assert _headings(under) == ["2021-04〜現在 フリーランス"]


def test_REQ_055_blocks_are_selected_by_heading_prefix() -> None:
    """見出しの前置きで、同じ深さの節から案件だけを取り出せる。"""
    blocks = select_blocks(_sections(LEDGER), BlockRule(heading_prefix="案件"))

    assert _headings(blocks) == ["案件12｜配送データの置き場づくり"]


def test_REQ_056_blocks_listed_in_skip_headings_are_not_read() -> None:
    """読まない見出しに挙げた節は、ブロックにならない。"""
    blocks = select_blocks(
        _sections(LEDGER), BlockRule(skip_headings=("台帳の使い方", "出典の節の決め方"))
    )

    assert _headings(blocks) == ["案件12｜配送データの置き場づくり"]


def test_REQ_056_sections_under_a_skipped_heading_are_not_read() -> None:
    """読まない見出しに挙げた節の下にある節も、ブロックにならない。

    束ねるための中間の見出しを読まない設定にすると、その下の深さ 5 の案件も落ちる。
    """
    rule = BlockRule(
        heading_levels=(4, 5),
        under_headings=("職歴・案件（新しい順）",),
        skip_headings=("2025 年から続いている案件",),
    )

    assert _headings(select_blocks(_sections(NESTED), rule)) == [
        "テラミナ物流 配送データの置き場づくり",
    ]


def test_REQ_057_sections_without_fields_are_skipped() -> None:
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


def test_REQ_058_career_and_engagements_share_one_file_and_split_by_level(alt_settings) -> None:
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


def test_REQ_059_table_rows_are_read_as_fields() -> None:
    """2 列の表の行を、ラベルと値の欄として読める。表の見出しの行と区切りの行は落ちる。"""
    fields = read_fields(_section(LEDGER_ENTRY), BlockRule(fields_from_table=True))

    assert fields["期間"] == "2022-05〜2022-11"
    assert "欄" not in fields, fields

    # 鍵を立てなければ、表の行は欄として読まない（第 1 版の読み方）。
    assert "期間" not in read_fields(_section(LEDGER_ENTRY))


def test_REQ_060_table_fields_and_bullet_fields_are_merged() -> None:
    """表の欄と箇条書きの欄は、同じ 1 つの欄の集合になる。"""
    fields = read_fields(_section(LEDGER_ENTRY), BlockRule(fields_from_table=True))

    assert fields["出典の節"] == "teramina-delivery"
    assert fields["期間"] == "2022-05〜2022-11"


def test_REQ_061_bare_declaration_lines_are_read_as_fields() -> None:
    """箇条書きの記号が無い行頭の宣言も、挙げたラベルだけは欄として読める。"""
    rule = BlockRule(fields_from_table=True, bare_labels=("畳み行",))

    fields = read_fields(_section(LEDGER_ENTRY), rule)
    assert fields["畳み行"] == "拠点ごとの項目のそろえ方は、面談で聞かれたときだけ話す"

    # 挙げていないラベルは、ただの地の文として読み飛ばす。
    assert "畳み行" not in read_fields(_section(LEDGER_ENTRY), BlockRule(fields_from_table=True))


def test_REQ_062_entry_number_is_read_from_the_heading(alt_settings) -> None:
    """案件番号の欄が無い台帳でも、見出しの前置きに続く数字から番号を読む。"""
    ledger = alt_settings.path_for("resume_ledger")
    assert "案件番号" not in ledger.read_text(encoding="utf-8")

    entries = MarkdownRepository(alt_settings).load().ledger_entries

    assert [item.entry_number for item in entries] == ["1", "2", "3"]


def test_REQ_063_label_note_is_stripped() -> None:
    """欄のラベルの末尾の括弧書きを落としてから読める。"""
    body = "- 成果（定量は本人の記録から）: 3 社とも運用が続いている"

    assert read_fields(_section(body), BlockRule(strip_label_note=True))["成果"] == (
        "3 社とも運用が続いている"
    )
    # 鍵を立てなければ、括弧書きごとのラベルとして読む（第 1 版の読み方）。
    assert "成果" not in read_fields(_section(body))


def test_REQ_064_label_alias_fills_every_field_it_maps_to() -> None:
    """1 つのラベルを複数の欄に読み替えると、同じ値がその欄すべてに入る。"""
    body = "- 期間 / 所属・立場: 2021-04〜現在 / フリーランス / 請負"
    rule = BlockRule(labels={"期間 / 所属・立場": ("期間", "所属", "立場")})

    fields = read_fields(_section(body), rule)

    assert fields["期間"] == fields["所属"] == fields["立場"]
    assert fields["期間"] == "2021-04〜現在 / フリーランス / 請負"
    assert "期間 / 所属・立場" not in fields


def test_REQ_065_presentations_are_read_from_every_declared_directory(alt_settings) -> None:
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


def test_REQ_066_presentations_are_limited_to_the_declared_files(alt_settings) -> None:
    """宣言の行を持つ Markdown だけを提示物として読み、同居する控えは読まない。"""
    snapshot = MarkdownRepository(alt_settings).load()

    assert all("companies/" not in item.path for item in snapshot.presentations)


def test_REQ_067_files_without_a_declaration_are_not_listed_as_defects(alt_settings) -> None:
    """宣言の行を持たない Markdown は、読まないだけでなく、欄が足りない断りにも出さない。"""
    snapshot = MarkdownRepository(alt_settings).load()

    assert [defect.model_dump() for defect in snapshot.defects] == []


def test_REQ_048_dropping_the_declaration_filter_lists_the_copies_as_defects(alt_settings) -> None:
    """宣言の行での絞りをやめると、同居する控えが提示物として読まれ、欄が足りない断りになる。"""
    wide = _reload(alt_settings, "require_declaration = true", "require_declaration = false")

    defects = MarkdownRepository(wide).load().defects

    assert [defect.file for defect in defects] == [
        "tsukikusa/channel.md",
        "tsukikusa/companies/teramina/log.md",
        "nagiho/channel.md",
        "nagiho/companies/nagisa/log.md",
    ]


def test_REQ_068_channel_rules_come_from_a_file_per_channel(alt_settings) -> None:
    """媒体の規約を、見せ方の正本の節ではなく、媒体ごとのファイルから読める。"""
    repository = MarkdownRepository(alt_settings)
    rules = repository.channel_rules(CHANNEL)

    assert any("400 字以内" in rule for rule in rules), rules
    # 他の媒体のファイルの中身は混ざらない。
    assert rules != repository.channel_rules("nagiho")
    # 見せ方の正本には、媒体の名前の節そのものが無い。
    assert CHANNEL not in alt_settings.path_for("presentation_rules").read_text(encoding="utf-8")


def test_REQ_069_unknown_channel_returns_no_rules(alt_settings) -> None:
    """媒体ごとの規約のファイルが無い媒体を渡すと、拒否ではなく空の一覧が返る。"""
    repository = MarkdownRepository(alt_settings)

    assert repository.channel_rules("shiokaze") == []


def test_REQ_070_forbidden_phrases_are_found_by_name_at_any_level(alt_settings) -> None:
    """禁じた言い回しの節を、深さを問わず見出しの名前で探せる。"""
    assert MarkdownRepository(alt_settings).forbidden_phrases() == FORBIDDEN_PHRASES

    # 深さを問う設定に戻すと、深さ 3 に置かれたこの節は見つからない。
    fixed = _reload(
        alt_settings,
        "forbidden_phrases_any_level = true",
        "forbidden_phrases_any_level = false",
    )
    assert MarkdownRepository(fixed).forbidden_phrases() == []


def test_REQ_071_forbidden_phrases_heading_note_is_ignored_when_matching(alt_settings) -> None:
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


def test_REQ_072_forbidden_phrases_ignore_a_second_table_in_the_same_section(alt_settings) -> None:
    """同じ節に見出しの無い 2 つ目の表があっても、最初の表だけを読む。"""
    text = alt_settings.path_for("presentation_rules").read_text(encoding="utf-8")
    assert SECOND_TABLE_PHRASE in text, "2 つ目の表がサンプルから消えている"

    phrases = MarkdownRepository(alt_settings).forbidden_phrases()

    assert phrases == FORBIDDEN_PHRASES
    assert SECOND_TABLE_PHRASE not in phrases


def test_REQ_074_forbidden_phrases_ignore_a_second_bullet_block_in_the_same_section(
    settings,
) -> None:
    """同じ節に空行で切れた 2 つ目の箇条書きがあっても、最初の塊だけを読む。"""
    rules_file = settings.path_for("presentation_rules")
    before = MarkdownRepository(settings).forbidden_phrases()
    assert len(before) == 3, before

    rules_file.write_text(
        rules_file.read_text(encoding="utf-8") + SECOND_BULLET_BLOCK, encoding="utf-8"
    )

    phrases = MarkdownRepository(settings).forbidden_phrases()

    assert phrases == before
    assert not any("足した日付" in phrase for phrase in phrases), phrases


def test_REQ_073_write_back_stays_readable_after_a_round_trip(alt_settings) -> None:
    """accord が第 1 版の書き方で書き足したブロックを、広げた読み方でそのまま読み直せる。"""
    service = PositioningService(alt_settings)
    rationale = "直近の引き合いが、散らばった数字を 1 か所に集める話に戻ったため。"

    result = service.record(
        PositioningDraft(
            decided_on=date(2026, 9, 16),
            scope="全体",
            headline_package="data-platform-setup",
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


def test_REQ_075_unknown_top_level_section_is_rejected_with_its_name(settings) -> None:
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


def test_REQ_076_the_three_known_top_level_sections_are_accepted(alt_settings) -> None:
    """最上位が source・vocabulary・reading の 3 つだけの設定は、いままでどおり読める。"""
    document = tomllib.loads(alt_settings.config_path.read_text(encoding="utf-8"))

    assert set(document) == {"source", "vocabulary", "reading"}
    assert set(document) <= set(TOP_LEVEL_KEYS)
    # 読み直しても例外にならず、同じ設定が返る。
    assert load_settings(alt_settings.config_path) == alt_settings


def test_REQ_077_unknown_reading_key_is_rejected_with_its_name(settings) -> None:
    """読み方の節に綴りを間違えた鍵を書くと、その鍵の名前と書ける鍵の名前を添えて止まる。

    黙って読み飛ばすと、書いたつもりの読み方だけが効かないまま、既定の読み方で読んだ結果が返る。
    """
    path: Path = settings.config_path
    path.write_text(
        path.read_text(encoding="utf-8") + "\n[reading.career]\nheading_levl = [3]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as caught:
        load_settings(path)

    message = str(caught.value)
    assert "heading_levl" in message, message
    assert "heading_levels" in message, message


def test_REQ_078_empty_heading_levels_are_rejected_with_the_key_name(alt_settings) -> None:
    """読み方の節の深さの一覧を空にすると、その鍵の名前を添えて設定の読み込みが止まる。

    深さが 1 つも無いと、その正本のブロックが 1 件も読めない。読み込みの瞬間に止める。
    """
    with pytest.raises(ValueError) as caught:
        _reload(alt_settings, "heading_levels = [3]", "heading_levels = []")

    message = str(caught.value)
    assert "heading_levels" in message, message
    assert "reading.career" in message, message


def test_REQ_079_word_outside_the_choices_is_rejected_with_the_choices(alt_settings) -> None:
    """選べる語が決まっている鍵に一覧の外の語を書くと、書いた語と選べる語を添えて止まる。"""
    with pytest.raises(ValueError) as caught:
        _reload(
            alt_settings,
            'channel_rules_from = "per_channel_file"',
            'channel_rules_from = "each_channel_file"',
        )

    message = str(caught.value)
    assert "each_channel_file" in message, message
    for word in CHANNEL_RULES_CHOICES:
        assert word in message, message


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
def test_REQ_080_config_with_the_public_record_file_but_without_its_vocabulary_is_rejected(
    settings, key: str
) -> None:
    """公開記録の置き場を書いたのに語彙を書いていない設定は、鍵の名前を添えて起動時に止まる。"""
    path = _drop_lines(settings, (f"{key} = ",))

    with pytest.raises(ValueError) as caught:
        load_settings(path)

    assert key in str(caught.value), str(caught.value)


def test_REQ_081_config_without_the_public_record_file_still_loads(settings) -> None:
    """置き場も語彙も書いていない設定は、例外にならず、公開記録を 0 件として読む。"""
    path = _drop_lines(settings, PUBLIC_RECORD_SETTING_LINES)

    plain = load_settings(path)

    assert plain.has_file("public_records") is False
    assert plain.public_record_kinds == []
    assert plain.public_record_roles == []
    snapshot = MarkdownRepository(plain).load()
    assert snapshot.public_records == []


def test_assemble_material_returns_no_public_records_without_the_public_record_file(
    settings,
) -> None:
    """置き場も語彙も書いていない設定でも、材料の取り出しは公開記録を空で返すだけで壊れない。"""
    from accord.models.results import MaterialRequest
    from accord.services.material import MaterialService

    path = _drop_lines(settings, PUBLIC_RECORD_SETTING_LINES)

    plain = load_settings(path)

    material = MaterialService(plain).assemble(MaterialRequest(channel=CHANNEL))
    assert material.public_records == []

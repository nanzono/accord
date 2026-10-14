"""正本の書き方（データの形）と変更の種類の表（`docs/data-format.md`）の、各マスのテスト。

表の 1 行の「変更の種類」の 1 つずつを 1 マスとし、マスごとに、accord の操作でその変更が行えること
（または、決めた理由で断られること）を見る。テストの名前は `test_REQ_540_<形>_<変更>` の形にそろえる。
すべて同梱の 2 つ目の見本の一時的な写しの上で走らせる。書き方の見本は、見本の
「書き方の見本」の節（架空の中身）にある。
"""

from __future__ import annotations

import pytest

from accord.repository.markdown_repository import MarkdownRepository
from accord.services.sections import SectionService
from conftest import add_config_lines, git, init_git, source_digest

CAREER = "career_master.md"
LEDGER = "keirekisho/daicho.md"
FEATURES = "product/features.md"
TITLE = "経歴の正本"
FORMATS = f"{TITLE} > 書き方の見本"
PRACTICE = "sample-practice"
FREELANCE = f"{TITLE} > 職歴・案件（新しい順） > 2021-04〜現在 フリーランス"
OUTSIDE = f"{TITLE} > 職歴の外の活動"
REASON = "書き方の表のマスを確かめる"


@pytest.fixture
def recording(sample_copy):
    """写しを git のリポジトリにし、書き込みの記録を有効にした 2 つ目の見本の設定を返す。"""
    init_git(sample_copy)
    settings = add_config_lines(sample_copy / "accord_alt.toml", "source", ["commit_writes = true"])
    git(sample_copy, "commit", "-q", "-am", "書き込みの記録を有効にする")
    return settings


def _service(settings) -> SectionService:
    return SectionService(settings)


def _read(settings, section):
    return _service(settings).read_section(section)


def _paths(settings, file=CAREER) -> list[str]:
    return [entry.heading_path for entry in _service(settings).list_sections(file).sections]


def _levels(settings, file=CAREER) -> dict[str, int]:
    repository = MarkdownRepository(settings)
    return {item.heading_path: item.level for item in repository.source_sections(file)}


def _revise(settings, section, body, disclosures=None):
    current = _read(settings, section)
    return _service(settings).revise_section(section, body, current.fingerprint, REASON, disclosures)


def _body(settings, section) -> str:
    return _read(settings, section).body


def _accepted(result) -> None:
    assert result.accepted is True, result.rejection


# ---------------------------------------------------------------- 最上位の見出し


def test_REQ_540_top_heading_add(recording) -> None:
    """最上位の見出し: 足す（親を省いてファイルを渡す）。"""
    _accepted(_service(recording).add_section(None, "付録", "補足の資料。", REASON, file=LEDGER))
    assert "付録" in _paths(recording, LEDGER)


def test_REQ_540_top_heading_remove(recording) -> None:
    """最上位の見出し: 消す。"""
    _accepted(_service(recording).add_section(None, "付録", "補足の資料。", REASON, file=LEDGER))
    _accepted(_service(recording).remove_section("付録", _read(recording, "付録").fingerprint, REASON))
    assert "付録" not in _paths(recording, LEDGER)


def test_REQ_540_top_heading_reorder(recording) -> None:
    """最上位の見出し: 並べ替える（新しい親を省き、前に置く深さ 1 の節を渡す）。"""
    _accepted(_service(recording).add_section(None, "付録", "補足の資料。", REASON, file=LEDGER))
    first = _paths(recording, LEDGER)[0]
    _accepted(
        _service(recording).move_section(
            "付録", None, _read(recording, "付録").fingerprint, REASON, before=first, file=LEDGER
        )
    )
    assert _paths(recording, LEDGER)[0] == "付録"


def test_REQ_540_top_heading_rename(recording) -> None:
    """最上位の見出し: 名を変える。"""
    _accepted(
        _service(recording).rename_heading(TITLE, "経歴の正本（架空）", _read(recording, TITLE).fingerprint, REASON)
    )
    assert _paths(recording)[0] == "経歴の正本（架空）"


# ---------------------------------------------------------------- 下位の見出し


def test_REQ_540_sub_heading_add(recording) -> None:
    """下位の見出し: 足す。"""
    _accepted(_service(recording).add_section(FORMATS, "見本の小節 C", "中身。", REASON))
    assert f"{FORMATS} > 見本の小節 C" in _paths(recording)


def test_REQ_540_sub_heading_remove(recording) -> None:
    """下位の見出し: 消す。"""
    path = f"{FORMATS} > 見本の小節 A > 補足"
    _accepted(_service(recording).remove_section(path, _read(recording, path).fingerprint, REASON))
    assert path not in _paths(recording)


def test_REQ_540_sub_heading_move(recording) -> None:
    """下位の見出し: 動かす（親を変える）。"""
    path = f"{FORMATS} > 見本の小節 A"
    _accepted(_service(recording).move_section(path, OUTSIDE, _read(recording, path).fingerprint, REASON))
    assert f"{OUTSIDE} > 見本の小節 A > 補足" in _paths(recording)


def test_REQ_540_sub_heading_rename(recording) -> None:
    """下位の見出し: 名を変える。"""
    path = f"{FORMATS} > 見本の小節 A"
    _accepted(_service(recording).rename_heading(path, "見本の小節 A2", _read(recording, path).fingerprint, REASON))
    assert f"{FORMATS} > 見本の小節 A2 > 補足" in _paths(recording)


def test_REQ_540_sub_heading_change_depth(recording) -> None:
    """下位の見出し: 深さを変える（隣の節の下へ動かすと 1 段深く、上の親の下へ動かすと 1 段浅くなる）。"""
    a = f"{FORMATS} > 見本の小節 A"
    b = f"{FORMATS} > 見本の小節 B"
    _accepted(_service(recording).move_section(b, a, _read(recording, b).fingerprint, REASON))
    assert _levels(recording)[f"{a} > 見本の小節 B"] == 4
    deeper = f"{a} > 見本の小節 B"
    _accepted(_service(recording).move_section(deeper, FORMATS, _read(recording, deeper).fingerprint, REASON))
    assert _levels(recording)[b] == 3


# ---------------------------------------------------------------- 同じ名前の見出し


def test_REQ_540_same_name_heading_address_by_path(recording) -> None:
    """同じ名前の見出しが別の親の下にある: 見出しの道筋で 1 つに指せる。"""
    a = _read(recording, f"{FORMATS} > 見本の小節 A > 補足")
    b = _read(recording, f"{FORMATS} > 見本の小節 B > 補足")
    assert a.body == "小節 A の補足。"
    assert b.body.startswith("小節 B の補足。")


def test_REQ_540_same_name_heading_edit(recording) -> None:
    """同じ名前の見出しが別の親の下にある: 片方を直し、名を変えても、重なりの守りに誤って断られない。"""
    path = f"{FORMATS} > 見本の小節 A > 補足"
    _accepted(_revise(recording, path, "小節 A の補足を直した。"))
    _accepted(_service(recording).add_section(f"{FORMATS} > 見本の小節 B", "別の補足", "中身。", REASON))
    other = f"{FORMATS} > 見本の小節 B > 別の補足"
    _accepted(_service(recording).rename_heading(other, "補足 2", _read(recording, other).fingerprint, REASON))
    assert _body(recording, path) == "小節 A の補足を直した。"


# ---------------------------------------------------------------- 箇条書きの項目


def test_REQ_540_list_item_add(recording) -> None:
    """箇条書きの項目: 足す。"""
    body = _body(recording, FORMATS)
    new = body.replace("**担当の範囲**", "- 振り返りの会\n\n**担当の範囲**", 1)
    _accepted(_revise(recording, FORMATS, new))
    assert "- 振り返りの会" in _body(recording, FORMATS)


def test_REQ_540_list_item_remove(recording) -> None:
    """箇条書きの項目: 消す。"""
    body = _body(recording, FORMATS)
    item = "- 引き継ぎの段取り\n  続きの行。1 つの項目を 2 行で書いている。\n  - 入れ子の項目\n      - 4 字下げの入れ子の項目\n"
    assert item in body
    _accepted(_revise(recording, FORMATS, body.replace(item, "", 1)))
    assert "引き継ぎの段取り" not in _body(recording, FORMATS)


def test_REQ_540_list_item_reorder(recording) -> None:
    """箇条書きの項目: 並べ替える。"""
    body = _body(recording, FORMATS)
    first = "- 取り組みの進め方\n  1. 決まっていないことを一覧にした\n  2. 週 1 回の確認の場をつくった\n"
    second = "- 引き継ぎの段取り\n  続きの行。1 つの項目を 2 行で書いている。\n  - 入れ子の項目\n      - 4 字下げの入れ子の項目\n"
    _accepted(_revise(recording, FORMATS, body.replace(first + second, second + first, 1)))
    after = _body(recording, FORMATS)
    assert after.index("引き継ぎの段取り") < after.index("取り組みの進め方")


def test_REQ_540_list_item_edit(recording) -> None:
    """箇条書きの項目: 本文を直す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("- 取り組みの進め方", "- 取り組みの進め方（直した）", 1)))
    assert "取り組みの進め方（直した）" in _body(recording, FORMATS)


# ---------------------------------------------------------------- 入れ子の箇条書き


def test_REQ_540_nested_list_add(recording) -> None:
    """入れ子の箇条書き: 入れ子ごと足す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("      - 4 字下げの入れ子の項目", "      - 4 字下げの入れ子の項目\n  - 足した入れ子\n    - その下の入れ子", 1)))
    assert "    - その下の入れ子" in _body(recording, FORMATS)


def test_REQ_540_nested_list_remove(recording) -> None:
    """入れ子の箇条書き: 入れ子ごと消す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("  - 入れ子の項目\n      - 4 字下げの入れ子の項目\n", "", 1)))
    assert "入れ子の項目" not in _body(recording, FORMATS)


def test_REQ_540_nested_list_change_depth(recording) -> None:
    """入れ子の箇条書き: 入れ子の深さを変える。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("      - 4 字下げの入れ子の項目", "    - 4 字下げの入れ子の項目", 1)))
    assert "\n    - 4 字下げの入れ子の項目" in _body(recording, FORMATS)


# ---------------------------------------------------------------- 箇条書きの続きの行


def test_REQ_540_continuation_line_edit(recording) -> None:
    """箇条書きの続きの行: 1 つの項目を複数行のまま直す。"""
    body = _body(recording, FORMATS)
    new = body.replace("  続きの行。1 つの項目を 2 行で書いている。", "  続きの行を直した。\n  もう 1 行足した。", 1)
    _accepted(_revise(recording, FORMATS, new))
    assert "  続きの行を直した。\n  もう 1 行足した。" in _body(recording, FORMATS)


# ---------------------------------------------------------------- 公開可否の行


def _practice_values(settings) -> list[str]:
    repository = MarkdownRepository(settings)
    section = next(item for item in repository.source_sections(CAREER) if item.id == PRACTICE)
    return [value for _, value in repository.disclosure_lines(section)]


def test_REQ_540_disclosure_line_add(recording) -> None:
    """公開可否の行: 足す（申告つき）。"""
    values = _practice_values(recording)
    body = _body(recording, PRACTICE) + "\n- 新しい取り組み\n  - 公開可否: 公開不可（社内の話）"
    _accepted(_revise(recording, PRACTICE, body, [*values, "公開不可（社内の話）"]))
    assert _practice_values(recording)[-1] == "公開不可（社内の話）"


def test_REQ_540_disclosure_line_remove(recording) -> None:
    """公開可否の行: 消す（項目ごと。申告つき）。"""
    values = _practice_values(recording)
    body = _body(recording, PRACTICE).replace("- 引き渡しの記録\n  1. 公開可否：公開可\n  2. 引き渡しの記録を月ごとに残した。\n", "", 1)
    _accepted(_revise(recording, PRACTICE, body, values[:3] + values[4:]))
    assert len(_practice_values(recording)) == len(values) - 1


def test_REQ_540_disclosure_line_reorder(recording) -> None:
    """公開可否の行: 並べ替える（項目ごと。申告つき）。"""
    values = _practice_values(recording)
    body = _body(recording, PRACTICE)
    first = "- 社内の手順書づくり\n  - 公開可否＝公開可（社名は出さない）\n  - 手順書を 3 冊にまとめた。\n"
    second = "- 勉強会での発表\n  公開可否：公開可\n  発表の資料を社内に残した。\n"
    assert first + second in body
    _accepted(_revise(recording, PRACTICE, body.replace(first + second, second + first, 1), [values[0], values[2], values[1], *values[3:]]))
    assert _practice_values(recording)[1:3] == [values[2], values[1]]


def test_REQ_540_disclosure_line_change_value(recording) -> None:
    """公開可否の行: 値を変える（何行目かを渡す）。"""
    _accepted(_service(recording).set_disclosure(PRACTICE, "公開不可（社名を出さない約束）", _read(recording, PRACTICE).fingerprint, REASON, 2))
    assert _practice_values(recording)[1] == "公開不可（社名を出さない約束）"


# ---------------------------------------------------------------- 公開可否の行の別の書き方


@pytest.mark.parametrize(
    "number, line",
    [
        (2, "  - 公開可否＝公開不可（確かめ）"),
        (3, "  公開可否：公開不可（確かめ）"),
        (4, "  1. 公開可否：公開不可（確かめ）"),
        (5, "  **公開可否**：公開不可（確かめ）"),
    ],
    ids=["区切りが＝", "続きの行", "番号つき", "太字のラベル"],
)
def test_REQ_540_disclosure_variant_change_value(recording, number, line) -> None:
    """公開可否の行の別の書き方: 値を変えても、区切り・記号・太字の書き方はそのまま残る。"""
    _accepted(_service(recording).set_disclosure(PRACTICE, "公開不可（確かめ）", _read(recording, PRACTICE).fingerprint, REASON, number))
    assert line in _body(recording, PRACTICE).splitlines()


def test_REQ_540_disclosure_variant_add_and_remove(recording) -> None:
    """公開可否の行の別の書き方: 足す・消す（申告つき。申告が無ければ断られる）。"""
    values = _practice_values(recording)
    added = _body(recording, PRACTICE) + "\n- 別の取り組み\n  公開可否＝公開可"
    refused = _revise(recording, PRACTICE, added)
    assert refused.accepted is False
    _accepted(_revise(recording, PRACTICE, added, [*values, "公開可"]))
    _accepted(_revise(recording, PRACTICE, added.replace("\n- 別の取り組み\n  公開可否＝公開可", ""), values))
    assert _practice_values(recording) == values


# ---------------------------------------------------------------- 番号つきの箇条書き


def test_REQ_540_numbered_list_add(recording) -> None:
    """番号つきの箇条書き: 足す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("  2. 週 1 回の確認の場をつくった", "  2. 週 1 回の確認の場をつくった\n  3. 決めたことを記録に残した", 1)))
    assert "  3. 決めたことを記録に残した" in _body(recording, FORMATS)


def test_REQ_540_numbered_list_remove(recording) -> None:
    """番号つきの箇条書き: 消す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("\n  2. 週 1 回の確認の場をつくった", "", 1)))
    assert "週 1 回の確認の場" not in _body(recording, FORMATS)


def test_REQ_540_numbered_list_reorder(recording) -> None:
    """番号つきの箇条書き: 並べ替える。"""
    body = _body(recording, FORMATS)
    old = "  1. 決まっていないことを一覧にした\n  2. 週 1 回の確認の場をつくった"
    new = "  1. 週 1 回の確認の場をつくった\n  2. 決まっていないことを一覧にした"
    _accepted(_revise(recording, FORMATS, body.replace(old, new, 1)))
    assert new in _body(recording, FORMATS)


# ---------------------------------------------------------------- 表の行


TABLE = "| 項目 | 内容 |\n|---|---|\n| 期間 | 3 か月 |\n| 体制 | 2 名 |"


def _table_edit(settings, new_table) -> None:
    body = _body(settings, FORMATS)
    assert TABLE in body
    _accepted(_revise(settings, FORMATS, body.replace(TABLE, new_table, 1)))
    assert new_table in _body(settings, FORMATS)


def test_REQ_540_table_row_add(recording) -> None:
    """表の行: 行を足す。"""
    _table_edit(recording, TABLE + "\n| 引き渡し | 月末 |")


def test_REQ_540_table_row_remove(recording) -> None:
    """表の行: 行を消す。"""
    _table_edit(recording, "| 項目 | 内容 |\n|---|---|\n| 期間 | 3 か月 |")


def test_REQ_540_table_row_reorder(recording) -> None:
    """表の行: 行を並べ替える。"""
    _table_edit(recording, "| 項目 | 内容 |\n|---|---|\n| 体制 | 2 名 |\n| 期間 | 3 か月 |")


def test_REQ_540_table_row_edit_cell(recording) -> None:
    """表の行: 欄の値を直す（機能の台帳の行も同じ操作で直せる）。"""
    _table_edit(recording, TABLE.replace("3 か月", "4 か月"))
    category = "機能の台帳 > 人と体制をつくる"
    body = _body(recording, category)
    _accepted(_revise(recording, category, body.replace("最初の数か月の判断", "最初の 3 か月の判断", 1)))


def test_REQ_540_table_row_add_column(recording) -> None:
    """表の行: 列を足す。"""
    _table_edit(recording, "| 項目 | 内容 | 備考 |\n|---|---|---|\n| 期間 | 3 か月 | なし |\n| 体制 | 2 名 | なし |")


# ---------------------------------------------------------------- 「名: 値」の欄の行


def test_REQ_540_field_line_edit_value(recording) -> None:
    """「名: 値」の欄の行: 値を直す。"""
    body = _body(recording, "teramina-delivery")
    _accepted(_revise(recording, "teramina-delivery", body.replace("従業員 140 名", "従業員 150 名", 1)))


def test_REQ_540_field_line_add(recording) -> None:
    """「名: 値」の欄の行: 欄を足す。"""
    body = _body(recording, "teramina-delivery")
    _accepted(_revise(recording, "teramina-delivery", body + "\n- 備考: 引き渡し後の問い合わせは 0 件"))


def test_REQ_540_field_line_remove(recording) -> None:
    """「名: 値」の欄の行: 欄を消す（必須でない欄は通り、必須の欄は読めないブロックになるので断る）。"""
    body = _body(recording, "teramina-delivery")
    _accepted(_revise(recording, "teramina-delivery", body + "\n- 備考: 消す欄"))
    _accepted(_revise(recording, "teramina-delivery", body))
    decision = "売り方の決め > 2026-06-01 全体"
    lines = _body(recording, decision).splitlines()
    refused = _revise(recording, decision, "\n".join(line for line in lines if not line.startswith("- 根拠")))
    assert refused.accepted is False


# ---------------------------------------------------------------- 段落の文の行・太字で始まる文の行

PARAGRAPH = "ID を持たない節と、その下の小節。accord が読み書きできる書き方を、架空の中身で 1 つずつ並べておく。"
BOLD_LEAD = "**まとめ** この節の書き方は、どれも架空の中身で書いている。"


def test_REQ_540_paragraph_line_add(recording) -> None:
    """段落の文の行: 足す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body + "\n\n足した段落の文。"))
    assert _body(recording, FORMATS).endswith("足した段落の文。")


def test_REQ_540_paragraph_line_remove(recording) -> None:
    """段落の文の行: 消す。"""
    body = _body(recording, FORMATS)
    assert PARAGRAPH in body
    _accepted(_revise(recording, FORMATS, body.replace(PARAGRAPH + "\n", "", 1)))
    assert PARAGRAPH not in _body(recording, FORMATS)


def test_REQ_540_paragraph_line_edit(recording) -> None:
    """段落の文の行: 直す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("架空の中身で 1 つずつ", "架空の中身で 1 つずつ（直した）", 1)))


def test_REQ_540_bold_lead_line_add(recording) -> None:
    """太字で始まる文の行: 足す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body + "\n\n**補足** 足した太字で始まる文。"))


def test_REQ_540_bold_lead_line_remove(recording) -> None:
    """太字で始まる文の行: 消す。"""
    body = _body(recording, FORMATS)
    assert BOLD_LEAD in body
    _accepted(_revise(recording, FORMATS, body.replace(BOLD_LEAD, "", 1)))
    assert BOLD_LEAD not in _body(recording, FORMATS)


def test_REQ_540_bold_lead_line_edit(recording) -> None:
    """太字で始まる文の行: 直す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace(BOLD_LEAD, BOLD_LEAD.replace("架空の中身", "架空の中身だけ"), 1)))


# ---------------------------------------------------------------- 太字の欄・引用・水平線・コードの囲み


def test_REQ_540_bold_field_edit_value(recording) -> None:
    """太字の欄: 値を直す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("**担当の範囲**：要件の整理から引き渡しまで", "**担当の範囲**：要件の整理だけ", 1)))
    assert "**担当の範囲**：要件の整理だけ" in _body(recording, FORMATS)


def test_REQ_540_quote_add(recording) -> None:
    """引用: 足す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body + "\n\n> 足した引用の行。"))


def test_REQ_540_quote_remove(recording) -> None:
    """引用: 消す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("> 引用の行。聞き取りで本人が話したことを、そのまま残す。\n\n", "", 1)))
    assert "> 引用の行" not in _body(recording, FORMATS)


def test_REQ_540_quote_edit(recording) -> None:
    """引用: 直す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("> 引用の行。", "> 引用の行（直した）。", 1)))


def test_REQ_540_horizontal_rule_not_a_section_border(recording) -> None:
    """水平線: 節の境と取り違えない（水平線の後ろも、同じ節の本文として読む）。"""
    body = _body(recording, FORMATS)
    assert "---" in body.splitlines()
    assert body.index("| 項目 | 内容 |") > body.index("---")


def test_REQ_540_horizontal_rule_add(recording) -> None:
    """水平線: 足す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body + "\n\n---\n\n水平線の後の段落。"))
    assert _body(recording, FORMATS).endswith("水平線の後の段落。")


def test_REQ_540_horizontal_rule_remove(recording) -> None:
    """水平線: 消す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("\n---\n", "\n", 1)))
    assert "---" not in _body(recording, FORMATS).splitlines()


FENCE = "```text\n集計の手順の覚え書き\n1 日目に取り込む\n```"


def test_REQ_540_code_fence_edit_inside(recording) -> None:
    """コードの囲み: 囲みの中を直す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace("1 日目に取り込む", "2 日目に取り込む", 1)))


def test_REQ_540_code_fence_add(recording) -> None:
    """コードの囲み: 囲みを足す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body + "\n\n```text\n足した覚え書き\n```"))


def test_REQ_540_code_fence_remove(recording) -> None:
    """コードの囲み: 囲みを消す。"""
    body = _body(recording, FORMATS)
    _accepted(_revise(recording, FORMATS, body.replace(FENCE, "", 1)))
    assert "集計の手順の覚え書き" not in _body(recording, FORMATS)


def test_REQ_540_code_fence_heading_line_is_refused(recording) -> None:
    """コードの囲み: 囲みの中に「#」で始まる行を書くと、見出しとして読まれるので断られる。"""
    before = source_digest(recording.source_dir)
    body = _body(recording, FORMATS)
    result = _revise(recording, FORMATS, body.replace("1 日目に取り込む", "# 1 日目に取り込む", 1))
    assert result.accepted is False
    assert result.rejection.constraint == "本文に見出しの行を書かない"
    assert source_digest(recording.source_dir) == before


# ---------------------------------------------------------------- ID を持つ行


def test_REQ_540_id_line_change_is_refused(recording) -> None:
    """ID を持つ行: ID を変える変更は断られる。"""
    before = source_digest(recording.source_dir)
    body = _body(recording, PRACTICE)
    result = _revise(recording, PRACTICE, body.replace("sample-practice", "sample-practice-2", 1))
    assert result.accepted is False
    assert result.rejection.constraint == "ID の欄を元の値のまま残す"
    assert source_digest(recording.source_dir) == before


def test_REQ_540_id_section_remove(recording) -> None:
    """ID を持つ行: 指す側の無い ID の節は消せ、指す側のある ID の節は書いた後の検査の違反で断られる。"""
    path = f"{FORMATS} > 見本の取り組み"
    _accepted(_service(recording).remove_section(path, _read(recording, path).fingerprint, REASON))
    referenced = _service(recording).remove_section(
        "teramina-delivery", _read(recording, "teramina-delivery").fingerprint, REASON
    )
    assert referenced.accepted is False


def test_REQ_540_id_section_move(recording) -> None:
    """ID を持つ行: ID を持つ節を動かせる（ID はそのまま残る）。"""
    path = f"{FORMATS} > 見本の取り組み"
    _accepted(_service(recording).move_section(path, OUTSIDE, _read(recording, path).fingerprint, REASON))
    assert _read(recording, PRACTICE).heading_path == f"{OUTSIDE} > 見本の取り組み"


# ---------------------------------------------------------------- 見出しの階層の飛び


def test_REQ_540_heading_skip_added_section_is_one_below_parent(recording) -> None:
    """見出しの階層の飛び: 足した節の深さは、いつも親の 1 段下になる。"""
    for parent in (TITLE, FORMATS, f"{FORMATS} > 見本の小節 A > 補足"):
        _accepted(_service(recording).add_section(parent, "深さを見る節", "中身。", REASON))
        levels = _levels(recording)
        assert levels[f"{parent} > 深さを見る節"] == levels[parent] + 1


def test_REQ_540_heading_skip_moved_section_is_one_below_parent(recording) -> None:
    """見出しの階層の飛び: 動かした節の深さは、いつも新しい親の 1 段下になり、下位の節も同じ段数ずれる。"""
    path = f"{FORMATS} > 見本の小節 A"
    target = f"{FORMATS} > 見本の小節 B > 補足"
    _accepted(_service(recording).move_section(path, target, _read(recording, path).fingerprint, REASON))
    levels = _levels(recording)
    moved = f"{target} > 見本の小節 A"
    assert levels[moved] == levels[target] + 1
    assert levels[f"{moved} > 補足"] == levels[moved] + 1

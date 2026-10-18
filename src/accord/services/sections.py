"""正本のファイルを節で読み書きする操作と、正本の書き出し。

正本のファイルは、人も AI のセッションも直接開かない。読みも書きも、ここにある操作だけで行う。
読みは 3 つ（節の一覧・節の読み・事実の検索）で、正本を 1 バイトも書き換えない。公開不可の節も
返す。AI のセッションが事実を確かめるための読みで、外に出す材料ではないからである。

書きは 7 つ。中身を変える 2 つ（事実の登記・節の書き換え）と、節の構造を変える 4 つ（見出しの変更・
節の追加・節の削除・節の移動）と、公開可否の変更である。どれも書く瞬間に制約で断り、断るときは
正本を 1 バイトも変えない。書いた後の正本に、書く前に無かった整合の検査の違反か、必須の欄が欠けて
読めないブロックが出るなら書かない。ただし「写しの鮮度」の違反は断る理由にせず、書いた後に
読み比べるべき写しとして返す。元の節を正しく直すたびに写しが古くなるのは当然で、それで書き込みを
止めると事実を直せなくなるためである。書いた後の正本の検査は、正本のファイルを一時の場所に写した
上で走らせる（本物のファイルは、検査が通るまで変えない）。書き込みの操作は、変えたファイルを
いつも 1 件のコミットにする。

書き出しは、正本の各ファイルをファイルの名前の見出しでつないだ Markdown を、呼ぶ側が渡した書き出し先の
ファイル 1 つに書く。書き出し先は、経歴データの置き場と提示物の置き場の外の、親ディレクトリが既にある
新しいファイルに限る。既にあるファイルと symlink には書かず（上書きしない）、ディレクトリも作らない。
返り値にはファイルの名前と字数だけを入れる。

どの返り値にも、正本の置き場の絶対パスを入れない。ファイルは accord の形の名前で指す。
"""
from __future__ import annotations

import dataclasses
import difflib
import shutil
import tempfile
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

from accord.models.constraints import CONSTRAINTS
from accord.models.results import (
    ExportResult,
    FactHit,
    FactSearch,
    NextAction,
    Rejection,
    SectionEntry,
    SectionList,
    SectionText,
    SourceDefect,
    SourceSection,
    Violation,
    WriteResult,
)
from accord.repository.markdown_repository import MarkdownRepository
from accord.repository.sections import (
    MAX_HEADING_LEVEL,
    PATH_SEPARATOR,
    has_heading_line,
    heading_text_is_valid,
)
from accord.services.recording import WriteRecorder, new_violations
from accord.vocabulary.settings import Settings

# 操作の名前。次の一手にそのまま載せる。
LIST_OPERATION = "list_sections"
READ_OPERATION = "read_section"
SEARCH_OPERATION = "search_facts"
RECORD_FACT_OPERATION = "record_fact"
REVISE_OPERATION = "revise_section"
RENAME_OPERATION = "rename_heading"
ADD_OPERATION = "add_section"
REMOVE_OPERATION = "remove_section"
MOVE_OPERATION = "move_section"
DISCLOSURE_OPERATION = "set_disclosure"
EXPORT_OPERATION = "export_source"

# 写しの鮮度。書く瞬間には断らず、読み比べる写しとして返す。
CONSTRAINT_BY_NAME = {constraint.name: constraint for constraint in CONSTRAINTS}
COPY_FRESHNESS = CONSTRAINT_BY_NAME["写しの鮮度"].name

# この操作が名乗る断りの名前。型の正本の制約ではなく、節の読み書きの操作が持つ決まりである。
SECTION_EXISTS = "節の実在"
SECTION_UNIQUE = "見出しの道筋の重なり"
FACT_REQUIRED_FIELDS = "事実の登記の必須欄"
FACT_DATE_FORMAT = "事実の日付の書き方"
FACT_ONE_LINE = "事実は 1 件 1 行"
FINGERPRINT_MATCHES = "読んだときの指紋の一致"
NO_HEADING_IN_BODY = "本文に見出しの行を書かない"
ID_FIELD_KEPT = "ID の欄を元の値のまま残す"
FACT_NOT_A_FIELD = "事実の文を欄の書き方で書かない"
REVISION_REASON_REQUIRED = "節の書き換えの理由"
EXPORT_OUTSIDE_DATA = "書き出し先は置き場の外"
EXPORT_NEW_FILE = "書き出し先は新しいファイル"
HEADING_FORMAT = "見出しの書き方"
DEPTH_LIMIT = "見出しの深さの上限"
PRECEDE_A_CHILD = "前に置く節は親の直下の節"
KEEP_SUBSECTIONS = "下位の節を持つ節は消さない"
NOT_UNDER_ITSELF = "自分の下へは動かさない"
SAME_FILE_ONLY = "ファイルをまたいで動かさない"
DISCLOSURE_NEEDS_ID = "公開可否は ID の欄を持つ節に置く"
DISCLOSURE_FORMAT = "公開可否の書き方"
SIBLING_HEADINGS_UNIQUE = "同じ親の下の見出しの重なり"
REASON_REQUIRED = "書き換えの理由"
DISCLOSURE_LINE_NUMBER = "公開可否の行の番号"
DISCLOSURE_DECLARED = "公開可否の行の申告"
ITEM_NEEDS_DISCLOSURE = "公開可否の行の無い項目を足さない"
SOURCE_FILE_EXISTS = "正本のファイルの実在"
READABLE_BLOCKS = "必須の欄が欠けて読めないブロックを作らない"
FIELD_VALUE_TYPE = "欄の値を型に合わせる"

# 読めないブロックの断りに名乗る、型の正本の制約。決めと公開記録は必須欄の制約を型の正本が持つ。
DEFECT_CONSTRAINTS = {
    "positioning": CONSTRAINT_BY_NAME["決めの必須欄"].name,
    "public_records": CONSTRAINT_BY_NAME["公開記録の必須欄"].name,
}

# 欄の名前。欠けた欄の断りに載せる。
FACT_FIELD = "事実の文"
SOURCE_FIELD = "出所"
DATE_FIELD = "日付"
REASON_FIELD = "理由"
LINE_FIELD = "line"
DISCLOSURES_FIELD = "disclosures"

# 見出しの道筋とファイルの名前を 1 つの文字列にするときのつなぎ。2 つ以上の節に当たったときの候補は
# この形で返し、そのまま渡し直せば 1 つに決まる。
FILE_SEPARATOR = " :: "

# 事実の検索で返す行の上限。
SEARCH_LIMIT = 50

# 近い候補を探すときの緩さと数。
CLOSE_CUTOFF = 0.3
CLOSE_COUNT = 5


def normalize_text(text: str) -> str:
    """全角と半角、大文字と小文字の違いを落とした形にする。事実の検索の比べ方はこの 1 か所が持つ。"""
    # spec: REQ-434
    return unicodedata.normalize("NFKC", text).casefold()


def qualified(section: SourceSection) -> str:
    """節を、ファイルの名前つきの見出しの道筋 1 つの文字列にする。"""
    return f"{section.file}{FILE_SEPARATOR}{section.heading_path}"


class SectionService:
    """正本のファイルを節で読み書きし、書き出す。"""

    def __init__(
        self,
        settings: Settings,
        repository: MarkdownRepository | None = None,
        recorder: WriteRecorder | None = None,
        watch=None,
    ) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)
        self.recorder = recorder or WriteRecorder(settings)
        self.watch = watch

    def _watch(self):
        """読みの前の整合の検査。サーバーが 1 つを配って共有させる。"""
        if self.watch is None:
            from accord.services.watch import SourceWatch

            self.watch = SourceWatch(self.settings, self.repository)
        return self.watch

    # ------------------------------------------------------------ 読む

    def _sections(self, names: list[str] | None = None) -> list[SourceSection]:
        found: list[SourceSection] = []
        for name in names if names is not None else self.repository.source_file_names():
            found.extend(self.repository.source_sections(name))
        return found

    def list_sections(self, file: str | None = None) -> SectionList:
        """正本の各ファイルの節を、ファイルの名前・見出しの道筋・指紋・字数で一覧にする。"""
        result = self._list_sections(file)
        # spec: REQ-458
        result.consistency_notice = self._watch().notice()
        return result

    def _list_sections(self, file: str | None) -> SectionList:
        names = self.repository.source_file_names()
        if file is not None and file not in names:
            # spec: REQ-428
            return SectionList(
                candidates=names,
                warnings=[
                    f"ファイル「{file}」は正本のファイルに無い。"
                    f"候補のファイルの名前をそのまま渡して、もう一度 {LIST_OPERATION} を呼ぶ。"
                ],
            )
        # spec: REQ-427
        targets = [file] if file is not None else names
        entries = [
            # spec: REQ-425
            SectionEntry(
                file=section.file,
                heading_path=section.heading_path,
                fingerprint=section.fingerprint,
                chars=len(section.body),
                # spec: REQ-426
                id=section.id,
                disclosure=section.disclosure,
            )
            for section in self._sections(targets)
        ]
        return SectionList(sections=entries)

    def _resolve(
        self, reference: str, names: list[str] | None = None
    ) -> tuple[list[SourceSection], list[str]]:
        """ID か見出しの道筋（ファイルの名前つきでもよい）で節を探す。当たった節と、近い候補を返す。"""
        wanted = (reference or "").strip()
        scope = names if names is not None else self.repository.source_file_names()
        file_name, separator, path = wanted.partition(FILE_SEPARATOR)
        if separator and file_name.strip() in scope:
            scope, wanted = [file_name.strip()], path.strip()
        sections = self._sections(scope)
        matched = [
            section
            for section in sections
            if section.heading_path == wanted or (section.id is not None and section.id == wanted)
        ]
        if matched:
            return matched, []
        return [], self._close_paths(wanted, sections)

    @staticmethod
    def _close_paths(wanted: str, sections: list[SourceSection]) -> list[str]:
        """渡された文字列に近い見出しの道筋を返す。末尾の見出しが一致するものを先に並べる。"""
        paths = list(dict.fromkeys(section.heading_path for section in sections))
        tail = [
            path
            for path in paths
            if wanted and (path.endswith(f" > {wanted}") or path.rsplit(" > ", 1)[-1] == wanted)
        ]
        close = difflib.get_close_matches(wanted, paths, n=CLOSE_COUNT, cutoff=CLOSE_CUTOFF)
        headings = {section.heading_path.rsplit(" > ", 1)[-1]: section.heading_path for section in sections}
        by_heading = [
            headings[name]
            for name in difflib.get_close_matches(
                wanted, list(headings), n=CLOSE_COUNT, cutoff=CLOSE_CUTOFF
            )
        ]
        found = list(dict.fromkeys([*tail, *close, *by_heading]))
        return found[:CLOSE_COUNT] or paths[:CLOSE_COUNT]

    def read_section(self, section: str) -> SectionText:
        """ID か見出しの道筋で節を 1 つ読み、本文と指紋を返す。正本は 1 バイトも書き換えない。"""
        result = self._read_section(section)
        # spec: REQ-458
        result.consistency_notice = self._watch().notice()
        return result

    def _read_section(self, reference: str) -> SectionText:
        matched, candidates = self._resolve(reference)
        if not matched:
            # spec: REQ-431
            return SectionText(
                candidates=candidates,
                warnings=[
                    f"「{reference}」に当たる節が無い。ID か、見出しの道筋（最上位の見出しから"
                    "「 > 」でつないだもの）を渡す。近い見出しの道筋を候補に挙げた。"
                ],
            )
        if len(matched) > 1:
            # spec: REQ-432
            return SectionText(
                candidates=[qualified(section) for section in matched],
                warnings=[
                    f"「{reference}」に当たる節が {len(matched)} つある。"
                    "候補のファイルの名前つきの見出しの道筋をそのまま渡して、もう一度呼ぶ。"
                ],
            )
        section = matched[0]
        # spec: REQ-429
        return SectionText(
            file=section.file,
            heading_path=section.heading_path,
            # spec: REQ-430
            body=section.body,
            fingerprint=section.fingerprint,
            id=section.id,
            disclosure=section.disclosure,
        )

    def search_facts(self, query: str) -> FactSearch:
        """語を含む行を、ファイルの名前と見出しの道筋と行の文で返す。正本は書き換えない。"""
        result = self._search_facts(query)
        # spec: REQ-458
        result.consistency_notice = self._watch().notice()
        return result

    def _search_facts(self, query: str) -> FactSearch:
        wanted = normalize_text((query or "").strip())
        if not wanted:
            return FactSearch(
                query=query or "",
                warnings=[f"探す語が空なので、何も探さなかった。語を渡して {SEARCH_OPERATION} を呼ぶ。"],
            )
        hits: list[FactHit] = []
        for name in self.repository.source_file_names():
            for path, line in self.repository.source_lines(name):
                # spec: REQ-433
                if wanted in normalize_text(line):
                    hits.append(FactHit(file=name, heading_path=path, line=line))
        warnings: list[str] = []
        # spec: REQ-435
        if len(hits) > SEARCH_LIMIT:
            warnings.append(
                f"当たった行は {len(hits)} 件で、先頭の {SEARCH_LIMIT} 件だけを返した。"
                "語を絞るか、節の読みで節ごとに読む。"
            )
        return FactSearch(query=query, total=len(hits), hits=hits[:SEARCH_LIMIT], warnings=warnings)

    # ------------------------------------------------------------ 書く

    def record_fact(self, section: str, fact: str, source: str, date_text: str) -> WriteResult:
        """経歴の正本の節 1 つの本文の末尾に、事実の文と日付と出所を書いた箇条の 1 行を足す。"""
        career = self.settings.files.get("career", "")
        missing = [
            label
            for label, value in ((FACT_FIELD, fact), (SOURCE_FIELD, source))
            if not str(value or "").strip()
        ]
        # spec: REQ-439
        if missing:
            return self._refuse(
                FACT_REQUIRED_FIELDS,
                "事実の登記の欄" + "、".join(f"「{name}」" for name in missing) + "が空なので、書かなかった。",
                RECORD_FACT_OPERATION,
                missing_fields=missing,
                example="事実の文は 1 行の文、出所は確かめた先（例「契約書」「本人の申告（2026-10-13 の聞き取り）」）。",
            )
        # spec: REQ-441
        if "\n" in fact or "\r" in fact:
            return self._refuse(
                FACT_ONE_LINE,
                "事実の文が改行を含むので、書かなかった。事実は 1 件 1 行で登記する。"
                "2 つ以上の事実なら、1 件ずつ呼ぶ。",
                RECORD_FACT_OPERATION,
                example="- 月次の集計を 3 日から 1 日に縮めた（のように 1 行で書く）",
            )
        recorded_on = _as_date(date_text)
        # spec: REQ-440
        if recorded_on is None:
            return self._refuse(
                FACT_DATE_FORMAT,
                f"日付「{date_text}」が読めないので、書かなかった。",
                RECORD_FACT_OPERATION,
                missing_fields=[DATE_FIELD],
                example="日付は 2026-10-13 の形（年-月-日）で渡す。",
            )

        matched, candidates = self._resolve(section, [career] if career else [])
        # spec: REQ-438
        if len(matched) != 1:
            return self._refuse(
                SECTION_EXISTS,
                f"節「{section}」は、経歴の正本 {career} に"
                + ("2 つ以上ある" if matched else "無い")
                + "ので、書かなかった。",
                RECORD_FACT_OPERATION,
                candidates=[item.heading_path for item in matched] or candidates,
                example="候補の見出しの道筋か、節の ID をそのまま渡して、もう一度呼ぶ。",
            )
        target = matched[0]
        source_text = " ".join(str(source).split())
        # spec: REQ-437
        line = f"- {fact.strip()}（{recorded_on.isoformat()}、{SOURCE_FIELD}: {source_text}）"
        new_text = self.repository.appended_text(target, line)
        after = self._section_after(target, new_text)
        # spec: REQ-469
        if after is None or (after.id, after.disclosure, after.private) != (
            target.id,
            target.disclosure,
            target.private,
        ):
            return self._refuse(
                FACT_NOT_A_FIELD,
                f"足す行で、節「{target.heading_path}」の ID か公開可否の欄の値が変わるので、"
                "書かなかった。事実の文を「欄の名前: 値」の書き方で書くと、節の欄として読まれる。"
                f"ID はどの操作でも変えない。公開可否は {DISCLOSURE_OPERATION} で変える。",
                RECORD_FACT_OPERATION,
                example="事実は「〜した」「〜を担当した」のような文で書く。",
            )
        return self._write(
            target.file,
            new_text,
            RECORD_FACT_OPERATION,
            summary=f"事実の登記 {target.heading_path}",
            recorded={"足した行": line},
            heading_path=target.heading_path,
            locate=_same_place(target),
        )

    def revise_section(
        self,
        section: str,
        body: str,
        fingerprint: str,
        reason: str,
        disclosures: list[str] | None = None,
    ) -> WriteResult:
        """節 1 つの本文を新しい本文に置き換える。見出しの行と下位の見出しの節は変えない。

        正本のどのファイルの節も書き換えられる。型の決まり（ID の形・重なり・指す先の実在・語彙）は、
        書いた後の整合の検査が見るので、型の操作と同じ決まりで断られる。公開可否の行が変わる本文は、
        書いた後の公開可否の行の値の並び（disclosures、申告）が実際と一致するときだけ書き、変わる前と
        後の公開可否の行を返り値とコミットの説明に載せる。
        """
        target, refusal = self._find_one(section, REVISE_OPERATION)
        if refusal is not None:
            return refusal
        # spec: REQ-485
        # 書ける正本を絞らない。どのファイルの節も、同じ断りの条件で書く。
        # spec: REQ-448
        if not str(reason or "").strip():
            return self._refuse(
                REVISION_REASON_REQUIRED,
                f"節の書き換えの欄「{REASON_FIELD}」が空なので、書かなかった。",
                REVISE_OPERATION,
                missing_fields=[REASON_FIELD],
                example="理由は、何をなぜ直すかの 1 文（例「契約書で期間を確かめ直した」）。",
            )
        # spec: REQ-445
        stale = self._stale_fingerprint(target, fingerprint)
        if stale is not None:
            return stale
        # spec: REQ-446
        if has_heading_line(body or ""):
            return self._refuse(
                NO_HEADING_IN_BODY,
                "新しい本文が見出しの行を含むので、書かなかった。"
                "節の新設と見出しの変更は、この操作ではできない。"
                f"節を足すときは {ADD_OPERATION}、見出しを変えるときは {RENAME_OPERATION} を呼ぶ。",
                REVISE_OPERATION,
                candidates=[ADD_OPERATION, RENAME_OPERATION],
                example="本文には見出しの行（# で始まる行）を書かず、節の中身だけを渡す。",
            )

        new_text = self.repository.replaced_text(target, body or "")
        after = self._section_after(target, new_text)
        # spec: REQ-447
        if target.id is not None and (after is None or after.id != target.id):
            return self._refuse(
                ID_FIELD_KEPT,
                f"新しい本文で、節「{target.heading_path}」の ID の欄"
                f"「{target.id}」が消えるか値が変わるので、書かなかった。"
                "ID の欄は元の値のまま残す（ほかの項目がこの ID で節を指している）。",
                REVISE_OPERATION,
                example=f"新しい本文に「- ID: {target.id}」の行をそのまま残す。",
            )
        rows_before = self.repository.disclosure_lines(target)
        rows_after = self.repository.disclosure_lines_in(target, new_text)
        if len(rows_before) >= 2:
            before_items = Counter(head for head, has in self.repository.disclosure_items(target) if not has)
            after_items = [
                head for head, has in self.repository.disclosure_items(target, new_text) if not has
            ]
            added = [head for head, count in Counter(after_items).items() if count > before_items.get(head, 0)]
            # spec: REQ-538
            if sum(Counter(after_items).values()) > sum(before_items.values()):
                return self._refuse(
                    ITEM_NEEDS_DISCLOSURE,
                    f"節「{target.heading_path}」は公開可否の行を {len(rows_before)} 行持つのに、新しい本文で"
                    "公開可否の行を持たない箇条書きの項目が増えるので、書かなかった。足す項目には、"
                    "外に出してよいかを決めた公開可否の行を添える（既定の値では埋めない）。増える項目: "
                    + " / ".join(added),
                    REVISE_OPERATION,
                    candidates=added,
                    example="項目の中に「  - 公開可否: 公開可（…）」のような行を足し、申告にも並べて呼ぶ。",
                )
        values_after = [value for _, value in rows_after]
        declared = None if disclosures is None else [str(item).strip() for item in disclosures]
        # 変わったかは、（属する項目の先頭の行・値）の組の並びで見る。値の並びが同じでも、
        # 公開可否の行が別の項目へ移れば、どの項目の公開可否が変わったかが変わるため。
        pairs_before = _item_value_pairs(self.repository.disclosure_lines_by_item(target), rows_before)
        pairs_after = _item_value_pairs(
            self.repository.disclosure_lines_by_item(target, new_text), rows_after
        )
        changed = pairs_before != pairs_after
        # spec: REQ-537
        if (changed and declared is None) or (declared is not None and declared != values_after):
            return self._refuse(
                DISCLOSURE_DECLARED,
                f"新しい本文で、節「{target.heading_path}」の公開可否の行が"
                + ("変わるのに、申告が無い" if declared is None else "、申告と違う並びになる")
                + "ので、書かなかった。公開可否の行を変えるときは、書いた後の公開可否の行の値を上から順に、"
                f"申告の欄「{DISCLOSURES_FIELD}」に並べて渡す。書いた後の実際の並び: "
                + (" / ".join(values_after) if values_after else "（公開可否の行なし）"),
                REVISE_OPERATION,
                missing_fields=[DISCLOSURES_FIELD],
                candidates=values_after,
                example=f"{DISCLOSURES_FIELD} に、候補の値をこの順のまま渡す。1 行の値だけを変えるなら "
                f"{DISCLOSURE_OPERATION} でもよい。",
            )
        recorded: dict = {"理由": str(reason).strip()}
        notices: list[str] = []
        summary = f"節の書き換え {target.heading_path}: {_one_line(reason)}"
        if changed:
            # spec: REQ-536
            # 公開可否の行の 1 つずつに、その行が属する項目の先頭の行（節の欄なら「節の欄」）を添える。
            lines_before = _by_item(self.repository.disclosure_lines_by_item(target))
            lines_after = _by_item(self.repository.disclosure_lines_by_item(target, new_text))
            recorded["変わる前の公開可否の行"] = lines_before
            recorded["変わった後の公開可否の行"] = lines_after
            summary += (
                "（公開可否の行の変更 前: " + (" / ".join(map(_item_text, lines_before)) or "なし")
                + " → 後: " + (" / ".join(map(_item_text, lines_after)) or "なし") + "）"
            )
            # spec: REQ-539
            if target.private and after is not None and not after.private:
                recorded["材料に新しく出る"] = True
                notices.append(
                    f"節「{target.heading_path}」は公開不可でなくなったので、材料の取り出しに新しく出る。"
                )
        return self._write(
            target.file,
            new_text,
            REVISE_OPERATION,
            summary=summary,
            recorded=recorded,
            heading_path=target.heading_path,
            locate=_same_place(target),
            notices=notices,
        )

    # ------------------------------------------------------------ 節の構造と公開可否を変える

    def rename_heading(self, section: str, heading: str, fingerprint: str, reason: str) -> WriteResult:
        """節の見出しの文字だけを置き換える。深さ・本文・下位の節は変えない。"""
        target, refusal = self._find_one(section, RENAME_OPERATION)
        if refusal is not None:
            return refusal
        refusal = (
            self._bad_heading(heading, RENAME_OPERATION)
            or self._missing_reason(reason, RENAME_OPERATION)
            or self._stale_fingerprint(target, fingerprint)
        )
        if refusal is not None:
            return refusal
        new_heading = heading.strip()
        # spec: REQ-470
        new_text = self.repository.renamed_text(target, new_heading)
        refusal = self._duplicated_headings(target.file, new_text, RENAME_OPERATION)
        if refusal is not None:
            return refusal
        return self._write(
            target.file,
            new_text,
            RENAME_OPERATION,
            summary=f"見出しの変更 {target.heading_path} → {new_heading}: {_one_line(reason)}",
            recorded={"元の見出し": target.heading, "新しい見出し": new_heading, "理由": str(reason).strip()},
            heading_path=target.heading_path,
            locate=lambda sections: next(
                (item for item in sections if item.start == target.start), None
            ),
        )

    def add_section(
        self,
        parent: str | None,
        heading: str,
        body: str,
        reason: str,
        before: str | None = None,
        file: str | None = None,
    ) -> WriteResult:
        """親の節より 1 段深い節を、親の下位の節の末尾（before を渡せばその節の直前）に足す。

        親の節を渡さずにファイルを渡すと、そのファイルの末尾に深さ 1 の節を足す（before に深さ 1 の
        節を渡せばその直前）。
        """
        refusal = self._unknown_file(file, ADD_OPERATION)
        if refusal is not None:
            return refusal
        target: SourceSection | None = None
        if str(parent or "").strip():
            target, refusal = self._find_one(parent, ADD_OPERATION, file)
            if refusal is not None:
                return refusal
            file_name = target.file
        else:
            file_name, refusal = self._known_file(file, ADD_OPERATION)
            if refusal is not None:
                return refusal
        refusal = self._bad_heading(heading, ADD_OPERATION)
        if refusal is not None:
            return refusal
        # spec: REQ-480
        if has_heading_line(body or ""):
            return self._refuse(
                NO_HEADING_IN_BODY,
                "足す節の本文が見出しの行を含むので、書かなかった。"
                f"下位の節は、{ADD_OPERATION} を重ねて 1 つずつ作る（足した節を親にして、もう一度呼ぶ）。",
                ADD_OPERATION,
                example="本文には見出しの行（# で始まる行）を書かず、節の中身だけを渡す。",
            )
        refusal = self._missing_reason(reason, ADD_OPERATION)
        if refusal is not None:
            return refusal
        # spec: REQ-475
        if target is not None and target.level >= MAX_HEADING_LEVEL:
            return self._refuse(
                DEPTH_LIMIT,
                f"親の節「{target.heading_path}」の見出しの深さが {MAX_HEADING_LEVEL} なので、"
                "書かなかった。それより深い見出しは作れない。",
                ADD_OPERATION,
                example="もっと浅い節を親にして足す。",
            )
        anchor, refusal = self._child_to_precede(file_name, target, before, ADD_OPERATION)
        if refusal is not None:
            return refusal
        new_heading = heading.strip()
        # spec: REQ-472
        # spec: REQ-473
        # spec: REQ-530
        new_text = self.repository.added_text(file_name, target, new_heading, body or "", anchor)
        refusal = self._duplicated_headings(file_name, new_text, ADD_OPERATION)
        if refusal is not None:
            return refusal
        new_path = (
            f"{target.heading_path}{PATH_SEPARATOR}{new_heading}" if target is not None else new_heading
        )
        return self._write(
            file_name,
            new_text,
            ADD_OPERATION,
            summary=f"節の追加 {new_path}: {_one_line(reason)}",
            recorded={
                "親の節": target.heading_path if target is not None else "",
                "足した見出し": new_heading,
                "理由": str(reason).strip(),
            },
            heading_path=new_path,
            locate=lambda sections: next(
                (item for item in sections if item.heading_path == new_path), None
            ),
        )

    def remove_section(self, section: str, fingerprint: str, reason: str) -> WriteResult:
        """節の見出しの行と本文を消す。下位の節を持つ節は消さない。"""
        target, refusal = self._find_one(section, REMOVE_OPERATION)
        if refusal is not None:
            return refusal
        refusal = self._missing_reason(reason, REMOVE_OPERATION) or self._stale_fingerprint(
            target, fingerprint
        )
        if refusal is not None:
            return refusal
        children = _descendants(self.repository.source_sections(target.file), target)
        # spec: REQ-477
        if children:
            return self._refuse(
                KEEP_SUBSECTIONS,
                f"節「{target.heading_path}」は下位の節を {len(children)} つ持つので、書かなかった。"
                f"先に下位の節を 1 つずつ {REMOVE_OPERATION} で消してから、この節を消す。",
                REMOVE_OPERATION,
                candidates=[item.heading_path for item in children],
                example="候補の見出しの道筋を、深いものから順に渡して消す。",
            )
        # spec: REQ-476
        new_text = self.repository.removed_text(target)
        return self._write(
            target.file,
            new_text,
            REMOVE_OPERATION,
            summary=f"節の削除 {target.heading_path}: {_one_line(reason)}",
            recorded={"消した節": target.heading_path, "理由": str(reason).strip()},
            heading_path=target.heading_path,
        )

    def move_section(
        self,
        section: str,
        new_parent: str | None,
        fingerprint: str,
        reason: str,
        before: str | None = None,
        file: str | None = None,
    ) -> WriteResult:
        """節を下位の節ごと、新しい親の下位の末尾（before を渡せばその節の直前）へ移す。

        新しい親を渡さなければ、同じファイルの深さ 1 の節として末尾（before に深さ 1 の節を渡せば
        その直前）へ移す。
        """
        refusal = self._unknown_file(file, MOVE_OPERATION)
        if refusal is not None:
            return refusal
        target, refusal = self._find_one(section, MOVE_OPERATION, file)
        if refusal is not None:
            return refusal
        parent: SourceSection | None = None
        if str(new_parent or "").strip():
            parent, refusal = self._find_one(new_parent, MOVE_OPERATION, file)
            if refusal is not None:
                return refusal
        refusal = self._missing_reason(reason, MOVE_OPERATION) or self._stale_fingerprint(
            target, fingerprint
        )
        if refusal is not None:
            return refusal
        # spec: REQ-495
        if parent is not None and parent.file != target.file:
            return self._refuse(
                SAME_FILE_ONLY,
                f"動かす節は {target.file}、新しい親の節は {parent.file} にあるので、書かなかった。"
                "ファイルをまたいでは動かせない（ファイルごとに読み方が違う）。",
                MOVE_OPERATION,
                candidates=[
                    item.heading_path
                    for item in self.repository.source_sections(target.file)
                    if item.start != target.start
                ][:CLOSE_COUNT],
                example=f"新しい親には、{target.file} の中の節を渡す。",
            )
        sections = self.repository.source_sections(target.file)
        inside = [target.start, *(item.start for item in _descendants(sections, target))]
        # spec: REQ-493
        if parent is not None and parent.start in inside:
            return self._refuse(
                NOT_UNDER_ITSELF,
                f"新しい親の節「{parent.heading_path}」は、動かす節そのものかその下位の節なので、"
                "書かなかった。自分の下へは動かせない。",
                MOVE_OPERATION,
                example="動かす節の外にある節を、新しい親に渡す。",
            )
        levels = self.repository.moved_levels(target, parent)
        moving = [target, *_descendants(sections, target)]
        too_deep = [item.heading_path for item, level in zip(moving, levels) if level > MAX_HEADING_LEVEL]
        # spec: REQ-494
        if too_deep:
            return self._refuse(
                DEPTH_LIMIT,
                f"動かした後に、見出しの深さが {MAX_HEADING_LEVEL} を超える節が {len(too_deep)} つ出るので、"
                "書かなかった。深さが足りない。",
                MOVE_OPERATION,
                candidates=too_deep,
                example="もっと浅い節を新しい親に渡すか、深い下位の節を先に動かす。",
            )
        anchor, refusal = self._child_to_precede(target.file, parent, before, MOVE_OPERATION)
        if refusal is not None:
            return refusal
        # spec: REQ-491
        # spec: REQ-492
        # spec: REQ-531
        new_text = self.repository.moved_text(target, parent, anchor)
        refusal = self._duplicated_headings(target.file, new_text, MOVE_OPERATION)
        if refusal is not None:
            return refusal
        new_path = (
            f"{parent.heading_path}{PATH_SEPARATOR}{target.heading}" if parent is not None else target.heading
        )
        return self._write(
            target.file,
            new_text,
            MOVE_OPERATION,
            summary=f"節の移動 {target.heading_path} → {new_path}: {_one_line(reason)}",
            recorded={
                "元の見出しの道筋": target.heading_path,
                "新しい親の節": parent.heading_path if parent is not None else "",
                "理由": str(reason).strip(),
            },
            heading_path=new_path,
            locate=lambda found: next((item for item in found if item.heading_path == new_path), None),
        )

    def set_disclosure(
        self,
        section: str,
        disclosure: str,
        fingerprint: str,
        reason: str,
        line: int | None = None,
    ) -> WriteResult:
        """ID の欄を持つ節の公開可否の欄の値だけを置き換える。欄が無ければ ID の欄の行の直後に足す。

        公開可否の行を 2 行以上持つ節では、何行目か（line、1 始まり）を受け、その行だけを置き換える。
        """
        target, refusal = self._find_one(section, DISCLOSURE_OPERATION)
        if refusal is not None:
            return refusal
        value = str(disclosure or "")
        # spec: REQ-498
        if not value.strip() or "\n" in value or "\r" in value:
            return self._refuse(
                DISCLOSURE_FORMAT,
                "新しい公開可否が空か改行を含むので、書かなかった。公開可否は 1 行の値で渡す。",
                DISCLOSURE_OPERATION,
                example="「公開可」「公開不可（社名を出さない約束があるため）」「公開可（業種と規模までにとどめる）」のように渡す。",
            )
        refusal = self._missing_reason(reason, DISCLOSURE_OPERATION) or self._stale_fingerprint(
            target, fingerprint
        )
        if refusal is not None:
            return refusal
        # spec: REQ-497
        if target.id is None:
            return self._refuse(
                DISCLOSURE_NEEDS_ID,
                f"節「{target.heading_path}」は ID の欄を持たないので、書かなかった。"
                "公開可否は、ID の欄を持つ節にだけ置く。",
                DISCLOSURE_OPERATION,
                example="ID の欄を持つ節（list_sections で ID が付いている節）を渡す。",
            )
        rows = self.repository.disclosure_lines(target)
        number: int | None = None
        if len(rows) >= 2:
            # spec: REQ-535
            if not isinstance(line, int) or isinstance(line, bool) or not 1 <= line <= len(rows):
                return self._refuse(
                    DISCLOSURE_LINE_NUMBER,
                    f"節「{target.heading_path}」は公開可否の行を {len(rows)} 行持つので、何行目を変えるかの"
                    "番号が要る。番号が渡されないか、番号に当たる行が無いので、書かなかった。",
                    DISCLOSURE_OPERATION,
                    missing_fields=[LINE_FIELD],
                    candidates=[f"{index}: {text}" for index, (text, _) in enumerate(rows, start=1)],
                    example="候補の行の番号（1 始まり）を line に渡して、もう一度呼ぶ。",
                )
            number = line
        new_value = value.strip()
        # spec: REQ-496
        # spec: REQ-534
        new_text = self.repository.disclosure_text(target, new_value, number)
        if number is not None:
            before_value = rows[number - 1][1]
        else:
            before_value = rows[0][1] if rows else ""
        after = self._section_after(target, new_text)
        newly_public = target.private and after is not None and not after.private
        recorded: dict = {
            "元の公開可否": before_value,
            "新しい公開可否": new_value,
            "理由": str(reason).strip(),
        }
        if number is not None:
            recorded["行の番号"] = number
        notice: list[str] = []
        # spec: REQ-499
        if newly_public:
            recorded["材料に新しく出る"] = True
            notice.append(
                f"節「{target.heading_path}」は公開不可でなくなったので、材料の取り出しに新しく出る"
                f"（元の公開可否「{before_value}」→ 新しい公開可否「{new_value}」、理由: {_one_line(reason)}）。"
            )
        return self._write(
            target.file,
            new_text,
            DISCLOSURE_OPERATION,
            summary=(
                f"公開可否の変更 {target.heading_path}: 「{before_value or 'なし'}」→「{new_value}」"
                f"（理由: {_one_line(reason)}）"
            ),
            recorded=recorded,
            heading_path=target.heading_path,
            locate=_same_place(target),
            notices=notice,
        )

    # ------------------------------------------------------------ 書く操作に共通の守り

    def _find_one(
        self, reference: str, operation: str, file: str | None = None
    ) -> tuple[SourceSection | None, WriteResult | None]:
        """節を 1 つに決める（file を渡せばそのファイルの中で）。決まらなければ断りを 2 つ目に返す。"""
        names = self.repository.source_file_names()
        scope = [file] if file and file in names else None
        matched, candidates = self._resolve(reference, scope)
        if not matched:
            return None, self._refuse(
                SECTION_EXISTS,
                f"「{reference}」に当たる節が無いので、書かなかった。",
                operation,
                candidates=candidates,
                example="候補の見出しの道筋か、節の ID をそのまま渡して、もう一度呼ぶ。",
            )
        if len(matched) > 1:
            return None, self._refuse(
                SECTION_UNIQUE,
                f"「{reference}」に当たる節が {len(matched)} つあるので、書かなかった。",
                operation,
                candidates=[qualified(item) for item in matched],
                example="候補のファイルの名前つきの見出しの道筋をそのまま渡して、もう一度呼ぶ。",
            )
        return matched[0], None

    def _bad_heading(self, heading: str, operation: str) -> WriteResult | None:
        """見出しの文字として書けなければ断りを返す。"""
        # spec: REQ-471
        if heading_text_is_valid(heading):
            return None
        return self._refuse(
            HEADING_FORMAT,
            "新しい見出しが空か、改行を含むか、「#」で始まるので、書かなかった。",
            operation,
            example="見出しは「#」を付けない 1 行の文字で渡す（例「2026-10 社内の勉強会の運営」）。深さは accord が決める。",
        )

    def _missing_reason(self, reason: str, operation: str) -> WriteResult | None:
        """理由が空なら断りを返す。"""
        # spec: REQ-481
        if str(reason or "").strip():
            return None
        return self._refuse(
            REASON_REQUIRED,
            f"欄「{REASON_FIELD}」が空なので、書かなかった。",
            operation,
            missing_fields=[REASON_FIELD],
            example="理由は、何をなぜ変えるかの 1 文（例「職歴の並びを新しい順にそろえる」）。",
        )

    def _stale_fingerprint(self, target: SourceSection, fingerprint: str) -> WriteResult | None:
        """渡された指紋がいまの指紋と違えば断りを返す。"""
        # spec: REQ-445
        # spec: REQ-479
        if (fingerprint or "").strip() == target.fingerprint:
            return None
        return self._refuse(
            FINGERPRINT_MATCHES,
            f"渡された指紋「{fingerprint}」は、節「{target.heading_path}」のいまの指紋"
            f"「{target.fingerprint}」と違うので、書かなかった。読んだ後に誰かが直している。"
            f"{READ_OPERATION} で節を読み直し、いまの本文に合わせて直してから、いまの指紋で呼ぶ。",
            READ_OPERATION,
            candidates=[target.fingerprint],
            example=f"{READ_OPERATION} に「{target.heading_path}」を渡して読み直す。",
        )

    def _unknown_file(self, file: str | None, operation: str) -> WriteResult | None:
        """ファイルの名前が渡されて、それが正本のファイルに無ければ、親の節の有無によらず断りを返す。"""
        names = self.repository.source_file_names()
        if file is None or not str(file).strip() or file in names:
            return None
        # spec: REQ-533
        return self._refuse(
            SOURCE_FILE_EXISTS,
            f"渡されたファイルの名前「{file}」は正本のファイルに無いので、書かなかった。",
            operation,
            candidates=names,
            example="候補のファイルの名前をそのまま渡すか、ファイルの名前を省いて呼ぶ。",
        )

    def _known_file(self, file: str | None, operation: str) -> tuple[str | None, WriteResult | None]:
        """親の節を渡さないときのファイルの名前を確かめる。正本のファイルに無ければ断りを返す。"""
        names = self.repository.source_file_names()
        if file and file in names:
            return file, None
        return None, self._refuse(
            SOURCE_FILE_EXISTS,
            "親の節が無く、渡されたファイルの名前"
            + (f"「{file}」" if file else "")
            + "も正本のファイルに無いので、書かなかった。親の節か、正本のファイルの名前を渡す。",
            operation,
            missing_fields=[] if file else ["parent", "file"],
            candidates=names,
            example="親の節の ID か見出しの道筋を parent に、深さ 1 の節を足すときはファイルの名前を file に渡す。",
        )

    def _child_to_precede(
        self, file_name: str, parent: SourceSection | None, before: str | None, operation: str
    ) -> tuple[SourceSection | None, WriteResult | None]:
        """前に置く節を、親の直下の節（親が None なら深さ 1 の節）から 1 つに決める。渡されなければ None。"""
        if before is None or not str(before).strip():
            return None, None
        sections = self.repository.source_sections(file_name)
        if parent is not None:
            children = _children(sections, parent)
            owner = f"親の節「{parent.heading_path}」の直下の節"
        else:
            children = [item for item in sections if item.level == 1]
            owner = f"{file_name} の深さ 1 の節"
        matched, _ = self._resolve(before, [file_name])
        wanted = {item.start for item in matched}
        found = [item for item in children if item.start in wanted]
        if len(found) == 1:
            return found[0], None
        # spec: REQ-474
        return None, self._refuse(
            PRECEDE_A_CHILD,
            f"前に置く節「{before}」は、{owner}ではないので、書かなかった。",
            operation,
            candidates=[item.heading_path for item in children],
            example="候補の見出しの道筋のどれかを渡すか、前に置く節を省いて末尾に置く。",
        )

    def _duplicated_headings(self, file_name: str, new_text: str, operation: str) -> WriteResult | None:
        """書いた後に、同じ親の下に同じ見出しの節が新しく 2 つ以上できるなら断りを返す。"""
        before = Counter(item.heading_path for item in self.repository.source_sections(file_name))
        after = Counter(
            item.heading_path for item in self.repository.source_sections(file_name, text=new_text)
        )
        doubled = [path for path, count in after.items() if count > 1 and count > before.get(path, 0)]
        # spec: REQ-478
        if not doubled:
            return None
        return self._refuse(
            SIBLING_HEADINGS_UNIQUE,
            "書いた後に、同じ親の下に同じ見出しの節が 2 つ以上できるので、書かなかった。"
            "重なる見出しの道筋: " + " / ".join(doubled),
            operation,
            candidates=doubled,
            example="同じ親の下のほかの節と重ならない見出しにする。",
        )

    def _section_after(self, target: SourceSection, new_text: str) -> SourceSection | None:
        """書いた後の全文で、同じ節（同じ並びの位置）を返す。"""
        before = self.repository.source_sections(target.file)
        index = next(
            (i for i, item in enumerate(before) if item.start == target.start), None
        )
        after = self.repository.source_sections(target.file, text=new_text)
        if index is None or index >= len(after):
            return None
        return after[index]

    def _write(
        self,
        file_name: str,
        new_text: str,
        operation: str,
        summary: str,
        recorded: dict,
        heading_path: str,
        locate=None,
        notices: list[str] | None = None,
    ) -> WriteResult:
        """書く前の守りを通し、ファイルに書き、記録をとって、新しい指紋と読み比べる写しを返す。"""
        # spec: REQ-514
        refusal = self.recorder.refusal(file_name, operation)
        if refusal is not None:
            return WriteResult(accepted=False, rejection=refusal)

        before = self._watch().report().violations
        after, defects_after = self._check_after(file_name, new_text)
        appeared = new_violations(before, after)
        blocking = [item for item in appeared if item.constraint != COPY_FRESHNESS]
        # spec: REQ-467
        # spec: REQ-482
        if blocking:
            return WriteResult(
                accepted=False,
                rejection=Rejection(
                    constraint=blocking[0].constraint,
                    reason=(
                        "書いた後の正本に、書く前に無かった整合の検査の違反が出るので、書かなかった。"
                        + " / ".join(item.as_note() for item in blocking)
                    ),
                    next_action=NextAction(
                        operation=operation,
                        candidates=[],
                        example="違反が出ない形に直してから、もう一度呼ぶ。",
                    ),
                ),
            )
        all_broken = _new_defects(self.repository.load().defects, defects_after)
        invalid = [item for item in all_broken if item.invalid_fields]
        # spec: REQ-541
        if invalid:
            fields = list(dict.fromkeys(name for item in invalid for name in item.invalid_fields))
            return WriteResult(
                accepted=False,
                rejection=Rejection(
                    constraint=FIELD_VALUE_TYPE,
                    reason=(
                        "書いた後の正本に、欄の値が型に合わず読めないブロックが新しく出るので、書かなかった。"
                        + " / ".join(f"{item.file} の{item.location}（{item.reason}）" for item in invalid)
                    ),
                    next_action=NextAction(
                        operation=operation,
                        missing_fields=fields,
                        example="欄の値を型に合う形（日付なら 2026-10-14 の形）にしてから、もう一度呼ぶ。",
                    ),
                ),
            )
        broken = [item for item in all_broken if item.missing_fields]
        # spec: REQ-490
        if broken:
            missing = list(dict.fromkeys(name for item in broken for name in item.missing_fields))
            return WriteResult(
                accepted=False,
                rejection=Rejection(
                    constraint=_defect_constraint(broken[0]),
                    reason=(
                        "書いた後の正本に、必須の欄が欠けて読めないブロックが新しく出るので、書かなかった。"
                        + " / ".join(
                            f"{item.file} の{item.location}（欠けた欄: {'、'.join(item.missing_fields)}）"
                            for item in broken
                        )
                    ),
                    next_action=NextAction(
                        operation=operation,
                        missing_fields=missing,
                        example="欠けた欄を残した形に直してから、もう一度呼ぶ。",
                    ),
                ),
            )

        self.repository.write_source_file(file_name, new_text)
        # spec: REQ-513
        notes = self.recorder.record(file_name, operation, summary)
        located = locate(self.repository.source_sections(file_name)) if locate else None
        stale = [item for item in appeared if item.constraint == COPY_FRESHNESS]
        result = dict(recorded)
        result.update(
            {
                "ファイル": file_name,
                "見出しの道筋": located.heading_path if located else heading_path,
                # spec: REQ-450
                # spec: REQ-483
                "読み比べる写し": [f"{item.file} の{item.location}" for item in stale],
            }
        )
        if locate is not None:
            # spec: REQ-442
            # spec: REQ-449
            result["新しい指紋"] = located.fingerprint if located else ""
        return WriteResult(
            accepted=True,
            recorded=result,
            warnings=list(notices or []) + [item.as_note() for item in stale] + notes,
        )

    def _check_after(self, file_name: str, new_text: str) -> tuple[list[Violation], list[SourceDefect]]:
        """正本のファイルを一時の場所に写し、1 つを書いた後の全文に置き換えて、全体を検査する。

        返すのは、整合の検査の違反と、必須の欄が欠けて読めないブロックの 2 つ。本物のファイルは
        変えない。提示物と媒体の規約は、本物の置き場から読む（書くのは正本だけなので）。
        """
        from accord.services.consistency import ConsistencyService

        with tempfile.TemporaryDirectory(prefix="accord-check-") as temporary:
            root = Path(temporary)
            for name in self.repository.source_file_names():
                origin = self.repository.source_path(name)
                if not origin.is_file():
                    continue
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin, destination)
            changed = root / file_name
            changed.parent.mkdir(parents=True, exist_ok=True)
            changed.write_text(new_text, encoding="utf-8")
            copied = dataclasses.replace(
                self.settings,
                source_dir=root,
            )
            violations = ConsistencyService(copied).inspect(None).violations
            defects = MarkdownRepository(copied).load().defects
            return violations, defects

    def _refuse(
        self,
        constraint: str,
        reason: str,
        operation: str,
        missing_fields: list[str] | None = None,
        candidates: list[str] | None = None,
        example: str = "",
    ) -> WriteResult:
        """書かずに断る返り値を作る。"""
        return WriteResult(
            accepted=False,
            rejection=Rejection(
                constraint=constraint,
                reason=reason,
                next_action=NextAction(
                    operation=operation,
                    missing_fields=list(missing_fields or []),
                    candidates=list(candidates or []),
                    example=example,
                ),
            ),
        )

    # ------------------------------------------------------------ 書き出す

    def export_source(self, path: str) -> ExportResult:
        """正本の各ファイルを、ファイルの名前の見出しを付けてつなぎ、渡された書き出し先に書く。"""
        result = self._export_source(path)
        # spec: REQ-458
        result.consistency_notice = self._watch().notice()
        return result

    def _export_source(self, path: str) -> ExportResult:
        raw = str(path or "")
        given = Path(raw).expanduser()
        destination = given.resolve()
        data_dir = self.settings.source_dir.resolve()
        outside_example = "置き場の外のファイルのパス（例: ~/accord_export.md）を path に渡して呼び直す。"
        # 渡されたパスそのものが symlink なら、解決した先がどこでも（置き場の中でも）同じ断りにする。
        # spec: REQ-557
        if raw.strip() and given.is_symlink():
            return _export_refused(
                EXPORT_NEW_FILE,
                f"書き出し先「{given.name}」が symlink なので、書き出さなかった。accord は symlink の先に書かない。",
                "symlink ではない、まだ無いファイルのパスを path に渡して呼び直す。",
            )
        # spec: REQ-525
        if not raw.strip() or _within(destination, data_dir):
            return _export_refused(
                EXPORT_OUTSIDE_DATA,
                "書き出し先が経歴データの置き場の中を指しているので、書き出さなかった。"
                "置き場の中には accord の正本と語彙のファイルのほかを置かない。",
                outside_example,
            )
        presentations = self.settings.presentations_dir
        # spec: REQ-555
        if presentations is not None and _within(destination, presentations.resolve()):
            return _export_refused(
                EXPORT_OUTSIDE_DATA,
                "書き出し先が提示物の置き場（起動の引数 --presentations）の中を指しているので、書き出さなかった。"
                "そこに置いた写しは、提示物として読まれる。",
                outside_example,
            )
        # spec: REQ-556
        if destination.exists():
            return _already_there(destination)
        # spec: REQ-558
        if not destination.parent.is_dir():
            return _export_refused(
                EXPORT_NEW_FILE,
                f"書き出し先「{destination.name}」の親ディレクトリが無いので、書き出さなかった。"
                "accord はディレクトリを作らない。",
                "親ディレクトリが既にある場所のファイルのパスを path に渡して呼び直す。",
            )
        parts = []
        for name in self.repository.source_file_names():
            parts.append(f"# {name}\n\n{self.repository.read_source_file(name).strip()}\n")
        text = "\n".join(parts)
        # 確かめた後に別の手がファイルを置いても上書きしないよう、新しいファイルとしてだけ開く。
        try:
            with destination.open("x", encoding="utf-8") as handle:
                handle.write(text)
        except FileExistsError:
            # spec: REQ-556
            return _already_there(destination)
        # spec: REQ-455
        return ExportResult(written=True, file_name=destination.name, chars=len(text))


def _within(path: Path, root: Path) -> bool:
    """path が root そのものか、root の下にあるか。どちらも解決済みのパスで比べる。"""
    return path == root or root in path.parents


def _already_there(destination: Path) -> ExportResult:
    """書き出し先に既にファイルがあるときの断り。上書きせず、別の名前か先に消すことを次の一手にする。"""
    return _export_refused(
        EXPORT_NEW_FILE,
        f"書き出し先「{destination.name}」には既にファイルがあるので、書き出さなかった。accord は上書きしない。",
        "別の名前のファイルのパスを path に渡すか、呼ぶ側が先にそのファイルを消してから呼び直す。",
    )


def _export_refused(constraint: str, reason: str, example: str) -> ExportResult:
    """書き出さずに断る返り値を作る。次の一手は、path を直して書き出しを呼び直すこと。"""
    return ExportResult(
        written=False,
        rejection=Rejection(
            constraint=constraint,
            reason=reason,
            next_action=NextAction(
                operation=EXPORT_OPERATION,
                missing_fields=["path"],
                example=example,
            ),
        ),
    )


def _as_date(text: str) -> date | None:
    """日付の文字列を date に直す。読めない形と空は None。"""
    try:
        return date.fromisoformat(str(text or "").strip())
    except ValueError:
        return None


# 公開可否の行が項目に属さず、節の欄として書かれているときに、項目の代わりに書く語。
SECTION_FIELD_WORD = "節の欄"


def _by_item(rows: list[tuple[str, str | None]]) -> list[dict[str, str]]:
    """公開可否の行を、項目（先頭の行。節の欄なら「節の欄」）と行の組の一覧にする。"""
    return [{"項目": head if head is not None else SECTION_FIELD_WORD, "行": line} for line, head in rows]


def _item_value_pairs(
    by_item: list[tuple[str, str | None]], rows: list[tuple[str, str]]
) -> list[tuple[str | None, str]]:
    """公開可否の行を、（属する項目の先頭の行・値）の組の並びにする。2 つの一覧は同じ行の並び。"""
    return [(head, value) for (_, head), (_, value) in zip(by_item, rows)]


def _item_text(entry: dict[str, str]) -> str:
    """項目と行の組を、コミットの説明に載せる 1 つの文字列にする。"""
    return f"［{entry['項目']}］{entry['行']}"


def _one_line(text: str) -> str:
    """理由の文を、コミットの説明に載せる 1 行にたたむ。"""
    return " ".join(str(text or "").split())


def _same_place(target: SourceSection):
    """書いた後のファイルで、同じ見出しの道筋と同じ位置の節を探す関数を返す。"""
    return lambda sections: next(
        (
            item
            for item in sections
            if item.heading_path == target.heading_path and item.start == target.start
        ),
        None,
    )


def _descendants(sections: list[SourceSection], parent: SourceSection) -> list[SourceSection]:
    """同じファイルの節の並びから、その節の下位の節をすべて（並びの順に）返す。"""
    found: list[SourceSection] = []
    started = False
    for item in sections:
        if item.start == parent.start:
            started = True
            continue
        if not started:
            continue
        if item.level <= parent.level:
            break
        found.append(item)
    return found


def _children(sections: list[SourceSection], parent: SourceSection) -> list[SourceSection]:
    """その節の直下の節（いちばん近い上位の節がその節であるもの）を、並びの順に返す。"""
    found: list[SourceSection] = []
    stack: list[SourceSection] = []
    for item in _descendants(sections, parent):
        while stack and stack[-1].level >= item.level:
            stack.pop()
        if not stack:
            found.append(item)
        stack.append(item)
    return found


def _defect_key(item: SourceDefect) -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
    return (item.file, item.source_key, tuple(item.missing_fields), tuple(item.invalid_fields))


def _new_defects(before: list[SourceDefect], after: list[SourceDefect]) -> list[SourceDefect]:
    """書いた後の読めないブロックのうち、書く前より増えたものを返す。

    見出しを変えたブロックも同じブロックと数えるため、場所ではなく、ファイル・正本の役割・欠けた欄の
    組の件数で比べる。件数が増えた組のうち、書く前に無かった場所のものを返す。
    """
    counts = Counter(_defect_key(item) for item in before)
    places = {(item.file, item.location) for item in before}
    grown = {key for key, count in Counter(_defect_key(item) for item in after).items() if count > counts.get(key, 0)}
    found = [item for item in after if _defect_key(item) in grown and (item.file, item.location) not in places]
    return found or [item for item in after if _defect_key(item) in grown]


def _defect_constraint(item: SourceDefect) -> str:
    """読めないブロックの断りに名乗る制約の名前。"""
    return DEFECT_CONSTRAINTS.get(item.source_key, READABLE_BLOCKS)

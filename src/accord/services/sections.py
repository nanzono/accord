"""正本のファイルを節で読み書きする操作と、正本の書き出し。

文面を書く AI のセッションが、正本のファイルを直接開かずに済むようにするための操作である。
読みは 3 つ（節の一覧・節の読み・事実の検索）で、正本を 1 バイトも書き換えない。公開不可の節も
返す。AI のセッションが事実を確かめるための読みで、外に出す材料ではないからである。

書きは 2 つ（事実の登記・節の書き換え）で、書く瞬間に制約で断る。断るときは正本を 1 バイトも
変えない。書いた後の正本に、書く前に無かった整合の検査の違反が出るなら書かない。ただし
「写しの鮮度」の違反は断る理由にせず、書いた後に読み比べるべき写しとして返す。元の節を正しく
直すたびに写しが古くなるのは当然で、それで書き込みを止めると事実を直せなくなるためである。
書いた後の正本の検査は、正本のファイルを一時の場所に写した上で走らせる（本物のファイルは、
検査が通るまで変えない）。

書き出しは、正本の各ファイルをファイルの名前の見出しでつないだ Markdown を、設定の書き出し先の
ファイル 1 つに書く。書き出し先は設定で固定し、返り値にはファイルの名前と字数だけを入れる。
セッションが書き出した写しを開いて、accord を通らずに読む道を作らないためである。

どの返り値にも、正本の置き場の絶対パスを入れない。ファイルは設定に書いた名前で指す。
"""

from __future__ import annotations

import dataclasses
import difflib
import shutil
import tempfile
import unicodedata
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
    SourceSection,
    Violation,
    WriteResult,
)
from accord.repository.markdown_repository import MarkdownRepository
from accord.repository.sections import has_heading_line
from accord.services.recording import WriteRecorder
from accord.vocabulary.settings import EXPORT_PATH_KEY, Settings

# 操作の名前。次の一手にそのまま載せる。
LIST_OPERATION = "list_sections"
READ_OPERATION = "read_section"
SEARCH_OPERATION = "search_facts"
RECORD_FACT_OPERATION = "record_fact"
REVISE_OPERATION = "revise_section"
EXPORT_OPERATION = "export_source"

# 節を書き換えられる正本の役割。型の操作を持たない 3 つ（経歴・職務経歴書の台帳・見せ方の正本）に限る。
WRITABLE_KEYS = ("career", "resume_ledger", "presentation_rules")

# 型の操作を持つ正本と、その正本を書く操作。節の書き換えで断るときに候補にする。
TYPED_OPERATIONS = {
    "positioning": "record_positioning",
    "packages": "revise_package",
    "capabilities": "register_capability",
    "public_records": "register_public_record",
}

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
DISCLOSURE_FIELD_KEPT = "公開可否の欄を元の値のまま残す"
FACT_NOT_A_FIELD = "事実の文を欄の書き方で書かない"
REVISION_REASON_REQUIRED = "節の書き換えの理由"
WRITABLE_SOURCE = "節を書き換えられる正本"
EXPORT_PATH_REQUIRED = "書き出し先の設定"

# 欄の名前。欠けた欄の断りに載せる。
FACT_FIELD = "事実の文"
SOURCE_FIELD = "出所"
DATE_FIELD = "日付"
REASON_FIELD = "理由"

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
                "ID と公開可否は、この操作では変えない。",
                RECORD_FACT_OPERATION,
                example="事実は「〜した」「〜を担当した」のような文で書く。",
            )
        return self._write(
            target,
            new_text,
            RECORD_FACT_OPERATION,
            summary=f"事実の登記 {target.heading_path}",
            recorded={"足した行": line},
        )

    def revise_section(self, section: str, body: str, fingerprint: str, reason: str) -> WriteResult:
        """節 1 つの本文を新しい本文に置き換える。見出しの行と下位の見出しの節は変えない。"""
        matched, candidates = self._resolve(section)
        if not matched:
            return self._refuse(
                SECTION_EXISTS,
                f"「{section}」に当たる節が無いので、書かなかった。",
                REVISE_OPERATION,
                candidates=candidates,
                example="候補の見出しの道筋か、節の ID をそのまま渡して、もう一度呼ぶ。",
            )
        if len(matched) > 1:
            return self._refuse(
                SECTION_UNIQUE,
                f"「{section}」に当たる節が {len(matched)} つあるので、書かなかった。",
                REVISE_OPERATION,
                candidates=[qualified(item) for item in matched],
                example="候補のファイルの名前つきの見出しの道筋をそのまま渡して、もう一度呼ぶ。",
            )
        target = matched[0]

        writable = {self.settings.files[key] for key in WRITABLE_KEYS if key in self.settings.files}
        # spec: REQ-451
        if target.file not in writable:
            operations = [
                TYPED_OPERATIONS[key]
                for key in self.settings.keys_for_file(target.file)
                if key in TYPED_OPERATIONS
            ]
            tail = (
                "この正本は、型の操作（" + " / ".join(operations) + "）で書く。"
                if operations
                else "この正本を書く操作は accord に無い。人の手で直す。"
            )
            return self._refuse(
                WRITABLE_SOURCE,
                f"{target.file} の節は、この操作では書き換えない。"
                "節を書き換えられるのは、経歴の正本・職務経歴書の台帳・見せ方の正本だけである。" + tail,
                operations[0] if operations else REVISE_OPERATION,
                candidates=operations,
                example="型の操作の入力の欄は、資源 accord://ontology で読める。",
            )
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
        if (fingerprint or "").strip() != target.fingerprint:
            return self._refuse(
                FINGERPRINT_MATCHES,
                f"渡された指紋「{fingerprint}」は、節「{target.heading_path}」のいまの指紋"
                f"「{target.fingerprint}」と違うので、書かなかった。読んだ後に誰かが直している。"
                f"{READ_OPERATION} で節を読み直し、いまの本文に合わせて直してから、いまの指紋で呼ぶ。",
                READ_OPERATION,
                candidates=[target.fingerprint],
                example=f"{READ_OPERATION} に「{target.heading_path}」を渡して読み直す。",
            )
        # spec: REQ-446
        if has_heading_line(body or ""):
            return self._refuse(
                NO_HEADING_IN_BODY,
                "新しい本文が見出しの行を含むので、書かなかった。"
                "節の新設と見出しの変更は、この操作ではできない（人の手で直す）。",
                REVISE_OPERATION,
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
        # spec: REQ-468
        if after is None or (after.disclosure, after.private) != (target.disclosure, target.private):
            return self._refuse(
                DISCLOSURE_FIELD_KEPT,
                f"新しい本文で、節「{target.heading_path}」の公開可否の欄が消えるか値が変わるので、"
                "書かなかった。公開可否は、外に出してよいかを人が決める欄なので、この操作では変えない。"
                "公開可否を変えるときは、人の手で直す。",
                REVISE_OPERATION,
                example="新しい本文に、公開可否の行を元の値のまま残す。",
            )
        return self._write(
            target,
            new_text,
            REVISE_OPERATION,
            summary=f"節の書き換え {target.heading_path}: {' '.join(str(reason).split())}",
            recorded={"理由": str(reason).strip()},
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
        target: SourceSection,
        new_text: str,
        operation: str,
        summary: str,
        recorded: dict,
    ) -> WriteResult:
        """書く前の守りを通し、ファイルに書き、記録をとって、新しい指紋と読み比べる写しを返す。"""
        # spec: REQ-405
        refusal = self.recorder.refusal(target.file, operation)
        if refusal is not None:
            return WriteResult(accepted=False, rejection=refusal)

        before = self._watch().report().violations
        after = self._violations_after(target.file, new_text)
        appeared = _new_violations(before, after)
        blocking = [item for item in appeared if item.constraint != COPY_FRESHNESS]
        # spec: REQ-467
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
                        example="違反が出ない本文に直してから、もう一度呼ぶ。",
                    ),
                ),
            )

        self.repository.write_source_file(target.file, new_text)
        notes = self.recorder.record(target.file, operation, summary)
        after_section = self._section_after_write(target)
        stale = [item for item in appeared if item.constraint == COPY_FRESHNESS]
        result = dict(recorded)
        result.update(
            {
                "ファイル": target.file,
                "見出しの道筋": target.heading_path,
                # spec: REQ-442
                # spec: REQ-449
                "新しい指紋": after_section.fingerprint if after_section else "",
                # spec: REQ-450
                "読み比べる写し": [f"{item.file} の{item.location}" for item in stale],
            }
        )
        return WriteResult(
            accepted=True,
            recorded=result,
            warnings=[item.as_note() for item in stale] + notes,
        )

    def _section_after_write(self, target: SourceSection) -> SourceSection | None:
        """書いた後のファイルで、同じ見出しの道筋の節を返す。"""
        return next(
            (
                item
                for item in self.repository.source_sections(target.file)
                if item.heading_path == target.heading_path and item.start == target.start
            ),
            None,
        )

    def _violations_after(self, file_name: str, new_text: str) -> list[Violation]:
        """正本のファイルを一時の場所に写し、1 つを書いた後の全文に置き換えて、全体を検査する。

        本物のファイルは変えない。提示物と媒体の規約は、本物の置き場から読む（書くのは正本だけなので）。
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
                presentations_root=self.settings.presentations_dir,
                commit_writes=False,
                export_path=None,
            )
            return ConsistencyService(copied).inspect(None).violations

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

    def export_source(self) -> ExportResult:
        """正本の各ファイルを、ファイルの名前の見出しを付けてつなぎ、設定の書き出し先に書く。"""
        result = self._export_source()
        # spec: REQ-458
        result.consistency_notice = self._watch().notice()
        return result

    def _export_source(self) -> ExportResult:
        destination = self.settings.export_path
        # spec: REQ-454
        if destination is None:
            return ExportResult(
                written=False,
                rejection=Rejection(
                    constraint=EXPORT_PATH_REQUIRED,
                    reason=(
                        f"設定に書き出し先が無いので、書き出さなかった。設定の [source] に鍵 {EXPORT_PATH_KEY} を足す"
                        "（正本の置き場と提示物の置き場の外のファイルを指す）。"
                    ),
                    next_action=NextAction(
                        operation=EXPORT_OPERATION,
                        missing_fields=[EXPORT_PATH_KEY],
                        example=f'[source] に {EXPORT_PATH_KEY} = "../accord_export.md" のように書く。',
                    ),
                ),
            )
        parts = []
        for name in self.repository.source_file_names():
            # spec: REQ-452
            parts.append(f"# {name}\n\n{self.repository.read_source_file(name).strip()}\n")
        text = "\n".join(parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        # spec: REQ-455
        return ExportResult(written=True, file_name=destination.name, chars=len(text))


def _as_date(text: str) -> date | None:
    """日付の文字列を date に直す。読めない形と空は None。"""
    try:
        return date.fromisoformat(str(text or "").strip())
    except ValueError:
        return None


def _new_violations(before: list[Violation], after: list[Violation]) -> list[Violation]:
    """書いた後の違反のうち、書く前に無かったものを返す。

    写しの鮮度は、直し先の文（変わった出典と指紋）まで比べる。書いたことで写しが新しく古くなったかを
    見るためである。ほかの違反は、制約・ファイル・場所で比べる。同じ場所の同じ違反の文の言い回しが
    変わっただけで、書き込みを止めないためである。
    """

    def key(item: Violation) -> tuple[str, ...]:
        if item.constraint == COPY_FRESHNESS:
            return (item.constraint, item.file, item.location, item.expected)
        return (item.constraint, item.file, item.location)

    seen = {key(item) for item in before}
    return [item for item in after if key(item) not in seen]

"""正本の Markdown を読み、型の集合として渡し、承認された変更だけを書き戻す。

Markdown の在処と書き方を知るのはこの文書だけである。上の層（サービスと皮）は、
ファイル名も見出しの形も知らずに、型の集合だけを見て判断する。
保管の形式を差し替えるときに直すのはここに閉じる、という分け方である。
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from accord.models.ontology import missing_required_fields
from accord.models.results import (
    PRIVATE_DISCLOSURE_PREFIX,
    PresentationUrl,
    SkippedHeading,
    SourceDefect,
    SourceSection,
    SourceSnapshot,
    normalize_url,
)
from accord.models.types import (
    Capability,
    CareerFrame,
    Engagement,
    Package,
    Positioning,
    Presentation,
    PublicRecord,
    ResumeLedger,
)
from accord.repository.sections import (
    Section,
    append_section_line,
    bullet_items,
    delete_section,
    drop_field_lines,
    field_lines,
    field_lines_with_items,
    find_section,
    find_urls,
    insert_section,
    is_frame_heading,
    list_items,
    leading_number,
    move_section,
    outline_sections,
    prefix_matches,
    read_fields,
    rename_heading,
    replace_section_body,
    section_fingerprint,
    select_blocks,
    set_field,
    shifted_levels,
    split_sections,
    strip_note,
    table_blocks,
)
from accord.vocabulary.settings import (
    CAPABILITY_CATEGORIES_KIND,
    CHANNEL_RULES_PER_CHANNEL_FILE,
    CHANNELS_KIND,
    HEADING_RE,
    PACKAGE_HYPOTHESIS_STATES_KIND,
    POSITIONING_TARGETS_KIND,
    PUBLIC_RECORD_KINDS_KIND,
    PUBLIC_RECORD_ROLES_KIND,
    TERM_RE,
    PHRASES_FROM_TABLE,
    PRESENTATION_RULES_KEY,
    PUBLIC_RECORDS_KEY,
    RESUME_LEDGER_KEY,
    VOCABULARY_KINDS,
    VOCABULARY_TITLE,
    BlockRule,
    Settings,
)

# 正本の欄の見出し（Markdown 側のラベル）と、型の欄の名前の対応。
POSITIONING_LABELS = {
    "日付": "decided_on",
    "適用範囲": "scope",
    "前面に出す束": "headline_package",
    "根拠": "rationale",
}
# 並びは、書き戻すときの行の並びでもある（読むときは並びを見ない）。
PACKAGE_LABELS = {
    "ID": "id",
    "最終更新": "updated_on",
    "想定買い手": "buyer",
    "仮説の状態": "hypothesis_state",
    "判定根拠": "basis",
    "出典": "source",
    "崩れる条件": "breaks_when",
}

# パッケージの「束ねる機能」の欄。一覧の欄なので、他の欄と書き方が違う。
PACKAGE_CAPABILITIES_LABEL = "束ねる機能"

# 決めの「例外」の欄。値が無いブロックにも、空を表す語で 1 行置く。
POSITIONING_EXCEPTIONS_LABEL = "例外"

# 例外の欄が持つ、提示物の名前と理由の鍵。読み書きの両方がこの鍵を使う。
EXCEPTION_PRESENTATION_KEY = "提示物"
EXCEPTION_REASON_KEY = "理由"
CAREER_LABELS = {
    "ID": "id",
    "期間": "period",
    "所属": "organization",
    "立場": "position",
    "やったこと": "summary",
    "成果": "outcome",
    "技術": "technologies",
    "公開可否": "disclosure",
    "出所": "source",
}
ENGAGEMENT_LABELS = {
    "ID": "id",
    "業種": "industry",
    "規模": "scale",
    "課題": "problem",
    "やったこと": "actions",
    "成果": "outcome",
    "技術": "technologies",
    "公開可否": "disclosure",
    "出所": "source",
}
LEDGER_LABELS = {
    "案件番号": "entry_number",
    "期間": "period",
    "規模": "scale",
    "担当工程": "process",
    "役割と任され方": "role",
    "自分が決めたこと": "decisions",
    "終わりの状態": "closing",
    "出典の節": "source_section",
    "出典の指紋": "source_fingerprints",
    "畳み行": "fold_line",
}
PRESENTATION_LABELS = {
    "宛先の媒体": "channel",
    "宣言する束": "declared_package",
    "作成日": "created_on",
}

# 提示物の宣言の行のうち、写し元を宣言する 2 つ。どちらも任意で、台帳のブロックと同じ書き方をする。
PRESENTATION_SOURCE_LABEL = "出典の節"
PRESENTATION_FINGERPRINT_LABEL = "出典の指紋"

# 職務経歴書の台帳のブロックの種類。型の正本の ResumeLedger の欄「種類」が取る語。
LEDGER_KIND_ENTRY = "案件"
LEDGER_KIND_FRAME = "在籍職歴の枠"

# 出典の指紋の欄の書き方。「ID=指紋」の組を半角のスラッシュで区切って並べる。
# 読んだ組は、ID と指紋の 2 つの鍵を持つ辞書の一覧になる（型の正本の mapping の欄）。
FINGERPRINT_SEPARATOR = "="
FINGERPRINT_ID_KEY = "ID"
FINGERPRINT_VALUE_KEY = "指紋"
# 公開記録の欄。名前は見出しが持つので、この表には無い。
# 並びは、書き戻すときの行の並びでもある（読むときは並びを見ない）。
PUBLIC_RECORD_LABELS = {
    "ID": "id",
    "種類": "kind",
    "日付": "published_on",
    "URL": "url",
    "発行元か主催": "publisher",
    "役割": "role",
    "由来の節": "origin_section",
    "出所": "source",
}

# 一覧の欄を 1 行に書くときの区切り。
LIST_SEPARATOR = "/"

# 例外の欄で、提示物の名前と理由を分ける印。
EXCEPTION_SEPARATOR = "—"

# 値が空であることを表す語。「未反映の注記: なし」のように書ける。
EMPTY_WORDS = {"", "なし", "無し", "-", "—"}

# 空の欄を書き戻すときに使う語。読むときは上の一覧のどれでも空として扱う。
EMPTY_MARK = "なし"

# 機能の台帳の表の見出し。節を新しく作るときに書き出す。
# 列の並びは「ID、機能名、説明、裏づけ」で、読み込みはこの並びに依存する。
CAPABILITY_TABLE_HEADER = ("| ID | 機能名 | 説明 | 裏づけの節 |", "|---|---|---|---|")

# ID の欄のラベル。
ID_LABEL = "ID"

# 公開可否の欄のラベル。職歴の枠と受託案件が持つ。
DISCLOSURE_LABEL = "公開可否"

# 媒体ごとの規約のファイルの場所に書く、媒体の名前が入るところの印。
CHANNEL_PLACEHOLDER = "{channel}"

# 裏づけの節と出典の節が指せる正本。どちらも節の見出しで指す。
EVIDENCE_SOURCE_KEYS = ("career", "engagements")

# 職務経歴書の台帳の正本の役割の名前。
LEDGER_KEY = RESUME_LEDGER_KEY

# 必須欄の判定（missing_required_fields）を呼ぶときに引く、型の名前。
# 決めの必須欄は _load_positionings が別の書き方で見ているので、ここには無い。
PACKAGE_TYPE_NAME = "Package"
CAPABILITY_TYPE_NAME = "Capability"
CAREER_FRAME_TYPE_NAME = "CareerFrame"
ENGAGEMENT_TYPE_NAME = "Engagement"
PRESENTATION_TYPE_NAME = "Presentation"
RESUME_LEDGER_TYPE_NAME = "ResumeLedger"
PUBLIC_RECORD_TYPE_NAME = "PublicRecord"


def _split_list(value: str) -> list[str]:
    """「A / B」の形の欄を、値の一覧にする。空を表す語なら空の一覧を返す。"""
    if value.strip() in EMPTY_WORDS:
        return []
    items = []
    for chunk in value.replace("\n", LIST_SEPARATOR).split(LIST_SEPARATOR):
        item = chunk.strip()
        if item and item not in EMPTY_WORDS:
            items.append(item)
    return items


def parse_fingerprints(value: str) -> list[dict[str, str]]:
    """出典の指紋の欄を、ID と指紋の組の一覧にする。

    「=」を持たない組は、指紋の無い組として ID だけを持たせる（検査はこれを控えの無い写しとして扱う）。
    """
    pairs: list[dict[str, str]] = []
    for item in _split_list(value):
        identifier, _, fingerprint = item.partition(FINGERPRINT_SEPARATOR)
        pairs.append(
            {FINGERPRINT_ID_KEY: identifier.strip(), FINGERPRINT_VALUE_KEY: fingerprint.strip()}
        )
    return pairs


def format_fingerprints(pairs: list[tuple[str, str]]) -> str:
    """ID と指紋の組の並びを、出典の指紋の欄にそのまま書ける 1 行にする。"""
    return f" {LIST_SEPARATOR} ".join(
        f"{identifier}{FINGERPRINT_SEPARATOR}{fingerprint}" for identifier, fingerprint in pairs
    )


def split_ids(value: str) -> list[str]:
    """半角のスラッシュで区切った ID の並びを、ID の一覧にする。"""
    return _split_list(value)


def _skip_reasons(section: Section, above: list[str], rule: BlockRule) -> list[str]:
    """その節が、読み方のどの絞りに当たって外れたかを並べる。1 つも当たらなければ空の一覧。

    絞りは select_blocks の 5 つと同じで、判定の順も同じである。当たったものを全部返すのは、
    accord の形のどの決まりに合わせれば読めるようになるかを、理由の文だけで言い切るためである。
    """
    reasons: list[str] = []
    if section.level not in set(rule.heading_levels):
        levels = " / ".join(str(item) for item in rule.heading_levels)
        reasons.append(f"深さ {section.level} が、accord の形の見出しの深さ（{levels}）に無い")
    if rule.under_headings and not any(name in rule.under_headings for name in above):
        parents = "、".join(above) if above else "上位の見出しなし"
        wanted = " / ".join(rule.under_headings)
        reasons.append(f"上位の見出し（{parents}）に、束ねる見出し「{wanted}」が無い")
    if not prefix_matches(section.heading, rule):
        if rule.frame_heading_prefix:
            reasons.append(
                f"見出しが「{rule.heading_prefix}」でも「{rule.frame_heading_prefix}」でも始まっていない"
            )
        else:
            reasons.append(f"見出しが「{rule.heading_prefix}」で始まっていない")
    if rule.skip_sections_without_fields and not read_fields(section, rule):
        reasons.append("欄を 1 つも持たないので、束ねるための見出しとして読み飛ばしている")
    if rule.skip_sections_without_labels and not (
        set(rule.skip_sections_without_labels) & set(read_fields(section, rule))
    ):
        reasons.append("型の欄を 1 つも持たないので、覚え書きの節として読み飛ばしている")
    return reasons


def _optional(value: str | None) -> str | None:
    """空を表す語を None にそろえる。"""
    if value is None or value.strip() in EMPTY_WORDS:
        return None
    return value.strip()


def _as_section(section: SourceSection) -> Section:
    """読み書きの層の節の型を、行の範囲だけを持つ切り出しの節に戻す。"""
    return Section(
        level=section.level,
        heading="",
        body=section.body,
        start=section.start,
        end=section.end,
    )


# 型の欄の名前（英字）から、正本の欄の名前を引けないときに使う、機能の台帳の列の名前。
CAPABILITY_COLUMN_LABELS = {"ID": "id", "機能名": "name", "説明": "description", "裏づけの節": "evidence_sections"}


def _type_word(error_type: str) -> str:
    """型の検査の誤りの種類を、読めなかった値の型の言葉にする。"""
    if "date" in error_type:
        return "日付"
    if "int" in error_type or "float" in error_type or "decimal" in error_type:
        return "数"
    if "url" in error_type:
        return "URL"
    return "型に合う値"


def _typed(model, values: dict, labels: dict[str, str], defect: dict):
    """values で型を作る。値が型に合わず作れなければ、読めない欄と理由を持つ SourceDefect を返す。

    必須の欄の欠けは呼ぶ側が先に見る。ここに来るのは、欄はあるが値が型に合わない場合
    （日付の欄に日付として読めない値がある、など）である。例外で落とさず、読めないブロックとして返す。
    """
    try:
        return model(**values)
    except ValidationError as error:
        names = {name: label for label, name in labels.items()}
        fields: list[str] = []
        reasons: list[str] = []
        for entry in error.errors():
            name = str(entry["loc"][0]) if entry.get("loc") else ""
            label = names.get(name, name)
            if label not in fields:
                fields.append(label)
                reasons.append(f"欄「{label}」の値を{_type_word(entry.get('type', ''))}として読めない")
        return SourceDefect(**defect, missing_fields=[], invalid_fields=fields, reason="、".join(reasons))


def _text(value: object) -> str:
    """欄の値を、断りに載せる文字列にそろえる。読めていなければ空文字。"""
    return str(value).strip() if value is not None else ""


class MarkdownRepository:
    """正本のディレクトリを 1 つ受け取り、その中の Markdown を読み書きする。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ------------------------------------------------------------ 読む

    def _read(self, key: str) -> str:
        """正本を 1 つ読む。ファイルが無ければ空文字を返す（無い正本は空として扱う）。"""
        path = self.settings.path_for(key)
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def _rule(self, key: str) -> BlockRule:
        """正本 1 種の読み方を返す。読み方は accord の形が決める。"""
        return self.settings.reading.rule_for(key)

    def _blocks(self, key: str) -> tuple[list[Section], BlockRule]:
        """正本 1 種を読み、その正本の読み方で選んだ節と、読み方そのものを返す。

        職歴の枠と受託案件のように、1 つのファイルを 2 種の正本として読むこともある。
        accord の形では同じファイルを指し、見出しの深さで分ける。
        """
        rule = self._rule(key)
        return select_blocks(split_sections(self._read(key)), rule), rule

    def _blocks_in(self, key: str, text: str) -> list[Section]:
        """書き戻す前の文字列を、その正本の読み方で節に切る。"""
        return select_blocks(split_sections(text), self._rule(key))

    def load(self) -> SourceSnapshot:
        """8 種の正本を読み、型のインスタンスの集合にする。

        必須の欄が欠けたブロックや節は型にできないので集合には入らないが、飛ばしたこと自体を
        defects に載せて渡す。黙って飛ばすと、1 つ前か隣のブロックが「いまの正本」として
        通ってしまい、読んだ側が逆向きの直し先を受け取る。
        """
        positionings, positioning_defects = self._load_positionings()
        packages, package_defects = self._load_packages()
        capabilities, capability_defects = self._load_capabilities()
        career_frames, career_defects = self._load_career_frames()
        engagements, engagement_defects = self._load_engagements()
        public_records, public_record_defects = self._load_public_records()
        presentations, presentation_urls, presentation_defects = self._load_presentations()
        ledger_entries, ledger_defects = self._load_ledger_entries()
        return SourceSnapshot(
            positionings=positionings,
            packages=packages,
            capabilities=capabilities,
            career_frames=career_frames,
            engagements=engagements,
            public_records=public_records,
            presentations=presentations,
            ledger_entries=ledger_entries,
            presentation_urls=presentation_urls,
            defects=[
                *positioning_defects,
                *package_defects,
                *capability_defects,
                *career_defects,
                *engagement_defects,
                *public_record_defects,
                *presentation_defects,
                *ledger_defects,
            ],
            skipped_headings=self._skipped_headings(),
            unread_ledger_sections=self._unread_ledger_sections(),
            section_fingerprints=self.section_fingerprints(),
        )

    def _unread_ledger_sections(self) -> list[SkippedHeading]:
        """職務経歴書の台帳の節のうち、読み方の深さにあって読み方の絞りで外れたものを集める。

        深さの外の節（題名の見出しや、読んだブロックの下位の見出し）は数えない。そうした節は
        ブロックの一部か台帳全体の題名で、読まなかったと言うと読み手が直す先を取り違えるからである。
        検査はこの一覧を 1 件の断りにして、何を見なかったかを結果に出す。
        """
        rule = self._rule(LEDGER_KEY)
        levels = set(rule.heading_levels)
        found: list[SkippedHeading] = []
        ancestors: list[tuple[int, str]] = []
        for section in split_sections(self._read(LEDGER_KEY)):
            while ancestors and ancestors[-1][0] >= section.level:
                ancestors.pop()
            above = [heading for _, heading in ancestors]
            if not section.heading:
                continue
            ancestors.append((section.level, section.heading))
            # spec: REQ-394
            if section.level not in levels:
                continue
            reasons = _skip_reasons(section, above, rule)
            if not reasons:
                continue
            found.append(
                SkippedHeading(
                    source_key=LEDGER_KEY,
                    heading=section.heading,
                    level=section.level,
                    parents=above,
                    reason="、".join(reasons),
                )
            )
        return found

    def section_fingerprints(self) -> dict[str, str]:
        """職歴の枠と受託案件の節の ID と、その節のいまの本文の指紋の対応を返す。

        本文は accord がその項目を読むのと同じ節で、下位の見出しの本文は含まない。入れ子の正本で
        受託案件の本文を直しても、上の職歴の枠の指紋は変わらない。ID の行も本文のうちに数える。
        ID の行を持たない節は、指しようが無いので入れない。
        """
        fingerprints: dict[str, str] = {}
        for key in EVIDENCE_SOURCE_KEYS:
            blocks, rule = self._blocks(key)
            for section in blocks:
                identifier = read_fields(section, rule).get(ID_LABEL, "").strip()
                if identifier:
                    fingerprints.setdefault(identifier, section_fingerprint(section.body))
        return fingerprints

    def _skipped_headings(self) -> list[SkippedHeading]:
        """裏づけと出典が指せる 2 種について、読み方の絞りで外れた節を集める。

        指された ID が読めていないとき、「どこにも無い」のか「実在するが読み取り範囲の外」なのかで
        直し先が正反対になる。その言い分けの材料をここで作る。同じ節が 2 種の両方で外れたときは
        両方入れ、探す側は先に見つかったほうを使う。
        外れた節でも欄は読む。読まないと ID が取れず、言い分けそのものができないからである。
        """
        found: list[SkippedHeading] = []
        for key in EVIDENCE_SOURCE_KEYS:
            rule = self._rule(key)
            ancestors: list[tuple[int, str]] = []
            for section in split_sections(self._read(key)):
                while ancestors and ancestors[-1][0] >= section.level:
                    ancestors.pop()
                above = [heading for _, heading in ancestors]
                if not section.heading:
                    # 見出しの無い先頭の塊は、読み方の絞りに当たる対象ではない。
                    continue
                ancestors.append((section.level, section.heading))
                reasons = _skip_reasons(section, above, rule)
                if not reasons:
                    continue
                found.append(
                    SkippedHeading(
                        source_key=key,
                        heading=section.heading,
                        id=read_fields(section, rule).get(ID_LABEL, "").strip(),
                        level=section.level,
                        parents=above,
                        reason="、".join(reasons),
                    )
                )
        return found

    def _load_positionings(self) -> tuple[list[Positioning], list[SourceDefect]]:
        """売り方の決めを、1 決め 1 ブロックで読む。

        欄が欠けたブロックは決めとして読めないので、読めなかったことと欠けた欄の名前を
        2 つ目の返り値に入れる。どちらを返すかではなく、両方を返すのがこの関数の仕事である。
        """
        result: list[Positioning] = []
        defects: list[SourceDefect] = []
        blocks, rule = self._blocks("positioning")
        for block in blocks:
            fields = read_fields(block, rule)
            missing = [label for label in POSITIONING_LABELS if label not in fields]
            if missing:
                defects.append(
                    SourceDefect(
                        file=self.settings.files["positioning"],
                        location=f"「{block.heading}」のブロック",
                        missing_fields=missing,
                        source_key="positioning",
                        heading=block.heading,
                    )
                )
                continue
            values = {name: fields[label] for label, name in POSITIONING_LABELS.items()}
            values["exceptions"] = self._parse_exceptions(
                fields.get(POSITIONING_EXCEPTIONS_LABEL, "")
            )
            item = _typed(
                Positioning,
                values,
                POSITIONING_LABELS,
                {
                    "file": self.settings.files["positioning"],
                    "location": f"「{block.heading}」のブロック",
                    "source_key": "positioning",
                    "heading": block.heading,
                },
            )
            if isinstance(item, SourceDefect):
                defects.append(item)
                continue
            result.append(item)
        return result, defects

    @staticmethod
    def _parse_exceptions(value: str) -> list[dict[str, str]]:
        """例外の欄を「提示物」と「理由」の組の一覧にする。"""
        exceptions: list[dict[str, str]] = []
        for line in value.splitlines():
            entry = line.strip()
            if not entry or entry in EMPTY_WORDS:
                continue
            if EXCEPTION_SEPARATOR in entry:
                presentation, reason = entry.split(EXCEPTION_SEPARATOR, 1)
            else:
                presentation, reason = entry, ""
            exceptions.append(
                {
                    EXCEPTION_PRESENTATION_KEY: presentation.strip(),
                    EXCEPTION_REASON_KEY: reason.strip(),
                }
            )
        return exceptions

    def _load_packages(self) -> tuple[list[Package], list[SourceDefect]]:
        """パッケージ定義を読む。必須の欄が欠けた節は型にできないので、飛ばしたことを断りに残す。"""
        result: list[Package] = []
        defects: list[SourceDefect] = []
        blocks, rule = self._blocks("packages")
        for block in blocks:
            fields = read_fields(block, rule)
            values: dict[str, object] = {
                name: fields.get(label) for label, name in PACKAGE_LABELS.items()
            }
            values["name"] = block.heading
            values["capabilities"] = _split_list(fields.get(PACKAGE_CAPABILITIES_LABEL, ""))

            missing = missing_required_fields(PACKAGE_TYPE_NAME, SimpleNamespace(**values))
            if missing:
                defects.append(
                    SourceDefect(
                        file=self.settings.files["packages"],
                        location=f"「{block.heading}」の節",
                        missing_fields=[field.label for field in missing],
                        source_key="packages",
                        heading=block.heading,
                        id=_text(values.get("id")),
                    )
                )
                continue

            for optional_name in ("basis", "source", "breaks_when"):
                values[optional_name] = _optional(values.get(optional_name))
            item = _typed(
                Package,
                values,
                PACKAGE_LABELS,
                {
                    "file": self.settings.files["packages"],
                    "location": f"「{block.heading}」の節",
                    "source_key": "packages",
                    "heading": block.heading,
                    "id": _text(values.get("id")),
                },
            )
            if isinstance(item, SourceDefect):
                defects.append(item)
                continue
            result.append(item)
        return result, defects

    def _load_capabilities(self) -> tuple[list[Capability], list[SourceDefect]]:
        """機能の台帳を読む。節の見出しが分類、表の 1 行が機能 1 つ。

        表の列は「ID、機能名、説明、裏づけ」の並びで、この関数はその並びに依存する。
        機能は節ではなく表の 1 行なので、ID も行ではなく列で持つ。
        必須の欄が欠けた行（列が足りない、値が空）は型にできないので、飛ばしたことを断りに残す。
        """
        result: list[Capability] = []
        defects: list[SourceDefect] = []
        blocks, _ = self._blocks("capabilities")
        for block in blocks:
            rows = [cells for table in table_blocks(block.body) for cells in table]
            for index, cells in enumerate(rows, start=1):
                values = {
                    "id": cells[0] if len(cells) > 0 else None,
                    "name": cells[1] if len(cells) > 1 else None,
                    "description": cells[2] if len(cells) > 2 else None,
                    "category": block.heading,
                    "evidence_sections": _split_list(cells[3]) if len(cells) > 3 else [],
                }
                missing = missing_required_fields(
                    CAPABILITY_TYPE_NAME, SimpleNamespace(**values)
                )
                if missing:
                    defects.append(
                        SourceDefect(
                            file=self.settings.files["capabilities"],
                            location=f"分類「{block.heading}」の表の{index}行目",
                            missing_fields=[field.label for field in missing],
                            source_key="capabilities",
                            heading=block.heading,
                            id=_text(values.get("id")),
                        )
                    )
                    continue
                item = _typed(
                    Capability,
                    values,
                    CAPABILITY_COLUMN_LABELS,
                    {
                        "file": self.settings.files["capabilities"],
                        "location": f"分類「{block.heading}」の表の{index}行目",
                        "source_key": "capabilities",
                        "heading": block.heading,
                        "id": _text(values.get("id")),
                    },
                )
                if isinstance(item, SourceDefect):
                    defects.append(item)
                    continue
                result.append(item)
        return result, defects

    def _load_career_frames(self) -> tuple[list[CareerFrame], list[SourceDefect]]:
        """職歴の枠を読む。必須の欄が欠けたブロックは型にできないので、飛ばしたことを断りに残す。"""
        result: list[CareerFrame] = []
        defects: list[SourceDefect] = []
        blocks, rule = self._blocks("career")
        for block in blocks:
            fields = read_fields(block, rule)
            values: dict[str, object] = {
                name: fields.get(label) for label, name in CAREER_LABELS.items()
            }
            values["heading"] = block.heading

            missing = missing_required_fields(CAREER_FRAME_TYPE_NAME, SimpleNamespace(**values))
            if missing:
                defects.append(
                    SourceDefect(
                        file=self.settings.files["career"],
                        location=f"「{block.heading}」のブロック",
                        missing_fields=[field.label for field in missing],
                        source_key="career",
                        heading=block.heading,
                        id=_text(values.get("id")),
                    )
                )
                continue
            item = _typed(
                CareerFrame,
                values,
                CAREER_LABELS,
                {
                    "file": self.settings.files["career"],
                    "location": f"「{block.heading}」のブロック",
                    "source_key": "career",
                    "heading": block.heading,
                    "id": _text(values.get("id")),
                },
            )
            if isinstance(item, SourceDefect):
                defects.append(item)
                continue
            result.append(item)
        return result, defects

    def _load_engagements(self) -> tuple[list[Engagement], list[SourceDefect]]:
        """受託案件を読む。必須の欄が欠けたブロックは型にできないので、飛ばしたことを断りに残す。"""
        result: list[Engagement] = []
        defects: list[SourceDefect] = []
        blocks, rule = self._blocks("engagements")
        for block in blocks:
            fields = read_fields(block, rule)
            values: dict[str, object] = {
                name: fields.get(label) for label, name in ENGAGEMENT_LABELS.items()
            }
            values["heading"] = block.heading

            missing = missing_required_fields(ENGAGEMENT_TYPE_NAME, SimpleNamespace(**values))
            if missing:
                defects.append(
                    SourceDefect(
                        file=self.settings.files["engagements"],
                        location=f"「{block.heading}」のブロック",
                        missing_fields=[field.label for field in missing],
                        source_key="engagements",
                        heading=block.heading,
                        id=_text(values.get("id")),
                    )
                )
                continue
            item = _typed(
                Engagement,
                values,
                ENGAGEMENT_LABELS,
                {
                    "file": self.settings.files["engagements"],
                    "location": f"「{block.heading}」のブロック",
                    "source_key": "engagements",
                    "heading": block.heading,
                    "id": _text(values.get("id")),
                },
            )
            if isinstance(item, SourceDefect):
                defects.append(item)
                continue
            result.append(item)
        return result, defects

    def _load_public_records(self) -> tuple[list[PublicRecord], list[SourceDefect]]:
        """公開記録を、1 件 1 ブロックで読む。

        置き場が設定に書かれていなければ、公開記録を 0 件として返す。書かなくてもよい置き場は
        これ 1 つで、書いていない正本は公開記録を使わない正本として、今までどおり読める。
        """
        if not self.settings.has_file(PUBLIC_RECORDS_KEY):
            return [], []

        result: list[PublicRecord] = []
        defects: list[SourceDefect] = []
        blocks, rule = self._blocks(PUBLIC_RECORDS_KEY)
        for block in blocks:
            fields = read_fields(block, rule)
            values: dict[str, object] = {
                name: fields.get(label) for label, name in PUBLIC_RECORD_LABELS.items()
            }
            values["name"] = block.heading

            missing = missing_required_fields(PUBLIC_RECORD_TYPE_NAME, SimpleNamespace(**values))
            if missing:
                defects.append(
                    SourceDefect(
                        file=self.settings.files[PUBLIC_RECORDS_KEY],
                        location=f"「{block.heading}」のブロック",
                        missing_fields=[field.label for field in missing],
                        source_key=PUBLIC_RECORDS_KEY,
                        heading=block.heading,
                        id=_text(values.get("id")),
                    )
                )
                continue

            # URL・由来の節・出所は、空を表す語（「なし」など）で書かれていたら持たないものとして読む。
            for optional_name in ("url", "origin_section", "source"):
                values[optional_name] = _optional(values.get(optional_name))
            item = _typed(
                PublicRecord,
                values,
                PUBLIC_RECORD_LABELS,
                {
                    "file": self.settings.files[PUBLIC_RECORDS_KEY],
                    "location": f"「{block.heading}」のブロック",
                    "source_key": PUBLIC_RECORDS_KEY,
                    "heading": block.heading,
                    "id": _text(values.get("id")),
                },
            )
            if isinstance(item, SourceDefect):
                defects.append(item)
                continue
            result.append(item)
        return result, defects

    def _load_ledger_entries(self) -> tuple[list[ResumeLedger], list[SourceDefect]]:
        """職務経歴書の台帳を、1 ブロックずつ読む。ブロックは案件か在籍職歴の枠のどちらか。

        見出しが在籍職歴の枠の前置き（frame_heading_prefix）で始まるブロックは在籍職歴の枠、
        それ以外は案件として読む。必須の欄は種類で変わり（型の正本の required_for_kinds）、
        在籍職歴の枠には案件だけの欄を求めない。
        必須の欄が欠けたブロックは型にできないので、飛ばしたことを断りに残す。
        """
        result: list[ResumeLedger] = []
        defects: list[SourceDefect] = []
        blocks, rule = self._blocks(LEDGER_KEY)
        for block in blocks:
            fields = read_fields(block, rule)
            values: dict[str, object] = {
                name: fields.get(label) for label, name in LEDGER_LABELS.items()
            }
            is_frame = is_frame_heading(block.heading, rule)
            values["kind"] = LEDGER_KIND_FRAME if is_frame else LEDGER_KIND_ENTRY
            values["heading"] = block.heading
            values["fold_line"] = _optional(values.get("fold_line"))
            values["source_fingerprints"] = parse_fingerprints(
                str(values.get("source_fingerprints") or "")
            )
            if rule.entry_number_from_heading:
                # 案件番号を欄ではなく見出しの数字で持つ書き方。欄があればそちらを優先しない。
                prefix = rule.frame_heading_prefix if is_frame else rule.heading_prefix
                number = leading_number(block.heading, prefix)
                if number:
                    values["entry_number"] = number

            # spec: REQ-376
            missing = missing_required_fields(RESUME_LEDGER_TYPE_NAME, SimpleNamespace(**values))
            if missing:
                # spec: REQ-377
                defects.append(
                    SourceDefect(
                        file=self.settings.files[LEDGER_KEY],
                        location=f"「{block.heading}」のブロック",
                        missing_fields=[field.label for field in missing],
                        source_key=LEDGER_KEY,
                        heading=block.heading,
                    )
                )
                continue
            item = _typed(
                ResumeLedger,
                values,
                LEDGER_LABELS,
                {
                    "file": self.settings.files[LEDGER_KEY],
                    "location": f"「{block.heading}」のブロック",
                    "source_key": LEDGER_KEY,
                    "heading": block.heading,
                },
            )
            if isinstance(item, SourceDefect):
                defects.append(item)
                continue
            result.append(item)
        return result, defects

    def _presentation_files(self) -> list[Path]:
        """提示物として読む Markdown を集める。

        提示物の置き場の下の、語彙の媒体と同じ名前のディレクトリだけをたどる。媒体ディレクトリの
        下には、提示物でないファイルも同居するので、宣言の行で絞るのは読む側である。
        提示物の置き場が起動の引数で渡されていなければ、提示物は 0 件である。
        """
        # spec: REQ-504
        if self.settings.presentations_dir is None:
            return []
        root = self.settings.path_for("presentations")
        found: list[Path] = []
        for name in self.settings.reading.presentation_directories:
            directory = root / name
            if directory.is_dir():
                found.extend(sorted(directory.rglob("*.md")))
        return found

    def _load_presentations(
        self,
    ) -> tuple[list[Presentation], list[PresentationUrl], list[SourceDefect]]:
        """提示物を読む。媒体ごとのディレクトリの下の Markdown が 1 件ずつ。

        必須の欄（宛先の媒体・宣言する束）が欠けたファイルは型にできないので、飛ばしたことを断りに残す。
        ただし、宣言の行を持つものだけを提示物として読む設定のときは、宣言を持たないファイルを
        提示物と見なさないので、断りにも残さない。

        あわせて、提示物として読んだファイルの本文に貼られた URL を拾う。提示物として読まなかった
        ファイル（宣言の行を持たないもの）からは拾わない。正規化して同じになる URL は 1 件に落とす。
        """
        result: list[Presentation] = []
        urls: list[PresentationUrl] = []
        defects: list[SourceDefect] = []
        rule = self._rule("presentations")
        require_declaration = self.settings.reading.require_presentation_declaration

        for path in self._presentation_files():
            text = path.read_text(encoding="utf-8")
            document = Section(level=0, heading="", body=text)
            fields = read_fields(document, rule)
            relative = path.relative_to(self.settings.presentations_dir).as_posix()
            values: dict[str, object] = {
                name: fields.get(label) for label, name in PRESENTATION_LABELS.items()
            }
            values["path"] = relative

            if require_declaration and not values.get("declared_package"):
                continue

            missing = missing_required_fields(PRESENTATION_TYPE_NAME, SimpleNamespace(**values))
            if missing:
                defects.append(
                    SourceDefect(
                        file=relative,
                        location="先頭の欄",
                        missing_fields=[field.label for field in missing],
                        source_key="presentations",
                    )
                )
                continue

            values["created_on"] = _optional(values.get("created_on"))
            # spec: REQ-391
            values["source_sections"] = _split_list(fields.get(PRESENTATION_SOURCE_LABEL, ""))
            values["source_fingerprints"] = parse_fingerprints(
                fields.get(PRESENTATION_FINGERPRINT_LABEL, "")
            )
            values["pending_notes"] = [
                note
                for note in fields.get("未反映の注記", "").splitlines()
                if note.strip() and note.strip() not in EMPTY_WORDS
            ]
            item = _typed(
                Presentation,
                values,
                PRESENTATION_LABELS,
                {"file": relative, "location": "先頭の欄", "source_key": "presentations"},
            )
            if isinstance(item, SourceDefect):
                defects.append(item)
                continue
            result.append(item)
            urls.extend(self._presentation_urls(relative, text))
        return result, urls, defects

    @staticmethod
    def _presentation_urls(relative: str, text: str) -> list[PresentationUrl]:
        """提示物 1 枚の本文から URL を拾う。正規化して同じになるものは 1 件に落とす。"""
        found: list[PresentationUrl] = []
        seen: set[str] = set()
        for url in find_urls(text):
            normalized = normalize_url(url)
            # spec: REQ-045
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            found.append(PresentationUrl(path=relative, url=url, normalized=normalized))
        return found

    def evidence_bodies(self) -> dict[str, str]:
        """裏づけとして指せる節の ID と、その本文の対応を返す。

        型に射影した欄ではなく本文をそのまま渡すのは、文面を書く側が読むのは節の中身だからである。
        鍵は ID で、ID は正本全体で一意なので、どちらの正本を先に読むかで中身が入れ替わらない。
        ID の行を持たない節は、指しようが無いので入れない。
        本文からは ID の行だけを落とす。ID は鍵としても欄としても別に返しているので、本文にも
        残すと、文面を書く側が同じ値を 2 か所で受け取り、どちらを使うのか決める手間が増える。
        落とすのは ID の行だけで、ほかの欄の行はそのまま渡す。
        """
        bodies: dict[str, str] = {}
        for key in EVIDENCE_SOURCE_KEYS:
            blocks, rule = self._blocks(key)
            for section in blocks:
                # spec: REQ-303
                identifier = read_fields(section, rule).get(ID_LABEL, "").strip()
                # spec: REQ-304
                if identifier:
                    bodies.setdefault(
                        # spec: REQ-301
                        identifier, drop_field_lines(section.body, (ID_LABEL,), rule)
                    )
        return bodies

    def _presentation_rule_sections(self) -> list[Section]:
        """見せ方の正本を節に切り分ける。ファイルが無ければ空の一覧を返す。"""
        blocks, _ = self._blocks(PRESENTATION_RULES_KEY)
        return blocks

    def channel_rules(self, channel: str) -> list[str]:
        """その媒体の規約（文字数の上限、書き出しの決まり）を箇条書きの一覧で返す。

        置き場は 2 通りある。見せ方の正本 1 つの中の、媒体の名前の節から読む書き方と、
        媒体ごとのファイルから読む書き方である。どちらかは設定が決める。
        節もファイルも無ければ空の一覧を返す。
        """
        rules = self.settings.reading
        if rules.channel_rules_from == CHANNEL_RULES_PER_CHANNEL_FILE:
            # spec: REQ-504
            if self.settings.presentations_dir is None:
                return []
            path = self.settings.presentations_dir / rules.channel_rules_file.replace(
                CHANNEL_PLACEHOLDER, channel
            )
            # spec: REQ-069
            if not path.is_file():
                return []
            return bullet_items(path.read_text(encoding="utf-8"))

        section = find_section(self._presentation_rule_sections(), channel)
        return bullet_items(section.body) if section is not None else []

    def _forbidden_phrases_section(self) -> Section | None:
        """禁じた言い回しの節を、見出しの名前で探す。

        見出しに但し書きの括弧が付く正本があるので、括弧書きを落としてから比べる。
        深さを問わずに探すかどうかは設定が決める。問わない設定のときは、どの深さの
        見出しでも名前が合えばその節を返す。
        """
        rules = self.settings.reading
        sections = split_sections(self._read(PRESENTATION_RULES_KEY))
        if not rules.forbidden_phrases_any_level:
            sections = select_blocks(sections, self._rule(PRESENTATION_RULES_KEY))

        # spec: REQ-071
        wanted = strip_note(rules.forbidden_phrases_heading)
        for section in sections:
            if section.heading and strip_note(section.heading) == wanted:
                return section
        return None

    def forbidden_phrases(self) -> list[str]:
        """見せ方の正本の、媒体によらない節から、禁じた言い回しを返す。

        中身は、節の最初の表の 1 列目か、節の最初の箇条書きの塊のどちらかで、設定が決める。
        最初の 1 つに限るのは、同じ節に別の話の表や箇条書きが続けて置かれている正本があり、
        全部を拾うと禁じた言い回しでないものが混ざるからである。
        """
        section = self._forbidden_phrases_section()
        if section is None:
            return []
        if self.settings.reading.forbidden_phrases_from == PHRASES_FROM_TABLE:
            tables = table_blocks(section.body)
            if not tables:
                return []
            return [cells[0] for cells in tables[0] if cells and cells[0]]
        return bullet_items(section.body, first_block=True)

    # ------------------------------------------------------------ 正本のファイルを節で読む

    def source_file_names(self) -> list[str]:
        """正本のファイルの名前を、設定の並びの順に返す（提示物は除き、重なりは 1 つに数える）。"""
        return self.settings.source_file_names()

    def source_path(self, name: str) -> Path:
        """正本のファイルの名前から、実ファイルの場所を返す。上の層には渡さない。"""
        return self.settings.source_dir / name

    def read_source_file(self, name: str) -> str:
        """正本のファイルを 1 つ読む。無ければ空文字。"""
        path = self.source_path(name)
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def _rule_for_file(self, name: str) -> BlockRule:
        """そのファイルを指す最初の役割の読み方。欄の読み替えは役割を問わず共通である。"""
        keys = self.settings.keys_for_file(name)
        return self._rule(keys[0]) if keys else self._rule("career")

    def source_sections(self, name: str, text: str | None = None) -> list[SourceSection]:
        """正本のファイル 1 つの、見出しを持つ節を、ファイルの並びの順に返す。

        text を渡すと、ファイルではなくその文字列を切る（書く前の判定に使う）。
        ID と公開可否は、その節自身の本文の欄から読む（下位の見出しの節の欄は見ない）。
        """
        rule = self._rule_for_file(name)
        content = self.read_source_file(name) if text is None else text
        found: list[SourceSection] = []
        for item in outline_sections(content):
            section = item.section
            fields = read_fields(section, rule)
            identifier = fields.get(ID_LABEL, "").strip() or None
            disclosure_value = fields.get(DISCLOSURE_LABEL, "").strip()
            found.append(
                SourceSection(
                    file=name,
                    heading_path=item.path,
                    heading=section.heading,
                    heading_line=content.splitlines()[section.start],
                    body=section.body,
                    fingerprint=section_fingerprint(section.body),
                    id=identifier,
                    disclosure=(disclosure_value or None) if identifier else None,
                    private=disclosure_value.startswith(PRIVATE_DISCLOSURE_PREFIX),
                    level=section.level,
                    start=section.start,
                    end=section.end,
                )
            )
        return found

    def source_lines(self, name: str) -> list[tuple[str, str]]:
        """正本のファイル 1 つの行を、その行がある節の見出しの道筋と組にして返す。

        見出しの行は、その見出しの節の行として数える。最初の見出しより前の行の道筋は空にする。
        frontmatter の行は入れない。
        """
        content = self.read_source_file(name)
        lines = content.splitlines()
        paths: dict[int, str] = {}
        outlined = outline_sections(content)
        for item in outlined:
            for index in range(item.section.start, item.section.end):
                paths[index] = item.path
        first = outlined[0].section.start if outlined else len(lines)
        preamble = split_sections(content)[0] if content else None
        found: list[tuple[str, str]] = []
        if preamble is not None and not preamble.heading:
            for index in range(preamble.start, min(preamble.end, first)):
                found.append(("", lines[index]))
        for index in range(first, len(lines)):
            found.append((paths.get(index, ""), lines[index]))
        return found

    def replaced_text(self, section: SourceSection, body: str) -> str:
        """節の本文を置き換えた後のファイルの全文を返す。ファイルには書かない。"""
        text = self.read_source_file(section.file)
        return replace_section_body(text, _as_section(section), body)

    def appended_text(self, section: SourceSection, line: str) -> str:
        """節の本文の末尾に 1 行足した後のファイルの全文を返す。ファイルには書かない。"""
        text = self.read_source_file(section.file)
        return append_section_line(text, _as_section(section), line)

    def renamed_text(self, section: SourceSection, heading: str) -> str:
        """節の見出しの文字だけを置き換えた後のファイルの全文を返す。ファイルには書かない。"""
        return rename_heading(self.read_source_file(section.file), section.start, heading)

    def added_text(
        self,
        file_name: str,
        parent: SourceSection | None,
        heading: str,
        body: str,
        before: SourceSection | None = None,
    ) -> str:
        """親の節の下（親が None なら深さ 1）に節を 1 つ足した後のファイルの全文を返す。ファイルには書かない。"""
        return insert_section(
            self.read_source_file(file_name),
            parent.start if parent is not None else None,
            heading,
            body,
            before.start if before is not None else None,
        )

    def removed_text(self, section: SourceSection) -> str:
        """節の見出しの行と本文を消した後のファイルの全文を返す。ファイルには書かない。"""
        return delete_section(self.read_source_file(section.file), section.start)

    def moved_levels(self, section: SourceSection, new_parent: SourceSection | None) -> list[int]:
        """節を新しい親の下（親が None なら深さ 1）へ動かしたときの、その節と下位の節の深さを返す。"""
        return shifted_levels(
            self.read_source_file(section.file),
            section.start,
            new_parent.start if new_parent is not None else None,
        )

    def moved_text(
        self,
        section: SourceSection,
        new_parent: SourceSection | None,
        before: SourceSection | None = None,
    ) -> str:
        """節を下位の節ごと新しい親の下（親が None なら深さ 1）へ移した後の全文を返す。ファイルには書かない。"""
        return move_section(
            self.read_source_file(section.file),
            section.start,
            new_parent.start if new_parent is not None else None,
            before.start if before is not None else None,
        )

    def disclosure_lines(self, section: SourceSection) -> list[tuple[str, str]]:
        """節の本文の公開可否の欄の行を、（行そのもの、値）の組で書かれた順に返す。"""
        return field_lines(
            self.read_source_file(section.file),
            section.start,
            DISCLOSURE_LABEL,
            self._rule_for_file(section.file),
        )

    def disclosure_lines_in(self, section: SourceSection, text: str) -> list[tuple[str, str]]:
        """全文 text の中の、section と同じ位置の節の公開可否の欄の行を返す（書く前の判定に使う）。"""
        return field_lines(text, section.start, DISCLOSURE_LABEL, self._rule_for_file(section.file))

    def disclosure_lines_by_item(
        self, section: SourceSection, text: str | None = None
    ) -> list[tuple[str, str | None]]:
        """節の公開可否の行を、（行そのもの、その行が属する項目の先頭の行。節の欄なら None）で返す。

        text を渡すと、ファイルではなくその全文の、同じ位置の節を見る。
        """
        content = self.read_source_file(section.file) if text is None else text
        return [
            (line, head)
            for line, _, head in field_lines_with_items(
                content, section.start, DISCLOSURE_LABEL, self._rule_for_file(section.file)
            )
        ]

    def disclosure_items(self, section: SourceSection, text: str | None = None) -> list[tuple[str, bool]]:
        """節の本文のいちばん浅い箇条書きの項目を、（先頭の行、公開可否の行を持つか）で返す。

        型の欄の行（「- 期間: …」のような、型の欄の名前に読める行）で始まる項目は数えない。
        text を渡すと、ファイルではなくその全文の、同じ位置の節を見る。
        """
        known = {
            *CAREER_LABELS,
            *ENGAGEMENT_LABELS,
            *LEDGER_LABELS,
            *PUBLIC_RECORD_LABELS,
            *PACKAGE_LABELS,
            *POSITIONING_LABELS,
            *PRESENTATION_LABELS,
            PACKAGE_CAPABILITIES_LABEL,
            POSITIONING_EXCEPTIONS_LABEL,
        }
        content = self.read_source_file(section.file) if text is None else text
        return list_items(content, section.start, DISCLOSURE_LABEL, known, self._rule_for_file(section.file))

    def disclosure_text(self, section: SourceSection, value: str, number: int | None = None) -> str:
        """節の公開可否の欄の値を置き換えた（欄が無ければ ID の欄の行の直後に足した）後の全文を返す。

        number（1 始まり）を渡すと、公開可否の行のうちその番号の行だけを置き換える。
        """
        return set_field(
            self.read_source_file(section.file),
            section.start,
            DISCLOSURE_LABEL,
            value,
            ID_LABEL,
            self._rule_for_file(section.file),
            number,
        )

    def write_source_file(self, name: str, text: str) -> None:
        """正本のファイル 1 つを、渡された全文で書き換える。"""
        self.source_path(name).write_text(text, encoding="utf-8")

    def source_digest(self) -> str:
        """正本のファイルすべてと語彙のファイルの中身から、1 つの指紋を作る。1 バイトでも変われば値が変わる。

        語彙のファイルを入れるのは、移行の操作が語彙を作った後に、移行の前の語彙で検査した結果を
        使い回さないためである。
        """
        digest = hashlib.sha256()
        vocabulary = self.settings.vocabulary_path
        digest.update(vocabulary.read_bytes() if vocabulary.is_file() else b"\1missing")
        digest.update(b"\0")
        for name in self.source_file_names():
            path = self.source_path(name)
            digest.update(name.encode("utf-8") + b"\0")
            digest.update(path.read_bytes() if path.is_file() else b"\1missing")
            digest.update(b"\0")
        return digest.hexdigest()

    # ------------------------------------------------------------ 語彙のファイルと、移行の確かめ

    @staticmethod
    def vocabulary_text(vocabulary: dict[str, list[str]]) -> str:
        """語彙を、accord の形の vocabulary.md の全文にする。

        1 行目に語彙の見出し、種類ごとに深さ 2 の見出しの節を置き、語を「- 語」で 1 行ずつ書く。
        語が 0 件の種類も節を置く。
        """
        lines = [f"# {VOCABULARY_TITLE}"]
        for kind, _ in VOCABULARY_KINDS:
            lines += ["", f"## {kind}"]
            words = vocabulary.get(kind, [])
            if words:
                lines.append("")
                lines += [f"- {word}" for word in words]
        return "\n".join(lines) + "\n"

    def write_vocabulary_file(self, text: str) -> None:
        """語彙のファイルを書く。"""
        self.settings.vocabulary_path.write_text(text, encoding="utf-8")

    def form_skipped_headings(self, key: str) -> list[str]:
        """その正本のうち、accord の形の読み方の深さにあり、型の欄を 1 つも持たないので読み飛ばす節の見出し。

        移行の操作が、移行の前の設定ファイルに書かれた読み飛ばす見出しと比べるために使う。
        """
        rule = self._rule(key)
        if not rule.skip_sections_without_labels:
            return []
        labels = set(rule.skip_sections_without_labels)
        return [
            section.heading
            for section in split_sections(self._read(key))
            if section.heading
            and section.level in set(rule.heading_levels)
            and not labels & set(read_fields(section, rule))
        ]

    def vocabulary_with_term(self, kind: str, term: str) -> str:
        """語彙のファイルの、その種類の節の末尾に「- 語」の 1 行を足した全文を返す（ファイルは書かない）。

        節の中のほかの行（語の行・空行・注記）は変えない。種類の節が無ければ、ファイルの末尾に節ごと足す。
        """
        lines = self._vocabulary_lines()
        start, end = _vocabulary_section(lines, kind)
        if start is None:
            while lines and not lines[-1].strip():
                lines.pop()
            return "\n".join([*lines, "", f"## {kind}", "", f"- {term}"]) + "\n"
        terms = [index for index in range(start + 1, end) if TERM_RE.match(lines[index].strip())]
        if terms:
            position = terms[-1] + 1
            inserted = [f"- {term}"]
        else:
            position = start + 1
            inserted = ["", f"- {term}"]
            if position < end and not lines[position].strip():
                position += 1
                inserted = [f"- {term}"]
        if position < len(lines) and lines[position].strip():
            inserted.append("")
        lines[position:position] = inserted
        return "\n".join(lines) + "\n"

    def vocabulary_without_term(self, kind: str, term: str) -> str:
        """語彙のファイルの、その種類の節から語の行を消した全文を返す（ファイルは書かない）。

        語の行を消して空行が 2 つ続くときは、1 つにたたむ。ほかの節は変えない。
        """
        lines = self._vocabulary_lines()
        start, end = _vocabulary_section(lines, kind)
        if start is None:
            return "\n".join(lines) + "\n"
        kept = lines[: start + 1]
        for line in lines[start + 1 : end]:
            match = TERM_RE.match(line.strip())
            if match is not None and match.group(1) == term:
                continue
            if not line.strip() and kept and not kept[-1].strip():
                continue
            kept.append(line)
        kept.extend(lines[end:])
        return "\n".join(kept) + "\n"

    def _vocabulary_lines(self) -> list[str]:
        path = self.settings.vocabulary_path
        return path.read_text(encoding="utf-8").splitlines() if path.is_file() else [f"# {VOCABULARY_TITLE}"]

    def term_users(self, kind: str, term: str) -> list[str]:
        """その種類の語を値に持つ正本の節の見出しの道筋を、正本の並びの順に返す。

        見るのは、整合の検査が語彙と照らしている欄だけである。媒体と決めの適用先は売り方の決めの
        適用範囲（末尾の括弧書きを落とす）、機能の分類は機能の台帳の分類の節の見出し、パッケージの
        仮説の状態はパッケージ定義の欄（末尾の括弧書きを落とす）、公開記録の種類と役割は公開記録の欄。
        提示物は正本の節ではないので見ない。
        """
        wanted = term.strip()
        scope = _label_of(POSITIONING_LABELS, "scope")
        state = _label_of(PACKAGE_LABELS, "hypothesis_state")
        record_kind = _label_of(PUBLIC_RECORD_LABELS, "kind")
        record_role = _label_of(PUBLIC_RECORD_LABELS, "role")
        if kind in (CHANNELS_KIND, POSITIONING_TARGETS_KIND):
            return self._users("positioning", lambda block, fields: strip_note(fields.get(scope, "")) == wanted)
        if kind == CAPABILITY_CATEGORIES_KIND:
            return self._users("capabilities", lambda block, fields: block.heading.strip() == wanted)
        if kind == PACKAGE_HYPOTHESIS_STATES_KIND:
            return self._users("packages", lambda block, fields: strip_note(fields.get(state, "")) == wanted)
        if kind == PUBLIC_RECORD_KINDS_KIND:
            return self._users(PUBLIC_RECORDS_KEY, lambda block, fields: fields.get(record_kind, "").strip() == wanted)
        if kind == PUBLIC_RECORD_ROLES_KIND:
            return self._users(PUBLIC_RECORDS_KEY, lambda block, fields: fields.get(record_role, "").strip() == wanted)
        return []

    def presentation_directory(self, channel: str) -> str | None:
        """提示物の置き場に、媒体の語と同じ名前のディレクトリがあれば、その名前（提示物の置き場からの相対）を返す。

        提示物の置き場が起動の引数で渡されていなければ、提示物は 0 件なので None を返す。
        """
        root = self.settings.presentations_dir
        name = channel.strip()
        if root is None or not name:
            return None
        directory = root / name
        if directory.is_dir() and directory.resolve().parent == root.resolve():
            return name
        return None

    def _users(self, key: str, uses) -> list[str]:
        """その正本の読み方で選んだ節のうち、uses が真を返す節の見出しの道筋。"""
        if not self.settings.has_file(key):
            return []
        name = self.settings.files[key]
        paths = {item.start: item.heading_path for item in self.source_sections(name)}
        blocks, rule = self._blocks(key)
        found: list[str] = []
        for block in blocks:
            if uses(block, read_fields(block, rule)) and block.start in paths:
                if paths[block.start] not in found:
                    found.append(paths[block.start])
        return found

    # ------------------------------------------------------------ 書き戻す

    def append_capability(self, capability: Capability) -> None:
        """機能の台帳に 1 行足す。分類の節が無ければ、節ごと作って足す。"""
        path = self.settings.path_for("capabilities")
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = text.splitlines()

        row = self._capability_row(capability)
        target = None
        for section in self._blocks_in("capabilities", text):
            if section.heading == capability.category:
                target = section
                break

        if target is None:
            block = ["", f"## {capability.category}", "", *CAPABILITY_TABLE_HEADER, row]
            lines.extend(block)
        else:
            insert_at = target.end
            for index in range(target.start, target.end):
                if lines[index].strip().startswith("|"):
                    insert_at = index + 1
            if insert_at == target.end:
                # 表がまだ無い節なので、見出しごと表を作る。
                lines[insert_at:insert_at] = ["", *CAPABILITY_TABLE_HEADER, row]
            else:
                lines.insert(insert_at, row)

        path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")

    @staticmethod
    def _capability_row(capability: Capability) -> str:
        """機能 1 つを、台帳の表の 1 行にする。列の並びは表の見出しと同じ。"""

        def cell(value: str) -> str:
            # 縦棒は表の区切りなので、全角に置き換えて表を壊さないようにする。
            return value.replace("|", "｜").strip()

        evidence = f" {LIST_SEPARATOR} ".join(cell(item) for item in capability.evidence_sections)
        return (
            f"| {cell(capability.id)} | {cell(capability.name)} "
            f"| {cell(capability.description)} | {evidence} |"
        )

    def append_positioning(self, positioning: Positioning) -> None:
        """売り方の決めを 1 ブロック足す。過去のブロックは書き換えず、末尾に積む。

        積むだけにするのは、いつ何を前面に出していたかを後から辿れるようにするためである。
        どのブロックが効いているかは、読むときに日付で決める。
        """
        path = self.settings.path_for("positioning")
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = text.splitlines()
        lines.extend(["", *self._positioning_block(positioning)])
        path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")

    @classmethod
    def _positioning_block(cls, positioning: Positioning) -> list[str]:
        """決め 1 件を、正本のブロックの行にする。読み戻すのは _load_positionings である。

        欄の値に改行を含むとき（根拠が複数行になるときなど）は、同じラベルの行を複数回書く。
        read_fields が同じラベルの行を改行でつないで 1 つの値に戻すので、書き戻しで
        1 行に畳んでしまうと、読み直したときの値が書いた値と食い違う。
        """
        decided_on = positioning.decided_on.isoformat()
        lines = [f"## {decided_on} {positioning.scope}", ""]
        for label, name in POSITIONING_LABELS.items():
            value = getattr(positioning, name)
            lines.extend(f"- {label}: {line}" for line in cls._as_lines(value))

        exceptions = [
            cls._exception_line(entry) for entry in positioning.exceptions
        ]
        exceptions = [line for line in exceptions if line]
        if not exceptions:
            exceptions = [EMPTY_MARK]
        lines.extend(f"- {POSITIONING_EXCEPTIONS_LABEL}: {line}" for line in exceptions)
        return lines

    @staticmethod
    def _exception_line(entry: dict[str, str]) -> str:
        """例外 1 件を「提示物 — 理由」の 1 行にする。理由が無ければ提示物だけを書く。"""
        presentation = str(entry.get(EXCEPTION_PRESENTATION_KEY, "")).strip()
        reason = str(entry.get(EXCEPTION_REASON_KEY, "")).strip()
        if not presentation:
            return ""
        if not reason:
            return presentation
        return f"{presentation} {EXCEPTION_SEPARATOR} {reason}"

    def append_public_record(self, record: PublicRecord) -> None:
        """公開記録を 1 ブロック足す。過去のブロックは書き換えず、末尾に積む。

        積むだけにするのは、決めの正本と同じく、いつ何を公開したかを後から辿れるようにするため
        である。値の無い任意の欄も「なし」の 1 行で書く。行ごと落とすと、手で書き足す人が
        欄の並びを写せなくなるからである。
        """
        path = self.settings.path_for(PUBLIC_RECORDS_KEY)
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = text.splitlines()
        lines.extend(["", *self._public_record_block(record)])
        path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")

    @classmethod
    def _public_record_block(cls, record: PublicRecord) -> list[str]:
        """公開記録 1 件を、正本のブロックの行にする。読み戻すのは _load_public_records である。"""
        lines = [f"## {record.name}", ""]
        for label, name in PUBLIC_RECORD_LABELS.items():
            value = getattr(record, name)
            if value is None or value == "":
                lines.append(f"- {label}: {EMPTY_MARK}")
                continue
            lines.append(f"- {label}: {cls._as_text(value)}")
        return lines

    def write_package(self, package: Package) -> None:
        """パッケージ定義の 1 節を書き換える。その名前の節が無ければ、末尾に足す。

        決めと違って積まないのは、パッケージがいまの売り物の定義 1 つだからである。
        いつ何を売っていたかは決めの正本の側が持つ。
        """
        path = self.settings.path_for("packages")
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = text.splitlines()
        block = self._package_block(package)

        target = next(
            (
                section
                for section in self._blocks_in("packages", text)
                if section.heading == package.name
            ),
            None,
        )
        if target is None:
            lines.extend(["", *block])
        else:
            lines[target.start : target.end] = [*block, ""]

        path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")

    @classmethod
    def _package_block(cls, package: Package) -> list[str]:
        """パッケージ 1 つを、正本の節の行にする。値の無い任意の欄は行ごと書かない。"""
        lines = [f"## {package.name}", ""]
        for label, name in PACKAGE_LABELS.items():
            value = getattr(package, name)
            if value is None or value == "":
                continue
            lines.append(f"- {label}: {cls._as_text(value)}")

        bundled = f" {LIST_SEPARATOR} ".join(package.capabilities)
        lines.append(f"- {PACKAGE_CAPABILITIES_LABEL}: {bundled or EMPTY_MARK}")
        return lines

    @staticmethod
    def _as_text(value: object) -> str:
        """欄の値を、正本に書く 1 行の文字列にする。日付は 2026-09-16 の形で書く。

        1 欄 1 行の書き方なので、値の中の改行は空白に畳む。畳まないと、2 行目以降が
        欄の付いていない行になり、読み戻したときに落ちる。
        """
        if isinstance(value, date):
            return value.isoformat()
        return " ".join(str(value).split())

    @staticmethod
    def _as_lines(value: object) -> list[str]:
        """欄の値を、正本に書く行の一覧にする（改行を含む値は複数行になる）。

        値に改行が無ければ、_as_text と同じ 1 行を 1 件だけ返す。改行があるときは、行ごとに
        別の「- ラベル: 行」として書けるように、行の一覧のまま返す（畳んで 1 行にはしない）。
        1 行の中の余分な空白は、_as_text と同じ規則でそろえる。
        """
        if isinstance(value, date):
            return [value.isoformat()]
        text = str(value)
        if "\n" not in text:
            return [" ".join(text.split())]
        return [" ".join(line.split()) for line in text.splitlines()]


def _vocabulary_section(lines: list[str], kind: str) -> tuple[int | None, int]:
    """語彙のファイルの行から、その種類の節の見出しの行の位置と、節の終わり（次の見出しの行の位置）を返す。"""
    start: int | None = None
    for index, line in enumerate(lines):
        heading = HEADING_RE.match(line.strip())
        if heading is None:
            continue
        if start is not None:
            return start, index
        if len(heading.group(1)) == 2 and heading.group(2) == kind:
            start = index
    return start, len(lines)


def _label_of(labels: dict[str, str], name: str) -> str:
    """正本の欄のラベルと型の欄の名前の対応から、型の欄の名前に当たるラベルを返す。"""
    return next(label for label, value in labels.items() if value == name)

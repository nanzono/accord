"""正本の Markdown を読み、型の集合として渡し、承認された変更だけを書き戻す。

Markdown の在処と書き方を知るのはこの文書だけである。上の層（サービスと皮）は、
ファイル名も見出しの形も知らずに、型の集合だけを見て判断する。
保管の形式を差し替えるときに直すのはここに閉じる、という分け方である。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from accord.models.ontology import missing_required_fields
from accord.models.results import (
    PresentationUrl,
    SkippedHeading,
    SourceDefect,
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
    bullet_items,
    drop_field_lines,
    find_section,
    find_urls,
    leading_number,
    read_fields,
    select_blocks,
    split_sections,
    strip_note,
    table_blocks,
)
from accord.vocabulary.settings import (
    CHANNEL_RULES_PER_CHANNEL_FILE,
    PHRASES_FROM_TABLE,
    PRESENTATION_RULES_KEY,
    PUBLIC_RECORDS_KEY,
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
    "畳み行": "fold_line",
}
PRESENTATION_LABELS = {
    "宛先の媒体": "channel",
    "宣言する束": "declared_package",
    "作成日": "created_on",
}
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

# ID の欄のラベル。設定の [reading.labels] で別の語に読み替えられる。
ID_LABEL = "ID"

# 媒体ごとの規約のファイルの場所に書く、媒体の名前が入るところの印。
CHANNEL_PLACEHOLDER = "{channel}"

# 裏づけの節と出典の節が指せる正本。どちらも節の見出しで指す。
EVIDENCE_SOURCE_KEYS = ("career", "engagements")

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


def _skip_reasons(section: Section, above: list[str], rule: BlockRule) -> list[str]:
    """その節が、読み方のどの絞りに当たって外れたかを並べる。1 つも当たらなければ空の一覧。

    絞りは select_blocks の 5 つと同じで、判定の順も同じである。当たったものを全部返すのは、
    設定のどの鍵を広げれば読めるようになるかを、理由の文だけで言い切るためである。
    """
    reasons: list[str] = []
    if section.level not in set(rule.heading_levels):
        levels = " / ".join(str(item) for item in rule.heading_levels)
        reasons.append(f"深さ {section.level} が heading_levels（{levels}）に無い")
    if rule.under_headings and not any(name in rule.under_headings for name in above):
        parents = "、".join(above) if above else "上位の見出しなし"
        wanted = " / ".join(rule.under_headings)
        reasons.append(f"上位の見出し（{parents}）に under_headings（{wanted}）の名前が無い")
    skipped = [name for name in (section.heading, *above) if name in rule.skip_headings]
    if skipped:
        reasons.append(f"skip_headings に挙げた見出し（{' / '.join(skipped)}）の中にある")
    if rule.heading_prefix and not section.heading.startswith(rule.heading_prefix):
        reasons.append(f"heading_prefix「{rule.heading_prefix}」で始まっていない")
    if rule.skip_sections_without_fields and not read_fields(section, rule):
        reasons.append("欄を 1 つも持たないので、束ねるための見出しとして読み飛ばしている")
    return reasons


def _optional(value: str | None) -> str | None:
    """空を表す語を None にそろえる。"""
    if value is None or value.strip() in EMPTY_WORDS:
        return None
    return value.strip()


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
        """正本 1 種の読み方を返す。設定に書き方の節が無ければ、第 1 版と同じ読み方になる。"""
        return self.settings.reading.rule_for(key)

    def _blocks(self, key: str) -> tuple[list[Section], BlockRule]:
        """正本 1 種を読み、その正本の読み方で選んだ節と、読み方そのものを返す。

        職歴の枠と受託案件のように、1 つのファイルを 2 種の正本として読むこともある。
        設定の `[source.files]` に同じファイル名を書き、見出しの深さで分ける。
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
        )

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
            result.append(Positioning(**values))
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
            result.append(Package(**values))
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
                result.append(Capability(**values))
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
            result.append(CareerFrame(**values))
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
            result.append(Engagement(**values))
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
            result.append(PublicRecord(**values))
        return result, defects

    def _load_ledger_entries(self) -> tuple[list[ResumeLedger], list[SourceDefect]]:
        """職務経歴書の台帳を、案件 1 件 1 ブロックで読む。

        必須の欄が欠けたブロックは型にできないので、飛ばしたことを断りに残す。
        """
        result: list[ResumeLedger] = []
        defects: list[SourceDefect] = []
        blocks, rule = self._blocks("resume_ledger")
        for block in blocks:
            fields = read_fields(block, rule)
            values: dict[str, object] = {
                name: fields.get(label) for label, name in LEDGER_LABELS.items()
            }
            values["heading"] = block.heading
            values["fold_line"] = _optional(values.get("fold_line"))
            if rule.entry_number_from_heading:
                # 案件番号を欄ではなく見出しの数字で持つ書き方。欄があればそちらを優先しない。
                number = leading_number(block.heading, rule.heading_prefix)
                if number:
                    values["entry_number"] = number

            missing = missing_required_fields(RESUME_LEDGER_TYPE_NAME, SimpleNamespace(**values))
            if missing:
                defects.append(
                    SourceDefect(
                        file=self.settings.files["resume_ledger"],
                        location=f"「{block.heading}」のブロック",
                        missing_fields=[field.label for field in missing],
                        source_key="resume_ledger",
                        heading=block.heading,
                    )
                )
                continue
            result.append(ResumeLedger(**values))
        return result, defects

    def _presentation_files(self) -> list[Path]:
        """提示物として読む Markdown を集める。

        置き場の一覧が設定にあれば、その一覧のディレクトリの下だけをたどる。無ければ、
        設定が提示物として指したディレクトリの下を全部たどる（第 1 版と同じ）。
        媒体ディレクトリの下に、提示物でないファイルが同居している正本があるためである。
        """
        names = self.settings.reading.presentation_directories
        roots = (
            [self.settings.source_dir / name for name in names]
            if names
            else [self.settings.path_for("presentations")]
        )
        found: list[Path] = []
        for root in roots:
            if root.is_dir():
                found.extend(sorted(root.rglob("*.md")))
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
            relative = path.relative_to(self.settings.source_dir).as_posix()
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
            values["pending_notes"] = [
                note
                for note in fields.get("未反映の注記", "").splitlines()
                if note.strip() and note.strip() not in EMPTY_WORDS
            ]
            result.append(Presentation(**values))
            urls.extend(self._presentation_urls(relative, text))
        return result, urls, defects

    @staticmethod
    def _presentation_urls(relative: str, text: str) -> list[PresentationUrl]:
        """提示物 1 枚の本文から URL を拾う。正規化して同じになるものは 1 件に落とす。"""
        found: list[PresentationUrl] = []
        seen: set[str] = set()
        for url in find_urls(text):
            normalized = normalize_url(url)
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
                identifier = read_fields(section, rule).get(ID_LABEL, "").strip()
                if identifier:
                    bodies.setdefault(
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
            path = self.settings.source_dir / rules.channel_rules_file.replace(
                CHANNEL_PLACEHOLDER, channel
            )
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

"""正本の Markdown を読み、型の集合として渡し、承認された変更だけを書き戻す。

Markdown の在処と書き方を知るのはこの文書だけである。上の層（サービスと皮）は、
ファイル名も見出しの形も知らずに、型の集合だけを見て判断する。
保管の形式を差し替えるときに直すのはここに閉じる、という分け方である。
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from accord.models.ontology import missing_required_fields
from accord.models.results import SourceDefect, SourceSnapshot
from accord.models.types import (
    Capability,
    CareerFrame,
    Engagement,
    Package,
    Positioning,
    Presentation,
    ResumeLedger,
)
from accord.repository.sections import (
    Section,
    bullet_items,
    find_section,
    parse_definition_list,
    split_sections,
)
from accord.vocabulary.settings import PRESENTATION_RULES_KEY, Settings

# 正本の欄の見出し（Markdown 側のラベル）と、型の欄の名前の対応。
POSITIONING_LABELS = {
    "日付": "decided_on",
    "適用範囲": "scope",
    "前面に出す束": "headline_package",
    "根拠": "rationale",
}
# 並びは、書き戻すときの行の並びでもある（読むときは並びを見ない）。
PACKAGE_LABELS = {
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

# 一覧の欄を 1 行に書くときの区切り。
LIST_SEPARATOR = "/"

# 例外の欄で、提示物の名前と理由を分ける印。
EXCEPTION_SEPARATOR = "—"

# 値が空であることを表す語。「未反映の注記: なし」のように書ける。
EMPTY_WORDS = {"", "なし", "無し", "-", "—"}

# 空の欄を書き戻すときに使う語。読むときは上の一覧のどれでも空として扱う。
EMPTY_MARK = "なし"

# 機能の台帳の表の見出し。節を新しく作るときに書き出す。
CAPABILITY_TABLE_HEADER = ("| 機能名 | 説明 | 裏づけの節 |", "|---|---|---|")

# 見せ方の正本の、媒体によらない節の見出し。媒体ごとの節の見出しは、媒体の名前そのものである。
FORBIDDEN_PHRASES_HEADING = "禁じた言い回し"

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


def _optional(value: str | None) -> str | None:
    """空を表す語を None にそろえる。"""
    if value is None or value.strip() in EMPTY_WORDS:
        return None
    return value.strip()


def _blocks(sections: list[Section], level: int = 2) -> list[Section]:
    """指定した深さの見出しを持つ節だけを取り出す。"""
    return [section for section in sections if section.level == level and section.heading]


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

    def load(self) -> SourceSnapshot:
        """7 種の正本を読み、型のインスタンスの集合にする。

        必須の欄が欠けたブロックや節は型にできないので集合には入らないが、飛ばしたこと自体を
        defects に載せて渡す。黙って飛ばすと、1 つ前か隣のブロックが「いまの正本」として
        通ってしまい、読んだ側が逆向きの直し先を受け取る。
        """
        positionings, positioning_defects = self._load_positionings()
        packages, package_defects = self._load_packages()
        capabilities, capability_defects = self._load_capabilities()
        career_frames, career_defects = self._load_career_frames()
        engagements, engagement_defects = self._load_engagements()
        presentations, presentation_defects = self._load_presentations()
        ledger_entries, ledger_defects = self._load_ledger_entries()
        return SourceSnapshot(
            positionings=positionings,
            packages=packages,
            capabilities=capabilities,
            career_frames=career_frames,
            engagements=engagements,
            presentations=presentations,
            ledger_entries=ledger_entries,
            defects=[
                *positioning_defects,
                *package_defects,
                *capability_defects,
                *career_defects,
                *engagement_defects,
                *presentation_defects,
                *ledger_defects,
            ],
        )

    def _load_positionings(self) -> tuple[list[Positioning], list[SourceDefect]]:
        """売り方の決めを、1 決め 1 ブロックで読む。

        欄が欠けたブロックは決めとして読めないので、読めなかったことと欠けた欄の名前を
        2 つ目の返り値に入れる。どちらを返すかではなく、両方を返すのがこの関数の仕事である。
        """
        result: list[Positioning] = []
        defects: list[SourceDefect] = []
        for block in _blocks(split_sections(self._read("positioning"))):
            fields = parse_definition_list(block.body)
            missing = [label for label in POSITIONING_LABELS if label not in fields]
            if missing:
                defects.append(
                    SourceDefect(
                        file=self.settings.files["positioning"],
                        location=f"「{block.heading}」のブロック",
                        missing_fields=missing,
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
        for block in _blocks(split_sections(self._read("packages"))):
            fields = parse_definition_list(block.body)
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
                    )
                )
                continue

            for optional_name in ("basis", "source", "breaks_when"):
                values[optional_name] = _optional(values.get(optional_name))
            result.append(Package(**values))
        return result, defects

    def _load_capabilities(self) -> tuple[list[Capability], list[SourceDefect]]:
        """機能の台帳を読む。節の見出しが分類、表の 1 行が機能 1 つ。

        必須の欄が欠けた行（列が足りない、値が空）は型にできないので、飛ばしたことを断りに残す。
        """
        result: list[Capability] = []
        defects: list[SourceDefect] = []
        for block in _blocks(split_sections(self._read("capabilities"))):
            for index, cells in enumerate(self._table_rows(block.body), start=1):
                values = {
                    "name": cells[0] if len(cells) > 0 else None,
                    "description": cells[1] if len(cells) > 1 else None,
                    "category": block.heading,
                    "evidence_sections": _split_list(cells[2]) if len(cells) > 2 else [],
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
                        )
                    )
                    continue
                result.append(Capability(**values))
        return result, defects

    @staticmethod
    def _table_rows(body: str) -> list[list[str]]:
        """本文から表の行を拾う。見出しの行と区切りの行は落とす。"""
        rows: list[list[str]] = []
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
                continue
            rows.append(cells)
        # 先頭の行は表の見出しなので落とす。
        return rows[1:] if rows else rows

    def _load_career_frames(self) -> tuple[list[CareerFrame], list[SourceDefect]]:
        """職歴の枠を読む。必須の欄が欠けたブロックは型にできないので、飛ばしたことを断りに残す。"""
        result: list[CareerFrame] = []
        defects: list[SourceDefect] = []
        for block in _blocks(split_sections(self._read("career"))):
            fields = parse_definition_list(block.body)
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
                    )
                )
                continue
            result.append(CareerFrame(**values))
        return result, defects

    def _load_engagements(self) -> tuple[list[Engagement], list[SourceDefect]]:
        """受託案件を読む。必須の欄が欠けたブロックは型にできないので、飛ばしたことを断りに残す。"""
        result: list[Engagement] = []
        defects: list[SourceDefect] = []
        for block in _blocks(split_sections(self._read("engagements"))):
            fields = parse_definition_list(block.body)
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
                    )
                )
                continue
            result.append(Engagement(**values))
        return result, defects

    def _load_ledger_entries(self) -> tuple[list[ResumeLedger], list[SourceDefect]]:
        """職務経歴書の台帳を、案件 1 件 1 ブロックで読む。

        必須の欄が欠けたブロックは型にできないので、飛ばしたことを断りに残す。
        """
        result: list[ResumeLedger] = []
        defects: list[SourceDefect] = []
        for block in _blocks(split_sections(self._read("resume_ledger"))):
            fields = parse_definition_list(block.body)
            values: dict[str, object] = {
                name: fields.get(label) for label, name in LEDGER_LABELS.items()
            }
            values["heading"] = block.heading
            values["fold_line"] = _optional(values.get("fold_line"))

            missing = missing_required_fields(RESUME_LEDGER_TYPE_NAME, SimpleNamespace(**values))
            if missing:
                defects.append(
                    SourceDefect(
                        file=self.settings.files["resume_ledger"],
                        location=f"「{block.heading}」のブロック",
                        missing_fields=[field.label for field in missing],
                    )
                )
                continue
            result.append(ResumeLedger(**values))
        return result, defects

    def _load_presentations(self) -> tuple[list[Presentation], list[SourceDefect]]:
        """提示物を読む。媒体ごとのディレクトリの下の Markdown が 1 件ずつ。

        必須の欄（宛先の媒体・宣言する束）が欠けたファイルは型にできないので、飛ばしたことを断りに残す。
        """
        directory = self.settings.path_for("presentations")
        if not directory.is_dir():
            return [], []

        result: list[Presentation] = []
        defects: list[SourceDefect] = []
        for path in sorted(directory.rglob("*.md")):
            fields = parse_definition_list(path.read_text(encoding="utf-8"))
            relative = path.relative_to(self.settings.source_dir).as_posix()
            values: dict[str, object] = {
                name: fields.get(label) for label, name in PRESENTATION_LABELS.items()
            }
            values["path"] = relative

            missing = missing_required_fields(PRESENTATION_TYPE_NAME, SimpleNamespace(**values))
            if missing:
                defects.append(
                    SourceDefect(
                        file=relative,
                        location="先頭の欄",
                        missing_fields=[field.label for field in missing],
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
        return result, defects

    def evidence_bodies(self) -> dict[str, str]:
        """裏づけの節として指せる見出しと、その本文の対応を返す。

        型に射影した欄ではなく本文をそのまま渡すのは、文面を書く側が読むのは節の中身だからである。
        同じ見出しが 2 つの正本にあるときは、先に読んだほう（職歴の枠）を残す。
        """
        bodies: dict[str, str] = {}
        for key in EVIDENCE_SOURCE_KEYS:
            for section in _blocks(split_sections(self._read(key))):
                bodies.setdefault(section.heading, section.body)
        return bodies

    def _presentation_rule_sections(self) -> list[Section]:
        """見せ方の正本を節に切り分ける。ファイルが無ければ空の一覧を返す。"""
        return _blocks(split_sections(self._read(PRESENTATION_RULES_KEY)))

    def channel_rules(self, channel: str) -> list[str]:
        """見せ方の正本のうち、その媒体の節の箇条書きを返す。

        媒体の規約（文字数の上限、書き出しの決まり）と、その媒体での見せ方の決めが、
        1 つの節に並ぶ。節が無ければ空の一覧を返す。
        """
        section = find_section(self._presentation_rule_sections(), channel)
        return bullet_items(section.body) if section is not None else []

    def forbidden_phrases(self) -> list[str]:
        """見せ方の正本の、媒体によらない節から、禁じた言い回しを返す。"""
        section = find_section(self._presentation_rule_sections(), FORBIDDEN_PHRASES_HEADING)
        return bullet_items(section.body) if section is not None else []

    # ------------------------------------------------------------ 書き戻す

    def append_capability(self, capability: Capability) -> None:
        """機能の台帳に 1 行足す。分類の節が無ければ、節ごと作って足す。"""
        path = self.settings.path_for("capabilities")
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = text.splitlines()

        row = self._capability_row(capability)
        target = None
        for section in _blocks(split_sections(text)):
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
        """機能 1 つを、台帳の表の 1 行にする。"""

        def cell(value: str) -> str:
            # 縦棒は表の区切りなので、全角に置き換えて表を壊さないようにする。
            return value.replace("|", "｜").strip()

        evidence = f" {LIST_SEPARATOR} ".join(cell(item) for item in capability.evidence_sections)
        return f"| {cell(capability.name)} | {cell(capability.description)} | {evidence} |"

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
        parse_definition_list が同じラベルの行を改行でつないで 1 つの値に戻すので、書き戻しで
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
                for section in _blocks(split_sections(text))
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

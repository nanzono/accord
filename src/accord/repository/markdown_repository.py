"""正本の Markdown を読み、型の集合として渡し、承認された変更だけを書き戻す。

Markdown の在処と書き方を知るのはこの文書だけである。上の層（サービスと皮）は、
ファイル名も見出しの形も知らずに、型の集合だけを見て判断する。
保管の形式を差し替えるときに直すのはここに閉じる、という分け方である。
"""

from __future__ import annotations

from pathlib import Path

from accord.models.results import SourceSnapshot
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
    parse_definition_list,
    split_sections,
)
from accord.vocabulary.settings import Settings

# 正本の欄の見出し（Markdown 側のラベル）と、型の欄の名前の対応。
POSITIONING_LABELS = {
    "日付": "decided_on",
    "適用範囲": "scope",
    "前面に出す束": "headline_package",
    "根拠": "rationale",
}
PACKAGE_LABELS = {
    "想定買い手": "buyer",
    "仮説の状態": "hypothesis_state",
    "最終更新": "updated_on",
    "判定根拠": "basis",
    "出典": "source",
    "崩れる条件": "breaks_when",
}
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

# 機能の台帳の表の見出し。節を新しく作るときに書き出す。
CAPABILITY_TABLE_HEADER = ("| 機能名 | 説明 | 裏づけの節 |", "|---|---|---|")


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
        """7 種の正本を読み、型のインスタンスの集合にする。"""
        return SourceSnapshot(
            positionings=self._load_positionings(),
            packages=self._load_packages(),
            capabilities=self._load_capabilities(),
            career_frames=self._load_career_frames(),
            engagements=self._load_engagements(),
            presentations=self._load_presentations(),
            ledger_entries=self._load_ledger_entries(),
        )

    def _load_positionings(self) -> list[Positioning]:
        """売り方の決めを、1 決め 1 ブロックで読む。"""
        result: list[Positioning] = []
        for block in _blocks(split_sections(self._read("positioning"))):
            fields = parse_definition_list(block.body)
            if not all(label in fields for label in POSITIONING_LABELS):
                continue
            values = {name: fields[label] for label, name in POSITIONING_LABELS.items()}
            values["exceptions"] = self._parse_exceptions(fields.get("例外", ""))
            result.append(Positioning(**values))
        return result

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
            exceptions.append({"提示物": presentation.strip(), "理由": reason.strip()})
        return exceptions

    def _load_packages(self) -> list[Package]:
        """パッケージ定義を読む。"""
        result: list[Package] = []
        for block in _blocks(split_sections(self._read("packages"))):
            fields = parse_definition_list(block.body)
            values = {
                name: fields[label] for label, name in PACKAGE_LABELS.items() if label in fields
            }
            for optional_name in ("basis", "source", "breaks_when"):
                values[optional_name] = _optional(values.get(optional_name))
            values["name"] = block.heading
            values["capabilities"] = _split_list(fields.get("束ねる機能", ""))
            if "buyer" not in values or "updated_on" not in values:
                continue
            result.append(Package(**values))
        return result

    def _load_capabilities(self) -> list[Capability]:
        """機能の台帳を読む。節の見出しが分類、表の 1 行が機能 1 つ。"""
        result: list[Capability] = []
        for block in _blocks(split_sections(self._read("capabilities"))):
            for cells in self._table_rows(block.body):
                if len(cells) < 3:
                    continue
                result.append(
                    Capability(
                        name=cells[0],
                        description=cells[1],
                        category=block.heading,
                        evidence_sections=_split_list(cells[2]),
                    )
                )
        return result

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

    def _load_career_frames(self) -> list[CareerFrame]:
        """職歴の枠を読む。"""
        result: list[CareerFrame] = []
        for block in _blocks(split_sections(self._read("career"))):
            fields = parse_definition_list(block.body)
            values = {
                name: fields[label] for label, name in CAREER_LABELS.items() if label in fields
            }
            values["heading"] = block.heading
            if not {"period", "organization", "position", "disclosure", "source"} <= values.keys():
                continue
            result.append(CareerFrame(**values))
        return result

    def _load_engagements(self) -> list[Engagement]:
        """受託案件を読む。"""
        result: list[Engagement] = []
        for block in _blocks(split_sections(self._read("engagements"))):
            fields = parse_definition_list(block.body)
            values = {
                name: fields[label] for label, name in ENGAGEMENT_LABELS.items() if label in fields
            }
            values["heading"] = block.heading
            if not {"disclosure", "source"} <= values.keys():
                continue
            result.append(Engagement(**values))
        return result

    def _load_ledger_entries(self) -> list[ResumeLedger]:
        """職務経歴書の台帳を、案件 1 件 1 ブロックで読む。"""
        result: list[ResumeLedger] = []
        for block in _blocks(split_sections(self._read("resume_ledger"))):
            fields = parse_definition_list(block.body)
            values = {
                name: fields[label] for label, name in LEDGER_LABELS.items() if label in fields
            }
            values["heading"] = block.heading
            values["fold_line"] = _optional(values.get("fold_line"))
            required = {
                "entry_number",
                "period",
                "scale",
                "process",
                "role",
                "decisions",
                "closing",
                "source_section",
            }
            if not required <= values.keys():
                continue
            result.append(ResumeLedger(**values))
        return result

    def _load_presentations(self) -> list[Presentation]:
        """提示物を読む。媒体ごとのディレクトリの下の Markdown が 1 件ずつ。"""
        directory = self.settings.path_for("presentations")
        if not directory.is_dir():
            return []

        result: list[Presentation] = []
        for path in sorted(directory.rglob("*.md")):
            fields = parse_definition_list(path.read_text(encoding="utf-8"))
            values = {
                name: fields[label]
                for label, name in PRESENTATION_LABELS.items()
                if label in fields
            }
            if "channel" not in values or "declared_package" not in values:
                continue
            values["created_on"] = _optional(values.get("created_on"))
            values["path"] = path.relative_to(self.settings.source_dir).as_posix()
            values["pending_notes"] = [
                note
                for note in fields.get("未反映の注記", "").splitlines()
                if note.strip() and note.strip() not in EMPTY_WORDS
            ]
            result.append(Presentation(**values))
        return result

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
        """売り方の決めを 1 ブロック足す（書きの操作 3 つの段で実装する）。"""
        raise NotImplementedError("決めの書き戻しは書きの操作 3 つの段で実装する")

    def write_package(self, package: Package) -> None:
        """パッケージ定義の 1 節を書き換える（書きの操作 3 つの段で実装する）。"""
        raise NotImplementedError("パッケージの書き戻しは書きの操作 3 つの段で実装する")

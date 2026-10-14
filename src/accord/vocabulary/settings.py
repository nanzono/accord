"""正本の置き場と語彙を読み、accord の形（正本の書き方）を持つ。

accord の形は 1 つで、この文書の定数が持つ。正本のファイルの名前と置き場、見出しの深さ、欄の書き方、
欄のラベルの読み替え、読み飛ばす節、媒体ごとの規約のファイル、禁じた言い回しの表の読み方を固定し、
読み方を変える設定も引数も受けない。違う書き方の正本を持つ人は、移行の操作で accord の形に変換する。
形の全体と、形を決める名前の一覧は、公開側の文書 `docs/data-format.md` 1 か所に書く。

置き場（経歴データの git の作業ツリーの根）と提示物の置き場は、起動の引数で受ける。語彙（媒体の名前、
機能の分類など 6 種）は、置き場の中の vocabulary.md から読む。語彙をコードに直書きしないのは、語彙が
使う人のデータで、accord の操作で変えるものだからである。

この文書は標準ライブラリだけで動かし、型の定義を読み込まない。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field, replace
from pathlib import Path

# 正本のファイルの役割の名前。型 8 つに 1 対 1 で対応する。
SOURCE_KEYS = (
    "positioning",
    "packages",
    "capabilities",
    "career",
    "engagements",
    "resume_ledger",
    "presentations",
    "public_records",
)

# 公開記録の正本の役割の名前。
PUBLIC_RECORDS_KEY = "public_records"

# 見せ方の正本の役割の名前。
# 見せ方（媒体の規約・語り口の決め・禁じた言い回し）は accord の境界の外なので、型には持たない。
# 持つのは置き場だけで、材料の取り出しが、宛先の媒体の規約と禁じた言い回しの節をそのまま渡す。
PRESENTATION_RULES_KEY = "presentation_rules"

# 職務経歴書の台帳の正本の役割の名前。
RESUME_LEDGER_KEY = "resume_ledger"

# 正本の役割の全体。正本 8 種に、見せ方の正本を 1 つ足したもの。
FILE_KEYS = (*SOURCE_KEYS, PRESENTATION_RULES_KEY)

# 媒体の規約の置き場の書き方。1 つのファイルの媒体名の節から読むか、媒体ごとのファイルから読むか。
CHANNEL_RULES_ONE_FILE = "one_file"
CHANNEL_RULES_PER_CHANNEL_FILE = "per_channel_file"

# 禁じた言い回しの節の中身の読み方。箇条書きから読むか、節の最初の表の 1 列目から読むか。
PHRASES_FROM_BULLETS = "bullets"
PHRASES_FROM_TABLE = "table"

# ------------------------------------------------------------------ accord の形を決める名前
# ここから「accord の形を決める名前」の終わりまでの文字列の定数（正本の役割の名前を除く）は、
# docs/data-format.md の「形を決める名前」の一覧と同じでなければならない（tests/test_reading_settings.py が
# 突き合わせる）。これ以外の見出しや値は利用者のデータの中身で、コードにも公開側の文書にも書かない。

# 置き場の中の正本のファイルの名前と置き場。職歴の枠と受託案件は 1 つのファイルに同居する。
# 提示物だけはディレクトリで、提示物の置き場（起動の引数 --presentations）そのものを指す。
# spec: REQ-505
FORM_FILES = {
    "positioning": "product/positioning.md",
    "packages": "product/packages.md",
    "capabilities": "product/features.md",
    "career": "career_master.md",
    "engagements": "career_master.md",
    "resume_ledger": "keirekisho/daicho.md",
    "presentations": ".",
    "public_records": "public_records.md",
    "presentation_rules": "misekata_master.md",
}

# 語彙のファイルの名前と、その最上位の見出し。
VOCABULARY_FILE = "vocabulary.md"
VOCABULARY_TITLE = "語彙"

# 語彙の種類の名前（vocabulary.md の節の見出し）。
CHANNELS_KIND = "媒体"
POSITIONING_TARGETS_KIND = "決めの適用先"
CAPABILITY_CATEGORIES_KIND = "機能の分類"
PACKAGE_HYPOTHESIS_STATES_KIND = "パッケージの仮説の状態"
PUBLIC_RECORD_KINDS_KIND = "公開記録の種類"
PUBLIC_RECORD_ROLES_KIND = "公開記録の役割"

# 経歴の正本で、職歴の枠と受託案件を束ねる上位の見出し。この見出しの下だけを型として読む。
CAREER_SECTION_HEADING = "職歴・案件（新しい順）"

# 職務経歴書の台帳の見出しの前置き。案件の節と、在籍職歴の枠の節。
LEDGER_ENTRY_PREFIX = "案件"
LEDGER_FRAME_PREFIX = "枠"

# 職務経歴書の台帳で、箇条書きの記号を付けずに行頭に書く欄のラベル。
LEDGER_BARE_LABELS = ("畳み行",)

# 欄のラベルの読み替え。1 つのラベルを複数の欄に読み替えると、同じ値がその欄すべてに入る。
LABEL_ALIASES = {
    "期間 / 所属・立場": ("期間", "所属", "立場"),
    "業種・規模": ("業種", "規模"),
    "技術スタック": ("技術",),
    "課題・背景": ("課題",),
}

# パッケージ定義で、パッケージとして読む節を見分ける欄のラベル。型の正本（ontology.yaml）の
# パッケージの欄と同じで、このどれも持たない節はパッケージとして読まない（覚え書きの節など）。
PACKAGE_FIELD_LABELS = (
    "ID",
    "パッケージ名",
    "想定買い手",
    "仮説の状態",
    "束ねる機能",
    "最終更新",
    "判定根拠",
    "出典",
    "崩れる条件",
)

# 媒体ごとの規約のファイル。提示物の置き場から見た場所で、{channel} を媒体の名前に置き換える。
CHANNEL_RULES_FILE = "{channel}/channel.md"

# 見せ方の正本の中の、禁じた言い回しの節の見出し（末尾の括弧書きは見ない）。
FORBIDDEN_PHRASES_HEADING = "本人が禁じた言い回し"

# ------------------------------------------------------------------ accord の形を決める名前の終わり

# 語彙の種類の名前と、Settings の欄の名前の対応。並びは vocabulary.md の節の並び。
VOCABULARY_KINDS = (
    (CHANNELS_KIND, "channels"),
    (POSITIONING_TARGETS_KIND, "positioning_targets"),
    (CAPABILITY_CATEGORIES_KIND, "capability_categories"),
    (PACKAGE_HYPOTHESIS_STATES_KIND, "package_hypothesis_states"),
    (PUBLIC_RECORD_KINDS_KIND, "public_record_kinds"),
    (PUBLIC_RECORD_ROLES_KIND, "public_record_roles"),
)

# 移行の前の置き場が持つ設定ファイルの名前。移行の操作が読む（accord の形の外の名前）。
LEGACY_CONFIG_FILE = "accord.toml"


@dataclass(frozen=True)
class BlockRule:
    """正本 1 種の読み方。どの節をブロックとして読み、その節の欄をどう読むか。

    値は accord の形の定数（下の ACCORD_FORM）が決める。既定値は、何も絞らない読み方である。
    """

    # 節を選ぶ
    heading_levels: tuple[int, ...] = (2,)
    under_headings: tuple[str, ...] = ()
    heading_prefix: str = ""
    # 職務経歴書の台帳の、在籍職歴の枠の見出しの前置き。heading_prefix の絞りを通さない見出しでも、
    # この文字列で始まれば読む（heading_prefix の意味は変えない）。
    frame_heading_prefix: str = ""
    skip_sections_without_fields: bool = False
    # このラベルの欄を 1 つも持たない節を読まない（空なら絞らない）。
    skip_sections_without_labels: tuple[str, ...] = ()
    # 欄を読む
    fields_from_table: bool = False
    bare_labels: tuple[str, ...] = ()
    entry_number_from_heading: bool = False
    # 欄のラベルを読み替える（正本を問わず共通）
    strip_label_note: bool = False
    labels: dict[str, tuple[str, ...]] = field(default_factory=dict)


# 何も絞らない読み方。深さ 2 の見出しの節を 1 件ぶんとして読む。
DEFAULT_BLOCK_RULE = BlockRule()


@dataclass(frozen=True)
class ReadingRules:
    """accord の形のうち、正本ごとの読み方と、提示物・見せ方の正本の読み方。"""

    blocks: dict[str, BlockRule] = field(default_factory=dict)
    # 提示物を探すディレクトリ（提示物の置き場から見た名前）。語彙の媒体の名前と同じ並びになる。
    presentation_directories: tuple[str, ...] = ()
    require_presentation_declaration: bool = False
    # 見せ方の正本
    channel_rules_from: str = CHANNEL_RULES_ONE_FILE
    channel_rules_file: str = ""
    forbidden_phrases_heading: str = "禁じた言い回し"
    forbidden_phrases_any_level: bool = False
    forbidden_phrases_from: str = PHRASES_FROM_BULLETS

    def rule_for(self, key: str) -> BlockRule:
        """正本の役割の名前から、その正本の読み方を返す。"""
        return self.blocks.get(key, DEFAULT_BLOCK_RULE)


def _form_blocks() -> dict[str, BlockRule]:
    """accord の形の、正本ごとの読み方。欄のラベルの読み替えは、どの正本にも同じに当てる。"""
    common = BlockRule(strip_label_note=True, labels=dict(LABEL_ALIASES))
    blocks = {key: common for key in FILE_KEYS}
    # spec: REQ-506
    blocks["packages"] = replace(common, skip_sections_without_labels=PACKAGE_FIELD_LABELS)
    blocks["career"] = replace(
        common, heading_levels=(3,), under_headings=(CAREER_SECTION_HEADING,)
    )
    blocks["engagements"] = replace(
        common,
        heading_levels=(4, 5),
        under_headings=(CAREER_SECTION_HEADING,),
        skip_sections_without_fields=True,
    )
    blocks[RESUME_LEDGER_KEY] = replace(
        common,
        heading_prefix=LEDGER_ENTRY_PREFIX,
        frame_heading_prefix=LEDGER_FRAME_PREFIX,
        fields_from_table=True,
        bare_labels=LEDGER_BARE_LABELS,
        entry_number_from_heading=True,
    )
    return blocks


# accord の形。提示物を探すディレクトリは語彙の媒体で決まるので、読み込みのときに埋める。
ACCORD_FORM = ReadingRules(
    blocks=_form_blocks(),
    require_presentation_declaration=True,
    channel_rules_from=CHANNEL_RULES_PER_CHANNEL_FILE,
    channel_rules_file=CHANNEL_RULES_FILE,
    forbidden_phrases_heading=FORBIDDEN_PHRASES_HEADING,
    forbidden_phrases_any_level=True,
    forbidden_phrases_from=PHRASES_FROM_TABLE,
)


class SettingsError(ValueError):
    """起動の引数か置き場の中身が、accord を開ける状態でないこと。文は標準エラーにそのまま書く。"""


@dataclass(frozen=True)
class Settings:
    """起動時に決まる、正本の置き場と語彙と accord の形。"""

    source_dir: Path
    files: dict[str, str] = field(default_factory=lambda: dict(FORM_FILES))
    channels: list[str] = field(default_factory=list)
    # 媒体ではない決めの適用範囲の語。空なら、適用範囲は媒体の名前と「全体」だけになる。
    positioning_targets: list[str] = field(default_factory=list)
    capability_categories: list[str] = field(default_factory=list)
    package_hypothesis_states: list[str] = field(default_factory=list)
    public_record_kinds: list[str] = field(default_factory=list)
    public_record_roles: list[str] = field(default_factory=list)
    reading: ReadingRules = field(default_factory=lambda: ACCORD_FORM)
    # 提示物の置き場。起動の引数で渡さなければ None で、提示物を 0 件として読む。
    presentations_path: Path | None = None
    # 置き場に移行の前の設定ファイルがあり、語彙のファイルが無い（移行の操作を待つ）か。
    needs_migration: bool = False

    @property
    def presentations_dir(self) -> Path | None:
        """提示物のディレクトリと媒体ごとの規約のファイルを読む根。渡されていなければ None。"""
        # spec: REQ-504
        return self.presentations_path

    @property
    def vocabulary_path(self) -> Path:
        """語彙のファイルの場所。"""
        return self.source_dir / VOCABULARY_FILE

    def refresh_vocabulary(self) -> None:
        """置き場の vocabulary.md を読み直し、語彙とそれに従う読み方を、この設定の中で入れ替える。

        移行の操作が vocabulary.md を作った後、同じ設定を共有するサービスのどれもが、移行の後の
        語彙で判断するように、設定そのものを差し替えずに中身を入れ替える。
        """
        if not self.vocabulary_path.is_file():
            return
        vocabulary = parse_vocabulary(self.vocabulary_path.read_text(encoding="utf-8"))
        for kind, name in VOCABULARY_KINDS:
            getattr(self, name)[:] = vocabulary[kind]
        object.__setattr__(self, "needs_migration", False)
        object.__setattr__(
            self, "reading", replace(self.reading, presentation_directories=tuple(self.channels))
        )

    def vocabulary(self) -> dict[str, list[str]]:
        """語彙の種類の名前から、その種類の語の一覧への対応を、節の並びで返す。"""
        return {kind: list(getattr(self, name)) for kind, name in VOCABULARY_KINDS}

    def source_file_names(self) -> list[str]:
        """正本のファイルの名前を、FILE_KEYS の並びで返す。

        提示物（ディレクトリ）は入れない。同じファイルを 2 つの役割が指すときは 1 つに数える。
        """
        names: list[str] = []
        for key in FILE_KEYS:
            if key == "presentations" or key not in self.files:
                continue
            if self.files[key] not in names:
                names.append(self.files[key])
        return names

    def keys_for_file(self, name: str) -> list[str]:
        """ファイルの名前から、そのファイルを指す正本の役割の名前を並びの順で返す。"""
        return [
            key for key in FILE_KEYS if key != "presentations" and self.files.get(key) == name
        ]

    def has_file(self, key: str) -> bool:
        """その正本の役割が、accord の形に置き場を持つか。"""
        return key in self.files

    def path_for(self, key: str) -> Path:
        """正本の役割の名前から、実ファイル（提示物だけはディレクトリ）の場所を返す。"""
        if key not in self.files:
            raise KeyError(f"accord の形に正本 '{key}' の置き場が無い")
        if key == "presentations":
            if self.presentations_dir is None:
                raise KeyError("提示物の置き場が起動の引数で渡されていない")
            return self.presentations_dir / self.files[key]
        return self.source_dir / self.files[key]


# 起動の引数の書き方。置き場の指定が足りないとき、そのまま標準エラーに書く。
DATA_USAGE = (
    "置き場の指定の書き方: accord --data <経歴データの置き場（git の作業ツリーの根）>"
    " [--presentations <提示物と媒体ごとの規約の置き場>]"
)
PRESENTATIONS_USAGE = (
    "提示物の置き場の指定の書き方: --presentations <実在するディレクトリ>"
    "（省けば提示物を 0 件として読む）"
)


def _git_top_level(directory: Path) -> Path | None:
    """そのディレクトリを含む git の作業ツリーの根を返す。git の作業ツリーの中でなければ None。"""
    try:
        completed = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return Path(completed.stdout.strip()).resolve()


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
TERM_RE = re.compile(r"^[-*]\s+(.*?)\s*$")


def parse_vocabulary(text: str) -> dict[str, list[str]]:
    """vocabulary.md の本文を、語彙の種類の名前から語の一覧への対応にする。

    種類ごとの節（深さ 2 の見出し）に、語を「- 語」で 1 行ずつ書く。節の無い種類は語 0 件と読む。
    6 つの種類のどれでもない節があれば、書き方の誤りとして止める。
    """
    kinds = [kind for kind, _ in VOCABULARY_KINDS]
    result: dict[str, list[str]] = {kind: [] for kind in kinds}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        heading = HEADING_RE.match(line)
        if heading is not None:
            name = heading.group(2)
            if len(heading.group(1)) == 1:
                current = None
                continue
            if name not in result:
                raise SettingsError(
                    f"{VOCABULARY_FILE} に語彙の種類でない節「{name}」がある"
                    f"（語彙の種類: {'、'.join(kinds)}）"
                )
            current = name
            continue
        term = TERM_RE.match(line)
        if term is not None and current is not None and term.group(1):
            result[current].append(term.group(1))
    return result


def unbound_settings() -> Settings:
    """置き場を持たない設定。開く操作の名前を並べるだけの起動（--list）で使う。"""
    return Settings(source_dir=Path("."))


def load_settings(data: Path, presentations: Path | None = None) -> Settings:
    """起動の引数から、置き場と提示物の置き場を確かめ、語彙を読んだ設定を返す。

    accord の形は固定なので、ここで読むのは語彙だけである。
    """
    data_dir = Path(data).resolve()
    # spec: REQ-503
    if not data_dir.is_dir() or _git_top_level(data_dir) != data_dir:
        raise SettingsError(
            f"--data が git の作業ツリーの根を指していない（渡された値: {data}）。{DATA_USAGE}"
        )
    presentations_path: Path | None = None
    if presentations is not None:
        presentations_path = Path(presentations).resolve()
        # spec: REQ-545
        if not presentations_path.is_dir():
            raise SettingsError(
                f"--presentations が実在するディレクトリを指していない（渡された値: {presentations}）。"
                f"{PRESENTATIONS_USAGE}"
            )

    vocabulary_path = data_dir / VOCABULARY_FILE
    needs_migration = False
    # spec: REQ-502
    # spec: REQ-505
    if vocabulary_path.is_file():
        vocabulary = parse_vocabulary(vocabulary_path.read_text(encoding="utf-8"))
    elif (data_dir / LEGACY_CONFIG_FILE).is_file():
        # 移行の前の置き場。語彙は移行の操作が作るまで空のまま読む。
        vocabulary = {kind: [] for kind, _ in VOCABULARY_KINDS}
        needs_migration = True
    else:
        # spec: REQ-546
        raise SettingsError(
            f"置き場に {VOCABULARY_FILE} が無い。accord は語彙（媒体・決めの適用先・機能の分類・"
            f"パッケージの仮説の状態・公開記録の種類・公開記録の役割）を置き場の {VOCABULARY_FILE} から読む。"
            f"種類ごとの節「## 種類の名前」に、語を「- 語」で 1 行ずつ書く。"
        )

    values = {name: vocabulary[kind] for kind, name in VOCABULARY_KINDS}
    # spec: REQ-506
    reading = replace(ACCORD_FORM, presentation_directories=tuple(values["channels"]))
    return Settings(
        source_dir=data_dir,
        reading=reading,
        presentations_path=presentations_path,
        needs_migration=needs_migration,
        **values,
    )


# ------------------------------------------------------------------ 移行の前の設定ファイルと accord の形の突き合わせ
# ここから下の名前は、移行の前の設定ファイルの鍵の名前で、accord の形を決める名前ではない。
# 移行の操作だけが使う。

# 移行の前の設定ファイルの、語彙の節の鍵と、語彙の種類の名前の対応。
LEGACY_VOCABULARY_KEYS = {
    "channels": CHANNELS_KIND,
    "positioning_targets": POSITIONING_TARGETS_KIND,
    "capability_categories": CAPABILITY_CATEGORIES_KIND,
    "package_hypothesis_states": PACKAGE_HYPOTHESIS_STATES_KIND,
    "public_record_kinds": PUBLIC_RECORD_KINDS_KIND,
    "public_record_roles": PUBLIC_RECORD_ROLES_KIND,
}

# 移行の前の設定ファイルで、パッケージ定義の読み飛ばす見出しを書いた鍵の道。
LEGACY_PACKAGE_SKIP_KEY = "reading.packages.skip_headings"

# 移行の前の設定ファイルの、正本 1 種の読み方の鍵と、書かなかったときの値。
_LEGACY_BLOCK_DEFAULTS = {
    "heading_levels": [2],
    "under_headings": [],
    "heading_prefix": "",
    "skip_headings": [],
    "skip_sections_without_fields": False,
    "fields_from_table": False,
    "bare_labels": [],
    "entry_number_from_heading": False,
}
# 職務経歴書の台帳の節にだけ書けた鍵。
_LEGACY_LEDGER_DEFAULTS = {"frame_heading_prefix": ""}
_LEGACY_PRESENTATION_DEFAULTS = {"directories": [], "require_declaration": False}
_LEGACY_RULES_DEFAULTS = {
    "channel_rules_from": CHANNEL_RULES_ONE_FILE,
    "channel_rules_file": "",
    "forbidden_phrases_heading": "禁じた言い回し",
    "forbidden_phrases_any_level": False,
    "forbidden_phrases_from": PHRASES_FROM_BULLETS,
}
# 読み方の節の直下に書けた、正本を問わない鍵。
_LEGACY_COMMON_KEYS = ("strip_label_note", "labels")


def read_legacy_config(path: Path) -> dict:
    """移行の前の設定ファイルを読む。TOML として読めなければ SettingsError。"""
    import tomllib

    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise SettingsError(
            f"{LEGACY_CONFIG_FILE} を TOML として読めなかった（{type(error).__name__}）"
        ) from error


def legacy_vocabulary(document: dict) -> dict[str, list[str]]:
    """移行の前の設定ファイルの語彙の節を、語彙の種類の名前から語の一覧への対応にする。"""
    table = document.get("vocabulary", {})
    result: dict[str, list[str]] = {kind: [] for kind, _ in VOCABULARY_KINDS}
    if not isinstance(table, dict):
        return result
    for key, kind in LEGACY_VOCABULARY_KEYS.items():
        words = table.get(key, [])
        if isinstance(words, list):
            result[kind] = [str(item) for item in words]
    return result


def _block_keys(key: str) -> dict[str, object]:
    """移行の前の設定ファイルで、その正本の読み方の節に書けた鍵と、書かなかったときの値。"""
    keys = dict(_LEGACY_BLOCK_DEFAULTS)
    if key == RESUME_LEDGER_KEY:
        keys.update(_LEGACY_LEDGER_DEFAULTS)
    if key == "presentations":
        keys.update(_LEGACY_PRESENTATION_DEFAULTS)
    if key == PRESENTATION_RULES_KEY:
        keys.update(_LEGACY_RULES_DEFAULTS)
    return keys


def _form_reading_table(channels: list[str]) -> dict[str, object]:
    """accord の形を、移行の前の設定ファイルの読み方の節の鍵の道と値で書いたもの。"""
    table: dict[str, object] = {
        "reading.strip_label_note": True,
        "reading.labels": {label: list(names) for label, names in LABEL_ALIASES.items()},
    }
    for key in FILE_KEYS:
        rule = ACCORD_FORM.rule_for(key)
        values: dict[str, object] = {
            "heading_levels": list(rule.heading_levels),
            "under_headings": list(rule.under_headings),
            "heading_prefix": rule.heading_prefix,
            "skip_headings": [],
            "skip_sections_without_fields": rule.skip_sections_without_fields,
            "fields_from_table": rule.fields_from_table,
            "bare_labels": list(rule.bare_labels),
            "entry_number_from_heading": rule.entry_number_from_heading,
        }
        if key == RESUME_LEDGER_KEY:
            values["frame_heading_prefix"] = rule.frame_heading_prefix
        if key == "presentations":
            values["directories"] = list(channels)
            values["require_declaration"] = ACCORD_FORM.require_presentation_declaration
        if key == PRESENTATION_RULES_KEY:
            values["channel_rules_from"] = ACCORD_FORM.channel_rules_from
            values["channel_rules_file"] = ACCORD_FORM.channel_rules_file
            values["forbidden_phrases_heading"] = ACCORD_FORM.forbidden_phrases_heading
            values["forbidden_phrases_any_level"] = ACCORD_FORM.forbidden_phrases_any_level
            values["forbidden_phrases_from"] = ACCORD_FORM.forbidden_phrases_from
        for name, value in values.items():
            table[f"reading.{key}.{name}"] = value
    return table


def _plain(value: object) -> object:
    """TOML の値を、比べられる形（一覧・表・文字列・数・真偽）にそろえる。"""
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    return value


def _legacy_reading_table(reading: dict) -> tuple[dict[str, object], list[str]]:
    """移行の前の設定ファイルの読み方の節を、書かなかった鍵を書かなかったときの値で埋めた鍵の道と値にする。

    あわせて、読み方の節にある知らない鍵の道を返す。
    """
    unknown: list[str] = []
    table: dict[str, object] = {
        "reading.strip_label_note": bool(reading.get("strip_label_note", False)),
        "reading.labels": _plain(reading.get("labels", {})),
    }
    for name in reading:
        if name not in _LEGACY_COMMON_KEYS and name not in FILE_KEYS:
            unknown.append(f"reading.{name}")
    for key in FILE_KEYS:
        section = reading.get(key, {})
        if not isinstance(section, dict):
            unknown.append(f"reading.{key}")
            section = {}
        keys = _block_keys(key)
        for name, default in keys.items():
            table[f"reading.{key}.{name}"] = _plain(section.get(name, default))
        for name in section:
            if name not in keys:
                unknown.append(f"reading.{key}.{name}")
    return table, unknown


def legacy_form_differences(document: dict) -> tuple[list[tuple[str, str]], list[str]]:
    """移行の前の設定ファイルの置き場の節と読み方の節を、accord の形と比べる。

    返すのは、違う鍵と accord の形の値（文）の組の並びと、パッケージ定義の読み飛ばす見出しの並びである。
    読み飛ばす見出しが accord の形で読み飛ばされる節と同じかは、正本を読む側が確かめる。
    置き場の節で比べるのは、正本の置き場（directory）と 7 ファイルの名前と置き場だけで、
    置き場の節のほかの鍵（接続の鍵）は accord の形に入らないので比べない。
    読み方の節にある知らない鍵は、違う鍵として返す。
    """
    differences: list[tuple[str, str]] = []
    source = document.get("source", {})
    if not isinstance(source, dict):
        source = {}
    if str(source.get("directory", "source")) != ".":
        differences.append(("source.directory", "."))
    files = source.get("files", {})
    if not isinstance(files, dict):
        files = {}
    for key, name in FORM_FILES.items():
        if str(files.get(key, "")) != name:
            differences.append((f"source.files.{key}", name))

    channels = legacy_vocabulary(document)[CHANNELS_KIND]
    expected = _form_reading_table(channels)
    reading = document.get("reading", {})
    if not isinstance(reading, dict):
        reading = {}
    written, unknown = _legacy_reading_table(reading)
    skipped = written.pop(LEGACY_PACKAGE_SKIP_KEY, [])
    expected.pop(LEGACY_PACKAGE_SKIP_KEY)
    for key, value in expected.items():
        if written.get(key) != value:
            differences.append((key, _value_text(value)))
    for key in unknown:
        differences.append((key, "（accord の形に無い鍵）"))
    skip_list = [str(item) for item in skipped] if isinstance(skipped, list) else [str(skipped)]
    return differences, skip_list


def _value_text(value: object) -> str:
    """accord の形の値を、断りの候補に載せる 1 つの文にする。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(_value_text(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{key} = {_value_text(item)}" for key, item in value.items()) + "}"
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)

"""正本の置き場と、固有の語彙と、正本の書き方を設定ファイルから読む。

固有の語彙（媒体の名前、機能の分類の節、パッケージの仮説の状態の語）をコードに直書きしない。
直書きすると、別の人が同じ道具を使うときに型の定義ごと書き換える羽目になり、公開できる形でなくなる。
正本の書き方（見出しの深さ、欄を箇条書きで書くか表で書くか、欄のラベルの言い方）も同じ理由で
設定に置く。書き方は人によって違い、コードに固定すると別の人の正本が読めなくなるからである。

この文書は標準ライブラリだけで動かし、型の定義を読み込まない。設定の値に意味の判断が
入り込むと、語彙を差し替えたときに壊れる場所が増えるからである。
"""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass, field, fields
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

# 公開記録の正本の役割の名前。書いても書かなくてもよい唯一の置き場である。
PUBLIC_RECORDS_KEY = "public_records"

# 公開記録の語彙を書く、[vocabulary] の鍵。置き場を書いた設定では、どちらも 1 語以上が要る。
PUBLIC_RECORD_KINDS_KEY = "public_record_kinds"
PUBLIC_RECORD_ROLES_KEY = "public_record_roles"

# 見せ方の正本の役割の名前。
# 見せ方（媒体の規約・語り口の決め・禁じた言い回し）は accord の境界の外なので、型には持たない。
# 持つのは置き場だけで、材料の取り出しが、宛先の媒体の節と禁じた言い回しの節をそのまま渡す。
PRESENTATION_RULES_KEY = "presentation_rules"

# 設定の [source.files] が埋める鍵の全体。正本 8 種に、見せ方の正本を 1 つ足したもの。
FILE_KEYS = (*SOURCE_KEYS, PRESENTATION_RULES_KEY)

# 書かなくてもよい置き場の鍵。公開記録を使わない正本が、今までどおり動くようにするためである。
# 書いていない設定では、公開記録を 0 件として読み、提示物の URL の照合を行わない。
# spec: REQ-081
OPTIONAL_FILE_KEYS = (PUBLIC_RECORDS_KEY,)

# 正本の書き方を書く節の名前。この節が無ければ、すべての鍵が既定値になる。
READING_KEY = "reading"

# [source] の直下に書ける、置き場と書き込みの鍵。どれも書かなくてよい。
# 提示物の置き場。書けば、提示物のディレクトリと媒体ごとの規約のファイルを、正本の置き場ではなく
# ここから読む。正本と提示物を別のリポジトリに置く人のための鍵である。
PRESENTATIONS_ROOT_KEY = "presentations_root"
# 書き込みの記録。true なら、書き込みの操作が正本のファイルを変えるたびに git にコミットする。
COMMIT_WRITES_KEY = "commit_writes"
# 書き出し先。正本の各ファイルを 1 つにつないだ Markdown を書くファイル 1 つ。
EXPORT_PATH_KEY = "export_path"

# 決めの適用先の語を書く、[vocabulary] の鍵。媒体ではない適用範囲（例: 会社のホームページ）。
POSITIONING_TARGETS_KEY = "positioning_targets"

# 設定ファイルの最上位に書ける節の名前。これ以外の名前は、設定を読んだ瞬間に止める。
TOP_LEVEL_KEYS = ("source", "vocabulary", READING_KEY)

# 欄のラベルの読み替えを書く、書き方の節の中の表の名前。
LABEL_ALIASES_KEY = "labels"

# 媒体の規約の置き場の書き方。1 つのファイルの媒体名の節から読むか、媒体ごとのファイルから読むか。
CHANNEL_RULES_ONE_FILE = "one_file"
CHANNEL_RULES_PER_CHANNEL_FILE = "per_channel_file"
CHANNEL_RULES_CHOICES = (CHANNEL_RULES_ONE_FILE, CHANNEL_RULES_PER_CHANNEL_FILE)

# 禁じた言い回しの節の中身の読み方。箇条書きから読むか、節の最初の表の 1 列目から読むか。
PHRASES_FROM_BULLETS = "bullets"
PHRASES_FROM_TABLE = "table"
PHRASES_FROM_CHOICES = (PHRASES_FROM_BULLETS, PHRASES_FROM_TABLE)


@dataclass(frozen=True)
class BlockRule:
    """正本 1 種の読み方。どの節をブロックとして読み、その節の欄をどう読むか。

    鍵を 1 つも書かなければ、すべてが既定値になり、第 1 版とまったく同じに読む。
    既定値はこの宣言の 1 か所だけが持ち、設定を読む側も読み込みの側も持たない。
    """

    # 節を選ぶ
    # spec: REQ-046
    heading_levels: tuple[int, ...] = (2,)
    under_headings: tuple[str, ...] = ()
    heading_prefix: str = ""
    # 職務経歴書の台帳だけに書ける鍵。見出しがこの文字列で始まる節を、在籍職歴の枠のブロックとして読む。
    # heading_prefix の絞りを通さない見出しでも、この文字列で始まれば読む（heading_prefix の意味は変えない）。
    # spec: REQ-375
    frame_heading_prefix: str = ""
    skip_headings: tuple[str, ...] = ()
    skip_sections_without_fields: bool = False
    # 欄を読む
    fields_from_table: bool = False
    bare_labels: tuple[str, ...] = ()
    entry_number_from_heading: bool = False
    # 欄のラベルを読み替える（正本を問わず共通で、[reading] の直下に書く）
    strip_label_note: bool = False
    labels: dict[str, tuple[str, ...]] = field(default_factory=dict)


# 鍵を 1 つも書かなかったときの読み方。第 1 版の読み方そのものである。
DEFAULT_BLOCK_RULE = BlockRule()

# 正本ごとの節に書ける鍵の名前。設定の綴り違いをその場で止めるために使う。
# ラベルの読み替え（labels）と括弧書きの除去（strip_label_note）は正本を問わず共通なので、
# 正本ごとの節ではなく [reading] の直下に 1 度だけ書く。
COMMON_LABEL_KEYS = frozenset({"strip_label_note", "labels"})
# 職務経歴書の台帳の節にだけ書ける鍵。ほかの正本の節に書くと、知らない鍵として止める。
LEDGER_ONLY_KEYS = frozenset({"frame_heading_prefix"})
BLOCK_RULE_KEYS = (
    frozenset(item.name for item in fields(BlockRule)) - COMMON_LABEL_KEYS - LEDGER_ONLY_KEYS
)

# 職務経歴書の台帳の正本の役割の名前。
RESUME_LEDGER_KEY = "resume_ledger"


@dataclass(frozen=True)
class ReadingRules:
    """設定の「書き方」の節。正本ごとの読み方と、提示物・見せ方の正本の読み方を持つ。"""

    blocks: dict[str, BlockRule] = field(default_factory=dict)
    # 提示物
    # spec: REQ-047
    presentation_directories: tuple[str, ...] = ()
    # spec: REQ-048
    require_presentation_declaration: bool = False
    # 見せ方の正本
    # spec: REQ-049
    channel_rules_from: str = CHANNEL_RULES_ONE_FILE
    channel_rules_file: str = ""
    # spec: REQ-050
    forbidden_phrases_heading: str = "禁じた言い回し"
    # spec: REQ-051
    forbidden_phrases_any_level: bool = False
    # spec: REQ-052
    forbidden_phrases_from: str = PHRASES_FROM_BULLETS
    # 設定ファイルに実際に書かれていた読み方の鍵。返り値の足跡にそのまま載せる。
    applied_keys: tuple[str, ...] = ()

    def rule_for(self, key: str) -> BlockRule:
        """正本の役割の名前から、その正本の読み方を返す。書いていなければ既定の読み方。"""
        return self.blocks.get(key, DEFAULT_BLOCK_RULE)


# 提示物と見せ方の正本の節にだけ書ける鍵と、それを受け取る ReadingRules の欄の名前。
PRESENTATION_KEYS = {
    "directories": "presentation_directories",
    "require_declaration": "require_presentation_declaration",
}
PRESENTATION_RULES_KEYS = {
    "channel_rules_from": "channel_rules_from",
    "channel_rules_file": "channel_rules_file",
    "forbidden_phrases_heading": "forbidden_phrases_heading",
    "forbidden_phrases_any_level": "forbidden_phrases_any_level",
    "forbidden_phrases_from": "forbidden_phrases_from",
}


@dataclass(frozen=True)
class Settings:
    """起動時に決まる、正本の置き場と語彙と書き方。"""

    config_path: Path
    source_dir: Path
    files: dict[str, str] = field(default_factory=dict)
    channels: list[str] = field(default_factory=list)
    # 媒体ではない決めの適用範囲の語。書かなければ空で、適用範囲は媒体の名前と「全体」だけになる。
    positioning_targets: list[str] = field(default_factory=list)
    capability_categories: list[str] = field(default_factory=list)
    package_hypothesis_states: list[str] = field(default_factory=list)
    public_record_kinds: list[str] = field(default_factory=list)
    public_record_roles: list[str] = field(default_factory=list)
    reading: ReadingRules = field(default_factory=ReadingRules)
    # 提示物の置き場。設定に書かなければ None で、正本の置き場（source_dir）から読む。
    presentations_root: Path | None = None
    # 書き込みの操作のたびに git にコミットするか。
    commit_writes: bool = False
    # 書き出し先のファイル。設定に書かなければ None で、書き出しは断る。
    export_path: Path | None = None

    @property
    def presentations_dir(self) -> Path:
        """提示物のディレクトリと媒体ごとの規約のファイルを読む根。書かなければ正本の置き場。"""
        # spec: REQ-398
        if self.presentations_root is not None:
            return self.presentations_root
        # spec: REQ-399
        return self.source_dir

    def source_file_names(self) -> list[str]:
        """正本のファイルの名前（設定に書いた名前）を、FILE_KEYS の並びで返す。

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
        """設定に書いたファイルの名前から、そのファイルを指す正本の役割の名前を並びの順で返す。"""
        return [
            key for key in FILE_KEYS if key != "presentations" and self.files.get(key) == name
        ]

    def has_file(self, key: str) -> bool:
        """その正本の置き場が、設定に書かれているか。

        書かなくてもよい置き場（公開記録）を読む側が、path_for を呼ぶ前に確かめる。
        """
        return key in self.files

    def path_for(self, key: str) -> Path:
        """正本の役割の名前から、実ファイル（提示物だけはディレクトリ）の場所を返す。"""
        if key not in self.files:
            raise KeyError(f"設定に正本 '{key}' のファイル名が無い: {self.config_path.name}")
        if key == "presentations":
            return self.presentations_dir / self.files[key]
        return self.source_dir / self.files[key]


def default_config_path() -> Path:
    """`--config` を省いたときに読む、同梱の設定の見本の場所を返す。

    開発中の木では リポジトリ直下の samples/、導入した先では accord/samples/ にある。
    どちらも見て、実在するほうを返す。
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "samples" / "accord.toml",  # 導入した先（accord/samples/）
        here.parents[3] / "samples" / "accord.toml",  # 開発中の木（リポジトリ直下）
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


def _require_list(table: dict, key: str, config_path: Path) -> list[str]:
    """設定の一覧の欄を、文字列の一覧として取り出す。空の一覧は誤りとして扱う。"""
    value = table.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"設定 '{key}' に 1 つ以上の語が要る: {config_path}")
    return [str(item) for item in value]


def _reject_unknown_keys(table: dict, allowed: set[str], where: str, config_path: Path) -> None:
    """書き方の節に、知らない鍵が書かれていないかを見る。

    綴りを間違えた鍵を黙って読み飛ばすと、書いたつもりの読み方が効かないまま
    「読めない」だけが残る。設定を読んだ瞬間に、鍵の名前と書ける名前の一覧で止める。
    """
    # spec: REQ-077
    unknown = sorted(key for key in table if key not in allowed)
    if unknown:
        raise ValueError(
            f"設定の [{where}] に知らない鍵がある: {'、'.join(unknown)}"
            f"（書ける鍵: {'、'.join(sorted(allowed))}）: {config_path}"
        )


def _reject_unknown_top_level(document: dict, config_path: Path) -> None:
    """設定ファイルの最上位に、知らない節が書かれていないかを見る。

    綴りを間違えた節を黙って読み飛ばすと、書いたつもりの置き場も語彙も読み方も効かないまま
    サーバーが立ち上がり、既定の見本を読んだ結果が返り続ける。書いた名前と書ける名前を添えて、
    設定を読んだ瞬間に止める（節でない最上位の鍵も同じ扱いにする）。
    """
    # spec: REQ-075
    unknown = sorted(key for key in document if key not in TOP_LEVEL_KEYS)
    if unknown:
        raise ValueError(
            f"設定の最上位に知らない節がある: {'、'.join(unknown)}"
            f"（書ける節: {'、'.join(sorted(TOP_LEVEL_KEYS))}）: {config_path}"
        )


def _one_of(value: object, choices: tuple[str, ...], where: str, config_path: Path) -> str:
    """選べる語が決まっている鍵の値を確かめる。"""
    text = str(value)
    # spec: REQ-079
    if text not in choices:
        raise ValueError(
            f"設定 '{where}' に書ける語は {'、'.join(choices)} のどれか"
            f"（書かれていた語: {text}）: {config_path}"
        )
    return text


def _block_rule(table: dict, common: dict, where: str, config_path: Path) -> BlockRule:
    """正本 1 種の書き方の節を、読み方にする。書いていない鍵は既定値のまま残る。"""
    values = dict(common)
    for name in BLOCK_RULE_KEYS | LEDGER_ONLY_KEYS:
        if name not in table:
            continue
        value = table[name]
        if name == "heading_levels":
            values[name] = tuple(int(item) for item in value)
        elif name in ("under_headings", "skip_headings", "bare_labels"):
            values[name] = tuple(str(item) for item in value)
        elif name in ("heading_prefix", "frame_heading_prefix"):
            values[name] = str(value)
        else:
            values[name] = bool(value)
    # spec: REQ-078
    if not values.get("heading_levels", DEFAULT_BLOCK_RULE.heading_levels):
        raise ValueError(f"設定 [{where}] の heading_levels に深さが 1 つ以上要る: {config_path}")
    return BlockRule(**values)


def _applied_reading_keys(table: dict) -> tuple[str, ...]:
    """設定ファイルに実際に書かれていた読み方の鍵を、点でつないだ道の並びにする。

    並びは [reading] の直下を先に、続けて正本ごとの節を FILE_KEYS の順に置き、同じ節の中は
    鍵の名前の辞書順にする。呼ぶたびに同じ並びになるようにするためである。
    """
    applied = [f"{READING_KEY}.{key}" for key in sorted(table) if key not in FILE_KEYS]
    for key in FILE_KEYS:
        section = table.get(key, {})
        applied += [f"{READING_KEY}.{key}.{name}" for name in sorted(section)]
    return tuple(applied)


def _inside(path: Path, root: Path) -> bool:
    """path が root そのものか、root の下にあるか。"""
    return path == root or root in path.parents


def _inside_git_repository(directory: Path) -> bool:
    """そのディレクトリが git のリポジトリの作業ツリーの中にあるか。git が無ければ False。"""
    try:
        completed = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _presentations_root(source_table: dict, config_path: Path) -> Path | None:
    """提示物の置き場の鍵を読む。書かれていなければ None。実在しないディレクトリなら止める。"""
    if PRESENTATIONS_ROOT_KEY not in source_table:
        return None
    value = str(source_table[PRESENTATIONS_ROOT_KEY])
    # spec: REQ-400
    root = (config_path.parent / value).resolve()
    # spec: REQ-401
    if not root.is_dir():
        raise ValueError(
            f"設定の [source] {PRESENTATIONS_ROOT_KEY} が実在するディレクトリを指していない"
            f"（書かれていた値: {value}）: {config_path.name}"
        )
    return root


def _export_path(
    source_table: dict, config_path: Path, source_dir: Path, presentations_dir: Path
) -> Path | None:
    """書き出し先の鍵を読む。正本の置き場か提示物の置き場の中を指していれば止める。"""
    if EXPORT_PATH_KEY not in source_table:
        return None
    value = str(source_table[EXPORT_PATH_KEY])
    path = (config_path.parent / value).resolve()
    # spec: REQ-453
    if _inside(path, source_dir) or _inside(path, presentations_dir):
        raise ValueError(
            f"設定の [source] {EXPORT_PATH_KEY} が、正本の置き場か提示物の置き場の中を指している"
            f"（書かれていた値: {value}）。書き出しの写しは、正本と提示物の置き場の外に置く: "
            f"{config_path.name}"
        )
    return path


def load_reading_rules(document: dict, config_path: Path) -> ReadingRules:
    """設定の「書き方」の節を読む。節が無ければ、すべて既定値（第 1 版と同じ読み方）を返す。"""
    table = document.get(READING_KEY, {})
    _reject_unknown_keys(
        table, {"strip_label_note", LABEL_ALIASES_KEY, *FILE_KEYS}, READING_KEY, config_path
    )

    # ラベルの読み替えと括弧書きの除去は、正本を問わず共通なので、どの正本の読み方にも同じ値が入る。
    common: dict = {}
    if "strip_label_note" in table:
        common["strip_label_note"] = bool(table["strip_label_note"])
    aliases = table.get(LABEL_ALIASES_KEY, {})
    if aliases:
        common["labels"] = {
            str(label): tuple(str(name) for name in names) for label, names in aliases.items()
        }

    blocks: dict[str, BlockRule] = {}
    for key in FILE_KEYS:
        section = table.get(key, {})
        extra = {
            "presentations": set(PRESENTATION_KEYS),
            PRESENTATION_RULES_KEY: set(PRESENTATION_RULES_KEYS),
            RESUME_LEDGER_KEY: set(LEDGER_ONLY_KEYS),
        }.get(key, set())
        _reject_unknown_keys(
            section, BLOCK_RULE_KEYS | extra, f"{READING_KEY}.{key}", config_path
        )
        blocks[key] = _block_rule(section, common, f"{READING_KEY}.{key}", config_path)

    values: dict = {"blocks": blocks, "applied_keys": _applied_reading_keys(table)}
    presentations = table.get("presentations", {})
    if "directories" in presentations:
        values[PRESENTATION_KEYS["directories"]] = tuple(
            str(name) for name in presentations["directories"]
        )
    if "require_declaration" in presentations:
        values[PRESENTATION_KEYS["require_declaration"]] = bool(
            presentations["require_declaration"]
        )

    rules_table = table.get(PRESENTATION_RULES_KEY, {})
    for key, name in PRESENTATION_RULES_KEYS.items():
        if key not in rules_table:
            continue
        where = f"{READING_KEY}.{PRESENTATION_RULES_KEY}.{key}"
        if key == "channel_rules_from":
            values[name] = _one_of(rules_table[key], CHANNEL_RULES_CHOICES, where, config_path)
        elif key == "forbidden_phrases_from":
            values[name] = _one_of(rules_table[key], PHRASES_FROM_CHOICES, where, config_path)
        elif key == "forbidden_phrases_any_level":
            values[name] = bool(rules_table[key])
        else:
            values[name] = str(rules_table[key])

    return ReadingRules(**values)


def load_settings(path: Path | None = None) -> Settings:
    """設定ファイルを読む。path が None なら同梱の見本（samples/accord.toml）を読む。"""
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.is_file():
        raise FileNotFoundError(f"設定ファイルが無い: {config_path}")

    with config_path.open("rb") as handle:
        document = tomllib.load(handle)

    _reject_unknown_top_level(document, config_path)

    source_table = document.get("source", {})
    directory = str(source_table.get("directory", "source"))
    source_dir = (config_path.parent / directory).resolve()
    presentations_root = _presentations_root(source_table, config_path)
    presentations_dir = presentations_root if presentations_root is not None else source_dir
    export_path = _export_path(source_table, config_path, source_dir, presentations_dir)

    commit_writes = bool(source_table.get(COMMIT_WRITES_KEY, False))
    # spec: REQ-406
    if commit_writes and not _inside_git_repository(source_dir):
        raise ValueError(
            f"設定の [source] {COMMIT_WRITES_KEY} が true なのに、正本の置き場が git のリポジトリの中に無い。"
            f"正本の置き場で git init するか、{COMMIT_WRITES_KEY} を外す: {config_path.name}"
        )

    files_table = source_table.get("files", {})
    missing = [
        key for key in FILE_KEYS if key not in files_table and key not in OPTIONAL_FILE_KEYS
    ]
    if missing:
        raise ValueError(f"設定の [source.files] に {'、'.join(missing)} が無い: {config_path}")

    vocabulary_table = document.get("vocabulary", {})

    # 公開記録の置き場を書いた設定だけ、その語彙 2 つを必須にする。置き場を書いていない設定は
    # 公開記録を使わないので、語彙が無くても今までどおり起動する。
    # spec: REQ-080
    if PUBLIC_RECORDS_KEY in files_table:
        public_record_kinds = _require_list(
            vocabulary_table, PUBLIC_RECORD_KINDS_KEY, config_path
        )
        public_record_roles = _require_list(
            vocabulary_table, PUBLIC_RECORD_ROLES_KEY, config_path
        )
    else:
        public_record_kinds = []
        public_record_roles = []

    targets = vocabulary_table.get(POSITIONING_TARGETS_KEY, [])
    if not isinstance(targets, list):
        raise ValueError(f"設定 '{POSITIONING_TARGETS_KEY}' は語の一覧で書く: {config_path.name}")

    return Settings(
        config_path=config_path,
        source_dir=source_dir,
        files={key: str(files_table[key]) for key in FILE_KEYS if key in files_table},
        channels=_require_list(vocabulary_table, "channels", config_path),
        # spec: REQ-407
        positioning_targets=[str(item) for item in targets],
        presentations_root=presentations_root,
        commit_writes=commit_writes,
        export_path=export_path,
        capability_categories=_require_list(
            vocabulary_table, "capability_categories", config_path
        ),
        package_hypothesis_states=_require_list(
            vocabulary_table, "package_hypothesis_states", config_path
        ),
        public_record_kinds=public_record_kinds,
        public_record_roles=public_record_roles,
        reading=load_reading_rules(document, config_path),
    )

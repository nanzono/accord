"""正本の置き場と、固有の語彙を設定ファイルから読む。

固有の語彙（媒体の名前、機能の分類の節、パッケージの仮説の状態の語）をコードに直書きしない。
直書きすると、別の人が同じ道具を使うときに型の定義ごと書き換える羽目になり、公開できる形でなくなる。

この文書は標準ライブラリだけで動かし、型の定義を読み込まない。設定の値に意味の判断が
入り込むと、語彙を差し替えたときに壊れる場所が増えるからである。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# 正本のファイルの役割の名前。設定ファイルの [source.files] はこの 7 つを埋める。
SOURCE_KEYS = (
    "positioning",
    "packages",
    "capabilities",
    "career",
    "engagements",
    "resume_ledger",
    "presentations",
)


@dataclass(frozen=True)
class Settings:
    """起動時に決まる、正本の置き場と語彙。"""

    config_path: Path
    source_dir: Path
    files: dict[str, str] = field(default_factory=dict)
    channels: list[str] = field(default_factory=list)
    capability_categories: list[str] = field(default_factory=list)
    package_hypothesis_states: list[str] = field(default_factory=list)

    def path_for(self, key: str) -> Path:
        """正本の役割の名前から、実ファイル（提示物だけはディレクトリ）の場所を返す。"""
        if key not in self.files:
            raise KeyError(f"設定に正本 '{key}' のファイル名が無い: {self.config_path}")
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


def load_settings(path: Path | None = None) -> Settings:
    """設定ファイルを読む。path が None なら同梱の見本（samples/accord.toml）を読む。"""
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.is_file():
        raise FileNotFoundError(f"設定ファイルが無い: {config_path}")

    with config_path.open("rb") as handle:
        document = tomllib.load(handle)

    source_table = document.get("source", {})
    directory = str(source_table.get("directory", "source"))
    source_dir = (config_path.parent / directory).resolve()

    files_table = source_table.get("files", {})
    missing = [key for key in SOURCE_KEYS if key not in files_table]
    if missing:
        raise ValueError(f"設定の [source.files] に {'、'.join(missing)} が無い: {config_path}")

    vocabulary_table = document.get("vocabulary", {})

    return Settings(
        config_path=config_path,
        source_dir=source_dir,
        files={key: str(files_table[key]) for key in SOURCE_KEYS},
        channels=_require_list(vocabulary_table, "channels", config_path),
        capability_categories=_require_list(
            vocabulary_table, "capability_categories", config_path
        ),
        package_hypothesis_states=_require_list(
            vocabulary_table, "package_hypothesis_states", config_path
        ),
    )

"""テストが共通で使う道具。

テストは必ず、同梱のサンプルの一時的な写しの上で走らせる。書きの操作を試すテストがあるので、
リポジトリのサンプルそのものを書き換えないための決まりである。
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from accord.vocabulary.settings import Settings, load_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples"


@pytest.fixture
def sample_copy(tmp_path: Path) -> Path:
    """同梱のサンプル一式を一時的な場所に写し、その置き場を返す。"""
    destination = tmp_path / "samples"
    shutil.copytree(SAMPLES_DIR, destination)
    return destination


@pytest.fixture
def settings(sample_copy: Path) -> Settings:
    """写したサンプルを指す設定を返す。"""
    return load_settings(sample_copy / "accord.toml")


@pytest.fixture
def alt_settings(sample_copy: Path) -> Settings:
    """写したサンプルのうち、書き方の違う第 2 の正本を指す設定を返す。

    中身は第 1 版のサンプルと同じで、書き方だけが違う。同じ呼び出しが同じ結果を返すことを、
    書き方の違いだけを変数にして確かめられる。
    """
    return load_settings(sample_copy / "accord_alt.toml")


def source_digest(source_dir: Path) -> dict[str, str]:
    """正本のディレクトリ配下の全ファイルについて、中身のバイト列の指紋を取る。

    拒否のときに正本が 1 バイトも変わらないことを、呼び出しの前後で比べて確かめるために使う。
    """
    digest: dict[str, str] = {}
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            digest[path.relative_to(source_dir).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return digest


def add_config_lines(config_path: Path, table: str, lines: list[str]) -> Settings:
    """設定ファイルの表（`[source]` や `[vocabulary]`）の見出しの直後に行を足し、読み直した設定を返す。

    写しの設定に、テストで使う鍵（提示物の置き場・書き込みの記録・書き出し先・適用先の語）を足すために使う。
    表の見出しが無ければ、テストの前提が崩れたとして落とす。
    """
    text = config_path.read_text(encoding="utf-8")
    heading = f"[{table}]\n"
    assert heading in text, f"設定に {heading.strip()} が無い: {config_path}"
    text = text.replace(heading, heading + "".join(f"{line}\n" for line in lines), 1)
    config_path.write_text(text, encoding="utf-8")
    return load_settings(config_path)


def git(directory: Path, *args: str) -> str:
    """一時の場所の git を呼び、標準出力を返す。失敗したらテストを落とす。"""
    import subprocess

    completed = subprocess.run(
        ["git", "-C", str(directory), *args], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def init_git(directory: Path) -> None:
    """一時の場所を git のリポジトリにし、いまの中身をすべて 1 つ目のコミットにする。"""
    git(directory, "init", "-q")
    git(directory, "config", "user.name", "tester")
    git(directory, "config", "user.email", "tester@example.invalid")
    git(directory, "add", "-A")
    git(directory, "commit", "-q", "-m", "first")

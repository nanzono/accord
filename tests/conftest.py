"""テストが共通で使う道具。

テストは必ず、同梱の見本の一時的な写しの上で走らせる。書きの操作を試すテストがあるので、
リポジトリの見本そのものを書き換えないための決まりである。写しの経歴データの置き場は、起動の
決まり（git の作業ツリーの根）に合わせて git のリポジトリにする。
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
    """同梱の見本一式を一時的な場所に写し、経歴データの置き場（data）を git の作業ツリーの根にして返す。

    返すのは見本の写しの根で、その下に data（経歴データの置き場）と presentations（提示物の置き場）がある。
    """
    destination = tmp_path / "samples"
    shutil.copytree(SAMPLES_DIR, destination)
    init_git(destination / "data")
    return destination


def sample_settings(sample_copy: Path) -> Settings:
    """写した見本を、起動の引数（--data と --presentations）と同じ形で読んだ設定を返す。"""
    return load_settings(sample_copy / "data", sample_copy / "presentations")


@pytest.fixture
def settings(sample_copy: Path) -> Settings:
    """写した見本を指す設定を返す。"""
    return sample_settings(sample_copy)


@pytest.fixture
def alt_settings(tmp_path: Path) -> Settings:
    """settings とは別の場所に写した、同じ見本の設定を返す。

    見本は accord の形の 1 つだけだが、2 つの設定に同じ書き換えを順に当てるテストのために、
    写しの置き場を分けておく。
    """
    destination = tmp_path / "samples_second"
    shutil.copytree(SAMPLES_DIR, destination)
    init_git(destination / "data")
    return sample_settings(destination)


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


def add_vocabulary_terms(settings: Settings, kind: str, terms: list[str]) -> Settings:
    """写しの語彙（vocabulary.md）の種類の節に語を足してコミットし、読み直した設定を返す。

    テストで使う語（決めの適用先の語など）を足すために使う。節が無ければ、テストの前提が崩れたとして落とす。
    """
    path = settings.vocabulary_path
    text = path.read_text(encoding="utf-8")
    heading = f"## {kind}\n"
    assert heading in text, f"語彙に {kind} の節が無い: {path}"
    text = text.replace(heading, heading + "\n" + "".join(f"- {term}\n" for term in terms), 1)
    path.write_text(text, encoding="utf-8")
    commit_all(settings.source_dir, "テストの語彙")
    return load_settings(settings.source_dir, settings.presentations_dir)


def commit_all(directory: Path, message: str = "テストの準備") -> None:
    """一時の置き場のいまの中身をすべて 1 件のコミットにする（テストが直接書いた変更を確定する）。"""
    git(directory, "add", "-A")
    git(directory, "commit", "-q", "--allow-empty", "-m", message)


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

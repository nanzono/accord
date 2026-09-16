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

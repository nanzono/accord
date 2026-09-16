"""型と制約の正本（ontology.yaml）と、そこから作る生成物・資源についてのテスト。"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from accord.models.constraints import CONSTRAINTS
from accord.models.ontology import load_ontology
from accord.server.app import create_server

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate_models.py"
SERVICES_DIR = REPO_ROOT / "src" / "accord" / "services"

# 数の正本は src/accord/ontology.yaml。
EXPECTED_TYPES = 7
EXPECTED_RELATIONS = 6
EXPECTED_RELATION_EDGES = 7
EXPECTED_CONSTRAINTS = 7


def test_ontology_lists_seven_types_six_relations_seven_constraints(settings) -> None:
    """資源 accord://ontology が、型 7 つ・関係 6 種・制約 7 つを返す。"""
    server = create_server(settings)
    contents = asyncio.run(server.read_resource("accord://ontology"))
    document = json.loads(contents[0].content)

    assert len(document["types"]) == EXPECTED_TYPES
    assert len(document["relations"]) == EXPECTED_RELATIONS
    assert len(document["constraints"]) == EXPECTED_CONSTRAINTS

    # 関係は 6 種で、相手の型ごとに数えた辺は 7 本になる。
    ontology = load_ontology()
    assert ontology.relation_edge_count == EXPECTED_RELATION_EDGES


def test_generated_models_match_ontology() -> None:
    """生成物が正本と 1 バイトも違わない（違えば生成器が終了コード 1 を返す）。"""
    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.xfail(
    strict=True,
    reason=(
        "制約 7 つのうち、実装をサービスに置くのは整合検査と書きの操作 3 つの段である。"
        "この段（決めの正本の型とサンプル）では、まだ執行の実装が揃っていない。"
    ),
)
def test_every_constraint_in_yaml_has_an_implementation() -> None:
    """YAML に宣言した制約のそれぞれに、サービス側の執行の実装が名前で結び付いている。

    執行する操作を持たない制約（モジュールの分け方で守る「逆参照を書かない」）は、
    実行時のコードを持たないので対象から外す。
    """
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(SERVICES_DIR.glob("*.py"))
    )
    unimplemented = [
        constraint.name
        for constraint in CONSTRAINTS
        if constraint.enforced_by and constraint.name not in sources
    ]
    assert unimplemented == []

"""型と制約の正本（ontology.yaml）と、そこから作る生成物・資源についてのテスト。

要件 1 件につきテストを 1 本置く。もとは 3 本で見ていたものを、返り値に現れる 1 か所ごとに割った。
資源が返す 3 つの一覧と矢印の数え方で 4 本、生成物の突き合わせで 2 本（合格する側と不合格になる側）、
正本とコードの結びで 3 本である。型の正本が 5 つの型に ID の欄を必須で持たせることは、
tests/test_id_reference.py にあったものをここへ移した（型の正本の欄の定義を見るテストなので）。

生成物の突き合わせが不合格になる側は、正本の写しを一時の場所で壊して `--ontology` に渡す。
リポジトリの正本と生成物は 1 バイトも書き換えない。
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import subprocess
import sys
from pathlib import Path

import yaml

from accord.models.constraints import CONSTRAINTS
from accord.models.ontology import load_ontology
from accord.server.app import create_server
from accord.services.consistency import ENFORCEMENT, enforcement_for

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate_models.py"
SERVICES_DIR = REPO_ROOT / "src" / "accord" / "services"
ONTOLOGY_YAML = REPO_ROOT / "src" / "accord" / "ontology.yaml"
CONSTRAINTS_PY = REPO_ROOT / "src" / "accord" / "models" / "constraints.py"

# 数の正本は src/accord/ontology.yaml。
EXPECTED_TYPES = 8
EXPECTED_RELATIONS = 8
EXPECTED_RELATION_EDGES = 11
EXPECTED_CONSTRAINTS = 16

# ID の欄を必須で持つ、指される側の 5 つの型。
ID_BEARING_TYPES = ("CareerFrame", "Engagement", "PublicRecord", "Capability", "Package")

# ID の形と一意性を守らせる制約の名前。
ID_FORMAT = "ID の形式"
ID_UNIQUENESS = "ID の一意性"

# サービスの実装が、制約の名前を型の正本の宣言から引くときの辞書の名前。
CONSTRAINT_LOOKUP = "CONSTRAINT_BY_NAME"


def _resource_document(settings) -> dict:
    """資源 accord://ontology を読み、返ってきた中身を辞書にして返す。"""
    server = create_server(settings)
    contents = asyncio.run(server.read_resource("accord://ontology"))
    return json.loads(contents[0].content)


def _services_source() -> str:
    """サービスの実装をすべてつないだ文字列を返す（制約の名前が現れるかを見るため）。"""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(SERVICES_DIR.glob("*.py")))


def _names_pulled_from_the_declaration(path: Path) -> set[str]:
    """ファイルの中で、制約の名前を型の正本の宣言から引いている箇所の名前をすべて返す。

    見るのは `CONSTRAINT_BY_NAME["名前"]` の形の式だけで、構文木から拾う。コメントや文字列の中に
    名前が書かれているだけでは拾わない（名前を変えたあとに古い名前がコメントに残っていても、
    引いていることにはならない）。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    pulled: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == CONSTRAINT_LOOKUP
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            pulled.add(node.slice.value)
    return pulled


# ---------------------------------------------------------------- 型の正本の欄の定義


def test_REQ_326_five_types_require_an_id_field() -> None:
    """指される側の 5 つの型が、必須の text の欄 id を持ち、制約は 16 件ある。"""
    ontology = load_ontology()

    for name in ID_BEARING_TYPES:
        entry = ontology.type_named(name)
        assert entry is not None, name
        field = next((item for item in entry.fields if item.name == "id"), None)
        assert field is not None, f"{name} に欄 id が無い"
        assert field.required is True, name
        assert field.type == "text", name
        assert field.label == "ID", name

    assert len(ontology.constraints) == EXPECTED_CONSTRAINTS
    assert any(item.name == ID_FORMAT for item in ontology.constraints)
    assert any(item.name == ID_UNIQUENESS for item in ontology.constraints)


# ---------------------------------------------------------------- 資源が返すもの


def test_REQ_327_the_resource_returns_every_type(settings) -> None:
    """資源 accord://ontology が、正本の型をすべて返す（いまは 8 つ）。"""
    document = _resource_document(settings)

    assert len(document["types"]) == EXPECTED_TYPES


def test_REQ_328_the_resource_returns_every_relation(settings) -> None:
    """資源 accord://ontology が、正本の関係をすべて返す（いまは 8 種）。"""
    document = _resource_document(settings)

    assert len(document["relations"]) == EXPECTED_RELATIONS


def test_REQ_329_the_resource_returns_every_constraint(settings) -> None:
    """資源 accord://ontology が、正本の制約をすべて返す（いまは 16 件）。"""
    document = _resource_document(settings)

    assert len(document["constraints"]) == EXPECTED_CONSTRAINTS


def test_REQ_330_a_relation_counts_one_edge_per_target() -> None:
    """相手の型を 2 つ以上持つ関係は、相手 1 つにつき 1 本の矢印として数える（8 種で 11 本）。"""
    ontology = load_ontology()

    assert ontology.relation_edge_count == EXPECTED_RELATION_EDGES


# ---------------------------------------------------------------- 生成物と正本の突き合わせ


def test_REQ_331_the_generated_models_match_the_ontology() -> None:
    """生成物が正本と 1 バイトも違わないので、突き合わせが終了コード 0 で終わる。"""
    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_REQ_332_a_stale_generated_file_fails_the_check(tmp_path: Path) -> None:
    """正本の写しから制約を 1 件落として渡すと、違うファイルの名前と差の要約つきで不合格になる。

    壊すのは一時の場所に作った写しだけである。リポジトリの正本と生成物には触らないことを、
    突き合わせの前後で生成物の中身を比べて確かめる。
    """
    before = CONSTRAINTS_PY.read_text(encoding="utf-8")

    document = yaml.safe_load(ONTOLOGY_YAML.read_text(encoding="utf-8"))
    assert document["constraints"], "正本に制約が 1 件も無く、写しを壊せない。"
    document["constraints"] = document["constraints"][:-1]
    stale = tmp_path / "ontology.yaml"
    stale.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--check", "--ontology", str(stale)],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert CONSTRAINTS_PY.name in completed.stdout, completed.stdout
    assert "差がある" in completed.stdout, completed.stdout
    assert CONSTRAINTS_PY.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------- 正本のルールと実装の結び


def test_REQ_333_every_rule_is_enforced_where_it_is_declared() -> None:
    """正本が挙げるルールのそれぞれを、執行するサービスの実装が型の正本の宣言から名前で引いている。

    ルールを執行する関数（効かせる先の一覧が結ぶもの）の置かれたファイルごとに、そのファイルが
    `CONSTRAINT_BY_NAME["名前"]` の式でそのルールの名前を引いているかを見る。名前が本文のどこかに
    部分一致で現れるかだけを見ると、古い名前がコメントに残っているだけで合格してしまう。
    執行する操作を持たない制約（モジュールの分け方で守る「逆参照を書かない」）は、
    実行時のコードを持たないので対象から外す。
    """
    sources = _services_source()
    unimplemented = [
        constraint.name
        for constraint in CONSTRAINTS
        if constraint.enforced_by and constraint.name not in sources
    ]
    assert unimplemented == []

    not_pulled = []
    for constraint in CONSTRAINTS:
        if not constraint.enforced_by:
            continue
        files = {
            Path(inspect.getsourcefile(function)).resolve()
            for operation in constraint.enforced_by
            for function in enforcement_for(constraint.name).get(operation, ())
        }
        assert files, f"{constraint.name} を執行する関数が効かせる先の一覧に無い"
        for path in sorted(files):
            if constraint.name not in _names_pulled_from_the_declaration(path):
                not_pulled.append(f"{constraint.name} / {path.name}")
    assert not_pulled == []


def test_REQ_334_every_declared_operation_has_a_way_to_enforce() -> None:
    """ルールが宣言した操作のそれぞれに、呼べる関数が 1 つ以上結び付いている。"""
    missing = []
    for constraint in CONSTRAINTS:
        table = enforcement_for(constraint.name)
        for operation in constraint.enforced_by:
            functions = table.get(operation, ())
            if not functions or not all(callable(function) for function in functions):
                missing.append(f"{constraint.name} / {operation}")
    assert missing == []


def test_REQ_335_no_stale_rule_or_operation_is_left_behind() -> None:
    """効かせる先の一覧に、正本に無い制約や操作が残っていない（名前を変えたときの取り残しを見る）。"""
    declared = {constraint.name: set(constraint.enforced_by) for constraint in CONSTRAINTS}
    stray = [
        f"{name} / {operation}"
        for name, table in ENFORCEMENT.items()
        for operation in table
        if operation not in declared.get(name, set())
    ]
    assert stray == []

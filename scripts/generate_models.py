#!/usr/bin/env python3
"""型と制約の正本 src/accord/ontology.yaml から、Pydantic のモデルと制約の宣言を書き出す道具。

書き出す先は 2 つ。

    src/accord/models/types.py        型の Pydantic モデル
    src/accord/models/constraints.py  制約の宣言（class Constraint と CONSTRAINTS）

引数なしで呼ぶと書き出す。`--check` を付けると、書き出す代わりに、いま生成した中身と
リポジトリにあるファイルを比べる。1 バイトも違わなければ終了コード 0、違えば 1 と差の要約を出す。

この道具は accord のモジュールを 1 つも読み込まない（正本の YAML を読んで文字列を組み立てるだけ）。
動かすのに要るのは標準ライブラリと PyYAML だけである。
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_PATH = REPO_ROOT / "src" / "accord" / "ontology.yaml"
TYPES_PATH = REPO_ROOT / "src" / "accord" / "models" / "types.py"
CONSTRAINTS_PATH = REPO_ROOT / "src" / "accord" / "models" / "constraints.py"

# 生成物の先頭に置く行。手で直しても次の生成で消えることを、ファイルを開いた人にまず伝える。
BANNER = "# 生成物。直すなら src/accord/ontology.yaml を直す"

# 正本の欄の型と、Python の型注釈の対応。
PYTHON_TYPES = {
    "text": "str",
    "date": "date",
    "text_list": "list[str]",
    "mapping": "list[dict[str, str]]",
    "flag": "bool",
}

# 必須でない欄の既定値。一覧の欄は None ではなく空の一覧にして、呼ぶ側の分岐を減らす。
OPTIONAL_DEFAULTS = {
    "text": ("str | None", "default=None"),
    "date": ("date | None", "default=None"),
    "text_list": ("list[str]", "default_factory=list"),
    "mapping": ("list[dict[str, str]]", "default_factory=list"),
    "flag": ("bool", "default=False"),
}


def py_str(value: str) -> str:
    """日本語をそのまま残したまま、Python の文字列リテラルにする。"""
    return json.dumps(str(value), ensure_ascii=False)


def load_ontology_document(path: Path) -> dict:
    """正本の YAML を読む。壊れていれば例外をそのまま上げる。"""
    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"正本の中身が辞書ではない: {path}")
    for key in ("types", "relations", "constraints"):
        if key not in document:
            raise ValueError(f"正本に '{key}' が無い: {path}")
    return document


def render_field(field: dict) -> str:
    """欄 1 つぶんの行（型注釈と Field の呼び出し）を組み立てる。"""
    kind = field.get("type", "text")
    if kind not in PYTHON_TYPES:
        raise ValueError(f"欄 '{field.get('name')}' の型 '{kind}' は正本の書式に無い")

    label = field.get("label", field["name"])
    note = field.get("description", "")
    caption = f"{label}。{note}" if note else f"{label}"

    if field.get("required", False):
        annotation = PYTHON_TYPES[kind]
        arguments = f"description={py_str(caption)}"
    else:
        annotation, default = OPTIONAL_DEFAULTS[kind]
        arguments = f"{default}, description={py_str(caption)}"

    return f"    {field['name']}: {annotation} = Field({arguments})"


def render_types(document: dict) -> str:
    """types.py の中身を組み立てる。"""
    types = document["types"]
    uses_date = any(
        field.get("type") == "date" for type_def in types for field in type_def["fields"]
    )

    lines = [
        BANNER,
        '"""accord の型の定義。',
        "",
        f"型は {len(types)} つで、正本 src/accord/ontology.yaml が",
        "挙げる型に 1 対 1 で対応する。欄の名前と必須の別は src/accord/ontology.yaml が持つ。",
        '"""',
        "",
        "from __future__ import annotations",
        "",
    ]
    if uses_date:
        lines += ["from datetime import date", ""]
    lines += ["from pydantic import BaseModel, Field", "", ""]

    for type_def in types:
        lines.append(f"class {type_def['name']}(BaseModel):")
        label = type_def.get("label", type_def["name"])
        note = type_def.get("description", "")
        lines.append(f'    """{label}。{note}"""' if note else f'    """{label}。"""')
        lines.append("")
        for field in type_def["fields"]:
            lines.append(render_field(field))
        lines.append("")
        lines.append("")

    # 末尾の空行 2 つを 1 つに詰めて、ファイルの終わりを改行 1 つで閉じる。
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def render_constraints(document: dict) -> str:
    """constraints.py の中身を組み立てる。"""
    constraints = document["constraints"]

    lines = [
        BANNER,
        '"""accord が執行する制約の宣言。',
        "",
        f"制約は {len(constraints)} つで、正本 src/accord/ontology.yaml が",
        "挙げる制約に 1 対 1 で対応する。サービスの実装も資源の定義も、この 1 か所を名前で参照する。",
        "同じ制約が、書きの操作では拒否、読みの操作では警告、検査の操作では一覧として現れる。",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from pydantic import BaseModel, ConfigDict",
        "",
        "",
        "class Constraint(BaseModel):",
        '    """制約 1 つの宣言。名前・見るもの・執行する操作・現れ方・次の一手を持つ。"""',
        "",
        "    model_config = ConfigDict(frozen=True)",
        "",
        "    name: str",
        "    watches: str",
        "    enforced_by: tuple[str, ...]",
        "    appears_as: str",
        "    next_action: str",
        "",
        "",
        "CONSTRAINTS: tuple[Constraint, ...] = (",
    ]

    for constraint in constraints:
        enforced_by = tuple(constraint.get("enforced_by") or ())
        if len(enforced_by) == 1:
            enforced = f"({py_str(enforced_by[0])},)"
        else:
            enforced = "(" + ", ".join(py_str(name) for name in enforced_by) + ")"
        lines += [
            "    Constraint(",
            f"        name={py_str(constraint['name'])},",
            f"        watches={py_str(constraint['watches'])},",
            f"        enforced_by={enforced},",
            f"        appears_as={py_str(constraint['appears_as'])},",
            f"        next_action={py_str(constraint['next_action'])},",
            "    ),",
        ]

    lines += [")", ""]
    return "\n".join(lines)


def diff_summary(expected: str, actual: str, path: Path) -> list[str]:
    """生成し直した中身と、リポジトリにある中身の差を、読める形にまとめる。"""
    diff = list(
        difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            fromfile=f"{path}（リポジトリ）",
            tofile=f"{path}（生成し直した結果）",
            lineterm="",
        )
    )
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    head = [f"{path}: 差がある（足りない行 {added}、余分な行 {removed}）"]
    return head + diff[:40]


def main(argv: list[str]) -> int:
    """書き出し、または `--check` での突き合わせを行う。"""
    parser = argparse.ArgumentParser(
        description="src/accord/ontology.yaml から型と制約の宣言を生成する"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="書き出さずに、生成し直した結果とリポジトリの生成物を比べる",
    )
    parser.add_argument(
        "--ontology",
        type=Path,
        default=ONTOLOGY_PATH,
        help="正本の YAML の場所（既定: src/accord/ontology.yaml）",
    )
    args = parser.parse_args(argv)

    try:
        document = load_ontology_document(args.ontology)
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"正本が読めない: {error}", file=sys.stderr)
        return 2

    try:
        rendered = {
            TYPES_PATH: render_types(document),
            CONSTRAINTS_PATH: render_constraints(document),
        }
    except (KeyError, ValueError) as error:
        print(f"正本の書式が正しくない: {error}", file=sys.stderr)
        return 2

    if args.check:
        differences: list[str] = []
        for path, expected in rendered.items():
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                differences.extend(diff_summary(expected, actual, path))
        if differences:
            print("\n".join(differences))
            print("生成物が正本と食い違っている。scripts/generate_models.py を引数なしで回す。")
            return 1
        print("生成物は正本と一致している。")
        return 0

    for path, expected in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
        print(f"書き出した: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

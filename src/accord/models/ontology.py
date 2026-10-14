"""型・関係・制約の正本 ontology.yaml を読み、資源 accord://ontology が返す形にする。

制約だけは YAML を読み直さず、生成物の CONSTRAINTS をそのまま載せる。制約の宣言は
1 か所（constraints.py）にあり、サービスの実装も資源もそこを読む、という決めに合わせるためである。
生成物と YAML が食い違っていないことは scripts/generate_models.py --check が見る。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from accord.models.constraints import CONSTRAINTS, Constraint

# 正本の置き場。このファイルから見て 1 つ上（src/accord/）に置く。
ONTOLOGY_PATH = Path(__file__).resolve().parent.parent / "ontology.yaml"

# 種類ごとに必須の欄が変わる型が持つ、種類の欄の名前。必須欄の判定はこの欄の値を見る。
KIND_FIELD = "kind"

# 欄の書き方の例を組み立てるときの、型ごとの見本。ontology.yaml が欄に書ける型の 5 つに対応する。
# 値そのものの例（媒体の名前、分類の名前）は語彙なので、ここには置かず語彙のファイルから取る。
FIELD_EXAMPLES = {
    "date": "2026-09-16",
    "text": "1 行の文",
    "text_list": "名前 / 名前",
    "mapping": "対象 — 理由",
    "flag": "true",
}


class OntologyField(BaseModel):
    """型が持つ欄 1 つの定義。"""

    name: str
    label: str
    type: str
    required: bool = False
    # 種類の欄（kind）がこの一覧の語のブロックでだけ必須になる欄。空なら種類によらない。
    required_for_kinds: list[str] = Field(default_factory=list)
    description: str = ""


class OntologyType(BaseModel):
    """型 1 つの定義。"""

    name: str
    label: str
    description: str = ""
    source: str = ""
    fields: list[OntologyField] = Field(default_factory=list)


class OntologyRelation(BaseModel):
    """関係 1 種の定義。相手の型が 2 つある関係は、辺を 2 本と数える。"""

    name: str
    from_type: str = Field(alias="from")
    to_types: list[str] = Field(alias="to")
    cardinality: str = ""
    description: str = ""

    model_config = {"populate_by_name": True}

    @property
    def edge_count(self) -> int:
        """この関係が持つ辺の本数。"""
        return len(self.to_types)


class Ontology(BaseModel):
    """資源 accord://ontology が返す中身。型・関係・制約の一覧を持つ。"""

    version: int = 1
    types: list[OntologyType] = Field(default_factory=list)
    relations: list[OntologyRelation] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)

    @property
    def relation_edge_count(self) -> int:
        """関係の辺の総数（種の数ではなく、本数）。"""
        # spec: REQ-330
        return sum(relation.edge_count for relation in self.relations)

    def type_named(self, name: str) -> OntologyType | None:
        """型の名前で定義を引く。欄の名前と必須の別は、どの層もここから取る。"""
        for entry in self.types:
            if entry.name == name:
                return entry
        return None


def load_ontology(path: Path | None = None) -> Ontology:
    """正本の YAML を読んで Ontology にする。path を省くと同梱の ontology.yaml を読む。"""
    source = path or ONTOLOGY_PATH
    with source.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    return Ontology(
        version=document.get("version", 1),
        # spec: REQ-327
        types=[OntologyType.model_validate(entry) for entry in document.get("types", [])],
        # spec: REQ-328
        relations=[
            OntologyRelation.model_validate(entry) for entry in document.get("relations", [])
        ],
        # spec: REQ-329
        constraints=list(CONSTRAINTS),
    )


def missing_required_fields(type_name: str, draft: object) -> list[OntologyField]:
    """型の正本が必須と定める欄のうち、入力が持っていない（または空の）ものを返す。

    種類によって必須かどうかが変わる欄（required_for_kinds）は、入力の種類の欄（kind）が
    その一覧の語のときだけ必須として見る。

    書きの操作が「欠けた欄」を数えるための 1 か所である。欄の名前を操作の側に書き写すと、
    正本の欄を直したときに、片方だけが古いまま残る。
    入力がその欄を持たないとき（操作の側が値を決める最終更新日など）は、見に行かない。
    """
    entry = load_ontology().type_named(type_name)
    if entry is None:
        return []

    kind = getattr(draft, KIND_FIELD, None)
    missing: list[OntologyField] = []
    for field in entry.fields:
        # spec: REQ-376
        required = field.required or (
            bool(field.required_for_kinds) and kind in field.required_for_kinds
        )
        if not required or not hasattr(draft, field.name):
            continue
        value = getattr(draft, field.name)
        if value is None:
            missing.append(field)
        elif isinstance(value, str) and not value.strip():
            missing.append(field)
        elif isinstance(value, (list, tuple, dict)) and not value:
            missing.append(field)
    return missing


def field_example(field: OntologyField) -> str:
    """欄 1 つの書き方の例を、型の正本の欄の定義から組み立てる。

    例を手で書くと、正本の欄を直したときに例だけが古いまま残る。だから型と説明から作る。
    """
    sample = FIELD_EXAMPLES.get(field.type, field.type)
    description = f"（{field.description}）" if field.description else ""
    return f"- {field.label}: {sample}{description}"

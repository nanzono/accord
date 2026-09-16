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


class OntologyField(BaseModel):
    """型が持つ欄 1 つの定義。"""

    name: str
    label: str
    type: str
    required: bool = False
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
        return sum(relation.edge_count for relation in self.relations)


def load_ontology(path: Path | None = None) -> Ontology:
    """正本の YAML を読んで Ontology にする。path を省くと同梱の ontology.yaml を読む。"""
    source = path or ONTOLOGY_PATH
    with source.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    return Ontology(
        version=document.get("version", 1),
        types=[OntologyType.model_validate(entry) for entry in document.get("types", [])],
        relations=[
            OntologyRelation.model_validate(entry) for entry in document.get("relations", [])
        ],
        constraints=list(CONSTRAINTS),
    )

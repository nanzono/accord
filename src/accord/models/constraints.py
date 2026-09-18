# 生成物。直すなら src/accord/ontology.yaml を直す
"""accord が執行する制約の宣言。

制約は 11 つで、正本 src/accord/ontology.yaml が
挙げる制約に 1 対 1 で対応する。サービスの実装も資源の定義も、この 1 か所を名前で参照する。
同じ制約が、書きの操作では拒否、読みの操作では警告、検査の操作では一覧として現れる。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Constraint(BaseModel):
    """制約 1 つの宣言。名前・見るもの・執行する操作・現れ方・次の一手を持つ。"""

    model_config = ConfigDict(frozen=True)

    name: str
    watches: str
    enforced_by: tuple[str, ...]
    appears_as: str
    next_action: str


CONSTRAINTS: tuple[Constraint, ...] = (
    Constraint(
        name="決めの必須欄",
        watches="売り方の決めに、日付・適用範囲・前面に出す束・根拠の 4 欄が揃っているか。",
        enforced_by=("record_positioning",),
        appears_as="拒否",
        next_action="欠けた欄の名前と、その欄の書き方の例を返す。",
    ),
    Constraint(
        name="パッケージ定義の鮮度",
        watches="パッケージ定義の最終更新が、適用される決めの日付より古くないか。",
        enforced_by=("record_positioning", "check_consistency"),
        appears_as="検出",
        next_action="定義ファイルの名前と、決めの日付と最終更新日の両方を返す。",
    ),
    Constraint(
        name="提示物の宣言と看板の一致",
        watches="提示物が宣言する束が、適用される決めの前面に出す束と一致するか。決めの例外欄に書いた提示物は見ない。",
        enforced_by=("record_positioning", "check_consistency"),
        appears_as="検出",
        next_action="提示物のファイル名と、いまの看板のパッケージ名を返す。",
    ),
    Constraint(
        name="裏づけ節名の実在",
        watches="機能の裏づけの節名が、職歴の枠か受託案件の見出しか、公開記録の名前として実在するか。",
        enforced_by=("register_capability", "check_consistency"),
        appears_as="拒否",
        next_action="実在する見出しのうち、近いものを候補として返す。",
    ),
    Constraint(
        name="束ねる機能名の一致",
        watches="パッケージが束ねる機能名が、機能の台帳にあるか。",
        enforced_by=("revise_package", "check_consistency"),
        appears_as="拒否",
        next_action="近い機能名の候補と、先に register_capability を呼ぶことを返す。",
    ),
    Constraint(
        name="注記と出典の節の実在・公開可否",
        watches="提示物の未反映の注記が指す節と、職務経歴書の台帳の出典の節が実在し、公開可の節に限るか。",
        enforced_by=("check_consistency", "assemble_material"),
        appears_as="検出",
        next_action="実在する節の候補を返す。公開不可の節は材料から落とし、落とした節の名前を警告に書く。",
    ),
    Constraint(
        name="公開記録の必須欄",
        watches="公開記録に、名前・種類・日付・発行元か主催・役割の 5 欄が揃っているか。",
        enforced_by=("register_public_record",),
        appears_as="拒否",
        next_action="欠けた欄の名前と、その欄の書き方の例を返す。",
    ),
    Constraint(
        name="公開記録の種類と役割の語彙",
        watches="公開記録の種類と役割が、設定ファイルが持つ語の一覧にあるか。",
        enforced_by=("register_public_record",),
        appears_as="拒否",
        next_action="設定が持つ語の一覧を返す。",
    ),
    Constraint(
        name="由来の節の実在",
        watches="公開記録の由来の節が、職歴の枠か受託案件の見出しとして実在するか。",
        enforced_by=("register_public_record", "check_consistency"),
        appears_as="拒否",
        next_action="実在する見出しのうち、近いものを候補として返す。",
    ),
    Constraint(
        name="提示物の URL と公開記録の一致",
        watches="提示物の本文に貼った URL が、正本の公開記録の URL にあるか。経路の書き方だけが違うものも見る。",
        enforced_by=("check_consistency",),
        appears_as="検出",
        next_action="提示物のファイル名と、正本にある近い URL を返す。経路の書き方だけが違うものは、相手の URL を 1 件返す。",
    ),
    Constraint(
        name="逆参照を書かない",
        watches="下の層の正本が上の層を指さないこと。事実の節がパッケージや決めを指す書き方を正本に入れない。",
        enforced_by=(),
        appears_as="構造",
        next_action="参照は上の層から下の層へ 1 方向で書く。逆に辿りたいときは検査の操作で数える。",
    ),
)

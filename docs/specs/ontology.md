# 型とルールの定義と起動の口

accord が扱うデータの種類（型）と、型どうしのつながり（関係）と、守らせる決まり（ルール）は、
`src/accord/ontology.yaml` の 1 ファイルに定めてあります。このファイルが定義の正本です。

Python の型のコードとルールの宣言は、この正本から生成します。生成物を手で直すと、正本と食い違った
まま動いてしまうので、生成し直した中身と 1 バイトも違わないことを突き合わせで確かめます。

AI が accord を使い始めるときは、まず資源 `accord://ontology` を読みます。返るのは、正本に定めた
型と関係とルールの一覧です。読んだ側は、この一覧だけで、どの型がどの型を指せるか、どのルールが
どこで効くかが分かります。

指される側の 5 つの型が ID の欄を必須で持つことも、この正本が定めます。ID の形と一意性、
指された値が読めないときの言い分けは [id-reference.md](id-reference.md) にあります。

このファイルは、正本が定める ID の欄と、資源が返すものと、正本とコードの結び付きと、起動した
accord が開く口の顔ぶれを述べます。ルールが 1 件ずつ何を見て何を返すかは、このファイルではなく
機能ごとの要件のファイルが持ちます。要件の書き方と番号の決まりは [README.md](README.md) に
あります。

## REQ-326
常に、accord は職歴の枠と受託案件と公開記録と機能とパッケージの型に、ID の欄を必須で持たせる。

- 関係するファイル: `src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_326`

## REQ-327
資源 `accord://ontology` を読まれたとき、accord は型の正本が挙げる型をすべて返す。

- 関係するファイル: `src/accord/models/ontology.py`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_327`

## REQ-328
資源 `accord://ontology` を読まれたとき、accord は型の正本が挙げる関係をすべて返す。

- 関係するファイル: `src/accord/models/ontology.py`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_328`

## REQ-329
資源 `accord://ontology` を読まれたとき、accord は型の正本が挙げる制約をすべて返す。

- 関係するファイル: `src/accord/models/ontology.py`、`src/accord/models/constraints.py`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_329`

## REQ-330
常に、accord は相手の型を 2 つ以上持つ関係を、相手の型 1 つにつき 1 本の矢印として数える。

- 関係するファイル: `src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_330`

## REQ-331
生成物と型の正本の突き合わせを求められたとき、accord は 1 バイトも違わない生成物を合格として終える。

- 関係するファイル: `scripts/generate_models.py`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_331`

## REQ-332
もし生成物が型の正本から作り直した中身と違うなら、accord は違うファイルの名前と差の要約を添えて、その突き合わせを不合格として終える。

- 関係するファイル: `scripts/generate_models.py`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_332`

## REQ-333
常に、accord は型の正本が挙げるルールのそれぞれを、そのルールが宣言した操作で効かせる。

- 関係するファイル: `src/accord/services/consistency.py`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_333`

## REQ-334
常に、accord はルールが宣言した操作のそれぞれに、そのルールを効かせる手を 1 つ以上持つ。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_334`

## REQ-335
常に、accord は型の正本に無いルールと操作を、効かせる先の一覧に残さない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_ontology.py -k REQ_335`

## REQ-336
起動されたとき、accord は決めを読む・材料を取り出す・決めを登記する・機能を登記する・公開記録を登記する・パッケージを改訂する・整合を検査するの 7 つの操作を開く。

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_336`

## REQ-337
起動されたとき、accord は型とルールの定義を返す資源を 1 本だけ開く。

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_337`

## REQ-338
開く口の一覧を求められたとき、accord は終了コード 0 で終わる。

- 関係するファイル: `src/accord/__main__.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_338`

## REQ-339
開く口の一覧を求められたとき、accord は起動したサーバーが開く操作と資源の名前をすべて出す。

- 関係するファイル: `src/accord/__main__.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_339`

## REQ-340
開く口の一覧を求められたとき、accord は同じ名前を 2 度出さない。

- 関係するファイル: `src/accord/__main__.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_340`

## 未決の質問

- 資源が制約をどこから取るかは、要件の文からは決まりません。いまの実装は正本の YAML を読み直さず、
  生成物の宣言をそのまま載せます。生成物を作り直し忘れたまま資源を読んだときに何が返るかは、
  この文からは 2 通りに書けます。両者が同じ中身を返すことは、生成物と正本の突き合わせを述べた
  2 件が支えているので、実害はありません。

- 起動して開く操作の要件だけが顔ぶれを並べ、ほかの 14 件は数も顔ぶれも書きません。操作が増える
  ことは accord の振る舞いが変わることそのものなので、そこだけは新しい番号を振る形にそろえて
  います。この不揃いに理由を見つけられるかは、この前書きの書き方しだいです。

- 型の正本の件数が変わると、件数を手で書いたテストの定数が落ちます。落ちたときに要件も直すのか、
  定数だけを直せばよいのかは、要件の側からは読めません。

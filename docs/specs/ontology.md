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
accord が開く口の顔ぶれを述べます。語彙（置き場の `vocabulary.md` の 6 つの種類と語）を変える 2 つの操作
（語彙に語を足す・語彙から語を消す）の要件もここに置きます。語が「使われている」かは、整合の検査が語彙と
照らしている欄（売り方の決めの適用範囲、機能の台帳の分類の節の見出し、パッケージ定義の仮説の状態、公開記録の
種類と役割）だけで見ます。媒体の語は、提示物の置き場に同じ名前のディレクトリがあるときも使われていると見ます。ルールが 1 件ずつ何を見て何を返すかは、このファイルではなく
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
- status: superseded by REQ-462

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

## REQ-462
起動されたとき、accord は決めを読む・材料を取り出す・決めを登記する・機能を登記する・公開記録を登記する・パッケージを改訂する・整合を検査する・節を一覧する・節を読む・事実を検索する・事実を登記する・節を書き換える・書き出すの 13 の操作を開く。

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_462`
- status: superseded by REQ-489

## REQ-463
起動されたとき、accord はサーバーの説明に、正本のファイルを直接開かずに accord の操作で読み書きすることを書く。

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_463`

## REQ-464
起動されたとき、accord は材料の取り出しの説明に、応募文とプロフィールと職務経歴書を書く前に呼ぶ操作であることを書く。

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_464`

## REQ-465
起動されたとき、accord は事実の登記の説明に、実績と経歴の事実を書き足すときに呼ぶ操作であることを書く。

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_465`

## REQ-489
起動されたとき、accord は決めを読む・材料を取り出す・決めを登記する・機能を登記する・公開記録を登記する・パッケージを改訂する・整合を検査する・節を一覧する・節を読む・事実を検索する・事実を登記する・節を書き換える・見出しを変える・節を足す・節を消す・節を動かす・公開可否を変える・書き出すの 18 の操作を開く。（REQ-462 に取って代わる）

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_489`
- status: superseded by REQ-549

## REQ-549
起動されたとき、accord は REQ-489 の 18 の操作に移行の操作を加えた 19 の操作を開く。

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_549`
- status: superseded by REQ-526

## REQ-508
語彙の種類と語と理由を渡されて語彙に語を足すとき、accord は vocabulary.md のその種類の節の末尾に語を 1 行足す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_vocabulary_terms.py -k REQ_508`

## REQ-509
もし足す語がその種類に既にあるか、空か、改行を含むなら、accord は書かずに、その種類のいまの語の一覧を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_vocabulary_terms.py -k REQ_509`

## REQ-510
語彙の種類と語と理由を渡されて語彙から語を消すとき、accord はその種類の節からその語の行を消す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_vocabulary_terms.py -k REQ_510`

## REQ-511
もし消す語を正本のどこかの節が使っているなら、accord は書かずに、使っている節の道筋を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_vocabulary_terms.py -k REQ_511`

## REQ-512
もし渡された語彙の種類が、媒体・決めの適用先・機能の分類・パッケージの仮説の状態・公開記録の種類・公開記録の役割の 6 つのどれでもないなら、accord は書かずに、6 つの種類の名前を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_vocabulary_terms.py -k REQ_512`

## REQ-542
もし語彙から消す語がその種類に無いなら、accord は書かずに、その種類のいまの語の一覧を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_vocabulary_terms.py -k REQ_542`

## REQ-554
もし語彙から消す媒体の語と同じ名前のディレクトリが提示物の置き場にあるなら、accord は書かずに、そのディレクトリの名前を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_vocabulary_terms.py -k REQ_554`

## REQ-526
起動されたとき、accord は決めを読む・材料を取り出す・決めを登記する・機能を登記する・公開記録を登記する・パッケージを改訂する・整合を検査する・節を一覧する・節を読む・事実を検索する・事実を登記する・節を書き換える・見出しを変える・節を足す・節を消す・節を動かす・公開可否を変える・書き出す・語彙に語を足す・語彙から語を消す・コミットを取り消す・未コミットの変更を捨てる・移行するの 23 の操作を開く。（REQ-549 に取って代わる）

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_526`

## REQ-527
起動されたとき、accord はサーバーの説明に、語彙の変更と取り消しと未コミットの変更を捨てることと移行も accord の操作で行い、置き場のファイルを直接書かないことを書く。

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_527`

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

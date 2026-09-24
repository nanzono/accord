# 説明書と定義の一致

リポジトリの直下の `README.md` には、accord が扱うデータの型とルールを一望する節と、自分のデータで
動かすときの起動のしかたを書いた節があります。このファイルは、その 2 つの節が定義の正本と食い違わ
ないことを述べます。

止めたい失敗は 2 つです。1 つは、定義の正本を直したときに説明書だけが古いまま残ることです。型を
1 つ足して図に描き忘れると、説明書を読んだ人は「accord はその型を扱わない」と読みます。もう 1 つは、
版を固定する起動だけを案内してしまうことです。その起動は版を上げないかぎり前の版が動き続けるので、
読んだ人は古いコードが返した結果を正本の不備と読み、正しい正本を直しにかかります。

説明書の文章は人が書き、直したかどうかは機械が見ます。数も、図のノードも、表の行も、手で書いた
期待値とではなく、定義の正本から数えた値と突き合わせます。その突き合わせ自体が効いていることは、
わざと 1 行壊した文面を同じ関数に渡して確かめています。

要件の書き方と番号の決まりは [README.md](README.md) にあります。型とルールの定義そのものは
[ontology.md](ontology.md) が持ちます。

## REQ-341
常に、accord は説明書の型とルールの節に、型の正本が挙げる型の数を書く。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_341`

## REQ-342
常に、accord は説明書の型とルールの節に、型の正本が挙げる関係の数を書く。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_342`

## REQ-343
常に、accord は説明書の型とルールの節に、関係を相手の型ごとに展開した矢印の数を書く。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_343`

## REQ-344
常に、accord は説明書の型とルールの節に、型の正本が挙げる制約の数を書く。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_344`

## REQ-345
常に、accord は説明書の型とルールの節に図を 1 つだけ置く。

- 関係するファイル: `README.md`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_345`

## REQ-346
常に、accord は説明書の図に、型の正本が挙げる型をすべてノードとして置く。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_346`

## REQ-347
常に、accord は説明書の図に、型の正本に無いノードを置かない。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_347`

## REQ-348
常に、accord は説明書の図のノードの表示名を、型の正本のその型の表示名と同じにする。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_348`

## REQ-349
常に、accord は説明書の図に、関係を相手の型ごとに展開した矢印をすべて置く。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_349`

## REQ-350
常に、accord は説明書の図に、型の正本に無い矢印を置かない。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_350`

## REQ-351
常に、accord は説明書の型の表に、型の正本が挙げる型の表示名を 1 列目に持つ行をそれぞれ置く。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_351`

## REQ-352
常に、accord は説明書のルールの表に、型の正本が挙げる制約の名前を 1 列目に持つ行をそれぞれ置く。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_352`

## REQ-353
常に、accord は説明書のルールの表の制約の行に、型の正本のその制約の現れ方の語を書く。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_353`

## REQ-354
常に、accord は説明書の図を画像にしたものを同梱する。

- 関係するファイル: `docs/ontology.svg`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_354`

## REQ-355
常に、accord はその画像に、型の正本が挙げる型の表示名をすべて入れる。

- 関係するファイル: `docs/ontology.svg`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_355`

## REQ-356
常に、accord はその画像に、型の正本が挙げる関係の名前をすべて入れる。

- 関係するファイル: `docs/ontology.svg`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_356`

## REQ-357
常に、accord は説明書の起動の節に、AI から呼ぶときの設定の例を置く。

- 関係するファイル: `README.md`
- 検証手順: `uv run pytest tests/test_readme_startup.py -k REQ_357`

## REQ-358
常に、accord はその設定の例の起動を、指した場所のソースをそのまま動かす形にする。

- 関係するファイル: `README.md`
- 検証手順: `uv run pytest tests/test_readme_startup.py -k REQ_358`

## REQ-359
常に、accord は説明書の起動の節に、指した場所のソースをそのまま動かす起動の書き方を置く。

- 関係するファイル: `README.md`
- 検証手順: `uv run pytest tests/test_readme_startup.py -k REQ_359`

## REQ-360
常に、accord は説明書の起動の節に、版を固定して入れて使う起動の書き方を置く。

- 関係するファイル: `README.md`
- 検証手順: `uv run pytest tests/test_readme_startup.py -k REQ_360`

## REQ-361
説明書の起動の節が版を固定して入れて使う起動を案内するとき、accord は版を上げないと前の版が動き続けることを同じ節に書く。

- 関係するファイル: `README.md`
- 検証手順: `uv run pytest tests/test_readme_startup.py -k REQ_361`

## REQ-372
常に、accord は説明書のルールの表に、型の正本に無い制約の名前を 1 列目に持つ行を置かない。

- 関係するファイル: `README.md`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_readme_ontology.py -k REQ_372`

## 未決の質問

- 数をどう書くかは、要件の文からは決まりません。いまの突き合わせは決まった 4 つの書き方で数を
  探すので、同じ数でも別の言い回しで書くと違いが返ります。数がどこかに書いてあればよいと読むか、
  いまの書き方のままと読むかで、実装が 2 通りに分かれます。

- 設定の例の「指した場所のソースをそのまま動かす形」が、どの書き方までを指すかは決まりません。
  いまの突き合わせは、起動のコマンドと引数の先頭 2 つだけを見ます。同じことを果たす別の書き方
  （作業ディレクトリを移してから呼ぶ形）は、いまの突き合わせでは違いとして返ります。

- 図の突き合わせは、説明書の節の中の図と、同梱した画像を別々に見ます。この 2 つが互いに同じ図で
  あることは、どちらの要件も述べていません。画像を別の図に差し替えても、型の表示名と関係の名前が
  そろっていれば通ります。

# 公開記録の登記

公開記録を 1 件登記する操作の要件です。公開記録は、リポジトリ・登壇・記事・書籍・第三者の掲載のように、本人の申告ではなく外から確かめられる成果物 1 件です。提示物の本文に貼った URL が正本のどこにも無い、という食い違いを止めるために、URL を持つ事実として正本に置きます。

この操作は、守るべきことを先に全部確かめ、通ると決まってから 1 度だけ正本の末尾に 1 ブロック足します。すでにある公開記録は書き換えません。通らなかったときは、何が通らなかったかと、次に何を渡せば通るかを返します。

受け付ける語（種類と役割）は設定ファイルが持ちます。語を変えるのに、この道具を作り直す必要はありません。公開記録の置き場も設定ファイルが持ち、置き場を書いていない正本では、書き足す先が決まらないことを足す鍵の名前つきで断ります。

ID の形式と一意性の断りは、この操作も他の書きの操作と同じ判定を使います。その断りの中身を述べる要件はこのファイルにありません（制約を見る順の要件に、順の 1 つとして名前だけが出ます）。

要件の書き方と番号の決まりは [README.md](README.md) にあります。

## REQ-207
通る入力を渡されたとき、accord は公開記録を正本の末尾に 1 ブロック足す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_207`

## REQ-208
通る入力を渡されたとき、accord は正本にすでにある公開記録を書き換えない。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_208`

## REQ-209
公開記録の登記が通ったとき、accord は登記した公開記録を返り値に入れる。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_209`

## REQ-210
URL を渡されないとき、accord はその公開記録を登記する。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_210`

## REQ-211
URL を渡されないとき、accord は URL を持たないことを正本に書く。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_211`

## REQ-212
URL を空を表す語で渡されたとき、accord はその公開記録を URL を持たないものとして登記する。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_212`

## REQ-213
由来の節を渡されないとき、accord は由来の節を確かめずにその公開記録を登記する。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_213`

## REQ-214
もし設定ファイルに公開記録の置き場が無いなら、accord はその公開記録を登記しない。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_214`

## REQ-215
もし設定ファイルに公開記録の置き場が無いなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_215`

## REQ-216
もし設定ファイルに公開記録の置き場が無いなら、accord は設定ファイルの名前と、書き足す先が決まらないことを断りの理由に書く。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_216`

## REQ-217
もし設定ファイルに公開記録の置き場が無いなら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_217`

## REQ-218
もし設定ファイルに公開記録の置き場が無いなら、accord は設定ファイルに足す 3 つの鍵の名前を含む書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_218`

## REQ-219
もし公開記録の必須の欄が空なら、accord はその公開記録を登記しない。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_219`

## REQ-220
もし公開記録の必須の欄が空なら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_220`

## REQ-221
もし公開記録の必須の欄が空なら、accord は欠けた欄の名前を断りの理由に書く。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_221`

## REQ-222
もし公開記録の必須の欄が空なら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_222`

## REQ-223
もし公開記録の必須の欄が空なら、accord は欠けた欄の名前の一覧を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_223`

## REQ-224
もし公開記録の必須の欄が空なら、accord は欠けた欄の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_224`

## REQ-225
もし公開記録の種類が設定ファイルの種類の語の一覧に無いなら、accord はその公開記録を登記しない。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_225`

## REQ-226
もし公開記録の種類が設定ファイルの種類の語の一覧に無いなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_226`

## REQ-227
もし公開記録の種類が設定ファイルの種類の語の一覧に無いなら、accord は渡された種類と、設定ファイルの鍵の名前を断りの理由に書く。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_227`

## REQ-228
もし公開記録の種類が設定ファイルの種類の語の一覧に無いなら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_228`

## REQ-229
もし公開記録の種類が設定ファイルの種類の語の一覧に無いなら、accord は設定ファイルの種類の語をすべて断りの候補に返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_229`

## REQ-230
もし公開記録の種類が設定ファイルの種類の語の一覧に無いなら、accord は種類の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_230`

## REQ-231
もし公開記録の役割が設定ファイルの役割の語の一覧に無いなら、accord はその公開記録を登記しない。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_231`

## REQ-232
もし公開記録の役割が設定ファイルの役割の語の一覧に無いなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_232`

## REQ-233
もし公開記録の役割が設定ファイルの役割の語の一覧に無いなら、accord は渡された役割と、設定ファイルの鍵の名前を断りの理由に書く。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_233`

## REQ-234
もし公開記録の役割が設定ファイルの役割の語の一覧に無いなら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_234`

## REQ-235
もし公開記録の役割が設定ファイルの役割の語の一覧に無いなら、accord は設定ファイルの役割の語をすべて断りの候補に返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_235`

## REQ-236
もし公開記録の役割が設定ファイルの役割の語の一覧に無いなら、accord は役割の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_236`

## REQ-237
もし公開記録の由来の節が職歴の枠にも受託案件にも無い ID なら、accord はその公開記録を登記しない。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_237`

## REQ-238
もし公開記録の由来の節が職歴の枠にも受託案件にも無い ID なら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_238`

## REQ-239
もし公開記録の由来の節が職歴の枠にも受託案件にも無い ID なら、accord はその ID がどちらにも無いことを断りの理由に書く。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_239`

## REQ-240
もし公開記録の由来の節が ID の形に合わないなら、accord は ID の形と、見出しをその節の ID に置き換えることを断りの理由に書く。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_240`

## REQ-241
もし公開記録の由来の節が職歴の枠にも受託案件にも無い ID なら、accord は候補の表示名を断りの理由に書く。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_241`

## REQ-242
もし公開記録の由来の節が職歴の枠にも受託案件にも無い ID なら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_242`

## REQ-243
もし公開記録の由来の節が職歴の枠にも受託案件にも無い ID なら、accord は職歴の枠と受託案件にある近い ID を断りの候補に返す。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_243`

## REQ-244
もし公開記録の由来の節が職歴の枠にも受託案件にも無い ID なら、accord は由来の節の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_244`

## REQ-246
もし公開記録の登記で 2 つ以上の制約が同時に外れているなら、accord は置き場・必須の欄・ID の形と重なり・種類・役割・由来の節の順で先に当たった 1 件だけを断りに返す。

- 関係するファイル: `src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_public_records.py -k REQ_246`

## 未決の質問

- 公開記録の URL を空を表す語で渡したとき（REQ-212）、どの語を空とみなすかを決めていません。いまの実装は、正本の読み書きが持つ 4 語（「なし」「無し」「-」「—」）をすべて空として読みます。要件の文は「空を表す語」としか書いていないので、この 4 語のうち一部だけを空とする実装も書けます。語の一覧を要件で固定するなら、正本の読み方の設定の要件（[reading-settings.md](reading-settings.md)）の側に置くほうが筋です。
- 制約を見る順の要件（REQ-246）は、ID の形と重なりを順の 1 つとして名前で挙げますが、その断りの中身を述べる要件はまだどの要件のファイルにもありません。この順を確かめるテストが、ID の断りが返ったことをどこまで確かめるか（返ったことだけを見るか、制約の名前まで見るか）を決めていません。
  - この断りの中身は、ID で結ぶことの要件 REQ-305〜318 で決まりました（形に合わない ID と、すでに使われている ID の 2 通りを、3 つの書きの操作で共通に断ります）。

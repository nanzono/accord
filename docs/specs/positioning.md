# 決めの読み書き

いま何を前面に出すかの決めを読む操作と、決めを 1 件登記する操作の要件です。読む操作は、媒体向けの文面を書く前と、整合の検査や文面の材料の取り出しの中から呼ばれ、いまの看板になる決め 1 件と、その決めが前面に出す束のパッケージと、警告の一覧を返します。

どの決めが当たるかの選び方は 1 つです。媒体の名前を渡されたら、その媒体を適用範囲に名指しした決めのうちいちばん新しい 1 件。名指しした決めが 1 件も無ければ、適用範囲「全体」の決めのうちいちばん新しい 1 件です。媒体を省いて呼ばれたときは、はじめから「全体」の決めを見ます。

読む操作は正本を書き換えません。決めが 1 件も登記されていないときも、媒体の名前が実在しないときも、当たる決めが無いときも、拒否ではなく警告で返します。読む側が次に何をすれば決めが返るようになるかを、警告の中で名前つきで伝えます。

登記する操作は、守るべきことを先に全部確かめ、通ると決まってから 1 度だけ正本の末尾に書きます。通らなかったときは、何が通らなかったかと、次に何を渡せば通るかを返します。

要件の書き方と番号の決まりは [README.md](README.md) にあります。

## REQ-157
媒体を省いて呼ばれたとき、accord は適用範囲「全体」の決めのうちいちばん新しい 1 件を返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_157`

## REQ-158
媒体の名前を渡されたとき、accord はその媒体を適用範囲に名指しした決めのうちいちばん新しい 1 件を返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_158`

## REQ-159
決めを返すとき、accord はその決めが前面に出す束のパッケージを添えて返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_159`

## REQ-160
同じ日付の決めが並ぶとき、accord は正本の後ろにあるブロックを新しいほうとして返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_160`

## REQ-161
常に、accord は決めを読む操作で正本のファイルを 1 バイトも書き換えない。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_161`

## REQ-162
渡された媒体を適用範囲に名指しした決めが 1 件も無いとき、accord は適用範囲「全体」の決めのうちいちばん新しい 1 件を返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_162`

## REQ-163
渡された媒体を適用範囲に名指しした決めが 1 件も無いとき、accord は適用範囲「全体」の決めを返したことを、その媒体の名前を添えて警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_163`

## REQ-164
もし決めが 1 件も登記されていないなら、accord は決めもパッケージも返さない。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_164`

## REQ-165
もし決めが 1 件も登記されていないなら、accord は決めが未登記であることを警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_165`

## REQ-166
もし決めが 1 件も登記されていないなら、accord は決めを登記する操作の名前を警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_166`

## REQ-167
もし決めが 1 件も登記されていないなら、accord は決めの入力の欄の名前と必須の別を警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_167`

## REQ-168
もし渡された媒体の名前が設定ファイルの媒体の一覧に無いなら、accord は決めもパッケージも返さない。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_168`

## REQ-169
もし渡された媒体の名前が設定ファイルの媒体の一覧に無いなら、accord はその媒体が一覧に無いことを、設定ファイルの名前を添えて警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_169`

## REQ-170
もし渡された媒体の名前が設定ファイルの媒体の一覧に無いなら、accord は実在する媒体の名前をすべて警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_170`

## REQ-171
もし渡された媒体の名前が設定ファイルの媒体の一覧に無いなら、accord は次に呼ぶ操作の名前を警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_171`

## REQ-172
もし渡された媒体の名前が設定ファイルの媒体の一覧に無いなら、accord は媒体を省いて呼べば適用範囲「全体」の決めが返ることを警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_172`

## REQ-173
もし渡された媒体にも適用範囲「全体」にも当たる決めが無いなら、accord は決めもパッケージも返さない。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_173`

## REQ-174
もし渡された媒体にも適用範囲「全体」にも当たる決めが無いなら、accord は登記されている決めの適用範囲を、重ねずにすべて警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_174`

## REQ-175
もし渡された媒体にも適用範囲「全体」にも当たる決めが無いなら、accord は決めを登記する操作の名前と入力の欄を警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_175`

## REQ-176
もし登記されている決めが前面に出す束がパッケージ定義に無い ID なら、accord は決めを読む操作でパッケージを返さない。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_176`

## REQ-177
もし登記されている決めが前面に出す束がパッケージ定義に無い ID なら、accord は実在する束の ID を表示名とともに警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_177`

## REQ-178
もし登記されている決めが前面に出す束がパッケージ定義に無い ID なら、accord は決めを登記し直す操作の名前を警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_178`

## REQ-179
通る入力を渡されたとき、accord は決めを正本の末尾に 1 ブロック足す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_179`

## REQ-180
決めの登記が通ったとき、accord は登記した決めを返り値に入れる。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_180`

## REQ-181
決めの登記が通ったとき、accord はパッケージ定義の鮮度の違反を返り値に入れる。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_181`

## REQ-182
パッケージ定義の鮮度の違反が 1 件も無いとき、accord は定義の最終更新がその決めの日付より古くないことを返り値に書く。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_182`

## REQ-183
決めの登記が通ったとき、accord は旧い束を宣言したままの提示物の件数を返り値に入れる。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_183`

## REQ-184
決めの登記が通ったとき、accord は旧い束を宣言したままの提示物のファイル名を返り値に入れる。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_184`

## REQ-185
決めの登記が通ったとき、accord は登記の後に走った 2 つの検査が見つけた違反を警告に返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_185`

## REQ-186
根拠に改行を含む決めを登記されたとき、accord は読み直しても同じ文字列を返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_186`

## REQ-187
断りで返した候補をそのまま前面に出す束に渡し直されたとき、accord はその決めを登記する。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_187`

## REQ-188
もし決めの必須の欄が空なら、accord はその決めを登記しない。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_188`

## REQ-189
もし決めの必須の欄が空なら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_189`

## REQ-190
もし決めの必須の欄が空なら、accord は欠けた欄の名前を断りの理由に書く。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_190`

## REQ-191
もし決めの必須の欄が空なら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_191`

## REQ-192
もし決めの必須の欄が空なら、accord は欠けた欄の名前の一覧を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_192`

## REQ-193
もし決めの必須の欄が空なら、accord は欠けた欄の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_193`

## REQ-194
もし決めの適用範囲が媒体の名前でも「全体」でもないなら、accord はその決めを登記しない。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_194`

## REQ-195
もし決めの適用範囲が媒体の名前でも「全体」でもないなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_195`

## REQ-196
もし決めの適用範囲が媒体の名前でも「全体」でもないなら、accord は渡された適用範囲と、媒体の名前が設定ファイルの一覧に限ることを断りの理由に書く。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_196`

## REQ-197
もし決めの適用範囲が媒体の名前でも「全体」でもないなら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_197`

## REQ-198
もし決めの適用範囲が媒体の名前でも「全体」でもないなら、accord は「全体」と設定ファイルの媒体の名前を断りの候補に返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_198`

## REQ-199
もし決めの適用範囲が媒体の名前でも「全体」でもないなら、accord は適用範囲の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_199`

## REQ-200
もし登記する決めが前面に出す束がパッケージ定義に無い ID なら、accord はその決めを登記しない。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_200`

## REQ-201
もし登記する決めが前面に出す束がパッケージ定義に無い ID なら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_201`

## REQ-202
もし登記する決めが前面に出す束がパッケージ定義に無い ID なら、accord は渡された ID を断りの理由に書く。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_202`

## REQ-203
もし登記する決めが前面に出す束がパッケージ定義に無い ID なら、accord は候補の表示名を断りの理由に書く。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_203`

## REQ-204
もし登記する決めが前面に出す束がパッケージ定義に無い ID なら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_204`

## REQ-205
もし登記する決めが前面に出す束がパッケージ定義に無い ID なら、accord はパッケージ定義にある近い ID を断りの候補に返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_205`

## REQ-206
もし登記する決めが前面に出す束がパッケージ定義に無い ID なら、accord は前面に出す束の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_206`

## REQ-245
もし決めの登記で 2 つ以上の制約が同時に外れているなら、accord は必須の欄・適用範囲・前面に出す束の順で先に当たった 1 件だけを断りに返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_245`

## 未決の質問

- 同じ日付・同じ適用範囲の決めが 3 件以上並んだときの順序を決めていません（REQ-160）。いまの実装は、正本の並びのいちばん後ろにあるブロックを新しいものとして返します。要件の文は「後ろにあるブロックを新しいほう」としか書いていないので、2 件のときだけを見る実装も書けます。

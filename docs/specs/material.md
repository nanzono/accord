# 文面の材料の取り出し

媒体向けの文面を書く工程に入ったときに 1 回呼ばれ、正本を通しで読む代わりになる一式を返す操作の要件です。返るのは、その媒体に適用される決め、看板のパッケージ、束ねる機能、各機能の裏づけの節、裏づけになっている公開記録、媒体の規約、禁じた言い回し、そして警告の一覧です。

この操作は正本を読むだけで、書き換えません。

この操作が守る決まりは 1 つ、「出典と裏づけの節の公開可否」です。対外の文面に書く事実を、公開可の節に限ります。公開不可の節は材料に載せず、落としたことと節の名前を警告に書きます。落としたことを黙ると、受け取った側は「その節は無い」と読んで、別の裏づけを探しに正本を開くことになります。

警告には、この操作が自分で作るものと、同じ媒体の範囲で整合の検査を呼んで返ってきたものが並びます。同じ判定を 2 か所に置かないためです。

媒体の規約と禁じた言い回しを**どこから読むか**は、正本の読み方の設定の要件（[reading-settings.md](reading-settings.md)）が持ちます。ここに書くのは、読んだものが材料の返り値に載ることだけです。

要件の書き方と番号の決まりは [README.md](README.md) にあります。

## REQ-084
媒体の名前を渡されたとき、accord はその媒体に適用される決めが前面に出す束を、材料の看板のパッケージとして返す。

- 関係するファイル: `src/accord/services/material.py`、`src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_084`

## REQ-085
パッケージの ID を渡されたとき、accord はその ID のパッケージを材料の看板として返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_085`

## REQ-086
看板のパッケージが決まったとき、accord は束ねる機能を、パッケージ定義が並べた ID の並びのまま材料に載せる。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_086`

## REQ-087
束ねる機能が裏づけの節を持つとき、accord はその節を、表示名と ID と本文を添えて材料に載せる。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_087`

## REQ-088
束ねる機能の裏づけが公開記録の ID を指すとき、accord はその公開記録を材料の公開記録として返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_088`

## REQ-089
束ねる機能の裏づけが公開記録の ID を指すとき、accord はその公開記録を裏づけの節の一覧に入れない。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_089`

## REQ-090
媒体の名前を渡されたとき、accord は見せ方の正本にあるその媒体の規約を材料に載せる。

- 関係するファイル: `src/accord/services/material.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_090`

## REQ-091
媒体の名前を渡されたとき、accord は見せ方の正本にある禁じた言い回しを、媒体によらず同じ一覧として材料に載せる。

- 関係するファイル: `src/accord/services/material.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_091`

## REQ-092
常に、accord は材料の取り出しで正本のファイルを 1 バイトも書き換えない。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_092`

## REQ-093
もし束ねる機能の裏づけの節が公開不可なら、accord はその節の見出しも本文も材料に載せない。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_093`

## REQ-094
もし束ねる機能の裏づけの節が公開不可なら、accord は落としたことと節の名前を警告に返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_094`

## REQ-095
もし束ねる機能の ID が機能の台帳に無いなら、accord はその機能の裏づけが材料に入っていないことを、束の名前とその ID を添えて警告に返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_095`

## REQ-096
もし束ねる機能の裏づけの節の ID が正本のどこにも無いなら、accord はその節が材料に入っていないことを、機能の名前とその ID を添えて警告に返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_096`

## REQ-097
もし見せ方の正本に渡された媒体の節が無いなら、accord は媒体の規約が空であることを、見せ方の正本のファイル名を添えて警告に返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_097`

## REQ-098
もし見せ方の正本に禁じた言い回しの節が無いなら、accord はその一覧が空であることを、見せ方の正本のファイル名を添えて警告に返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_098`

## REQ-099
もし渡されたパッケージの ID がパッケージ定義に無いなら、accord は看板のパッケージも束ねる機能も材料に載せない。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_099`

## REQ-100
もし渡されたパッケージの ID がパッケージ定義に無いなら、accord は実在するパッケージの ID の一覧と次に呼ぶ操作の名前を警告に返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_100`

## REQ-101
もし媒体の名前が設定の媒体の一覧に無いなら、accord は決めも看板のパッケージも材料に載せない。

- 関係するファイル: `src/accord/services/material.py`、`src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_101`

## REQ-102
もし媒体の名前が設定の媒体の一覧に無いなら、accord は実在する媒体の名前をすべてと、次に呼ぶ操作の名前を警告に返す。

- 関係するファイル: `src/accord/services/material.py`、`src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_102`

## REQ-103
もし決めが 1 件も登記されていないなら、accord は決めも看板のパッケージも裏づけも材料に載せない。

- 関係するファイル: `src/accord/services/material.py`、`src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_103`

## REQ-104
もし決めが 1 件も登記されていないなら、accord は先に決めを登記することと、決めの入力の欄の名前を警告に返す。

- 関係するファイル: `src/accord/services/material.py`、`src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_104`

## REQ-105
案件を渡されたとき、accord は案件を渡さないときと同じ看板のパッケージと裏づけを返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_105`

## REQ-106
案件を渡されたとき、accord はその案件を材料に反映しないことを、案件の名前を添えて警告に返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_106`

## REQ-107
材料を取り出すとき、accord は同じ媒体の範囲で整合の検査を呼び、返った違反を材料の警告に載せる。

- 関係するファイル: `src/accord/services/material.py`、`src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_107`

## REQ-108
もしどの機能の裏づけにもなっていない公開記録があるなら、accord はその件数と名前を添えた警告を返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_108`

## REQ-371
もし束ねる機能の裏づけの節が公開不可なら、accord は当たった制約の名前を警告に書く。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_371`

## REQ-373
材料を取り出すとき、accord は提示物の未反映の注記を材料の中身に使わない。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_material.py -k REQ_373`

## REQ-374
公開記録の置き場を書いていない設定で文面の材料を取り出すとき、accord は公開記録を空の一覧で返す。

- 関係するファイル: `src/accord/services/material.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_374`

## 未決の質問

- 「その媒体に適用される決めが前面に出す束」（REQ-084）が、その媒体を名指しした決めが 1 件も無いときに何を返すかを決めていません。いまの実装は適用範囲「全体」の決めに落として、落としたことを警告に 1 行足します。この文だけを読むと、名指しの決めが無ければ何も返さない実装も書けます。いまのテストは、媒体を名指しした決めがある見本で確かめているので、落ち方を見ていません。
  - この落ち方は、決めの読み書きの要件 REQ-162 と REQ-163 で決まりました（媒体を名指しした決めが 1 件も無いときは、適用範囲「全体」の最新を返し、落としたことを警告に返します）。
- 「返った違反を材料の警告に載せる」（REQ-107）が、整合の検査が返すもう 1 つの一覧（断り）をどう扱うかを決めていません。いまの実装は違反と断りの両方を警告に足します。文のとおりに違反だけを載せる実装も書けます。いまのテストは違反 1 種類しか見ていないので、どちらでも通ります。

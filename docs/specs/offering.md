# 機能の登記とパッケージの改訂

売り物の層（機能の台帳とパッケージ定義）に書き足す 2 つの操作の要件です。機能を 1 件登記する操作と、パッケージの 1 節を改訂する操作があります。

どちらも、守るべきことを先にすべて確かめ、通ると決まってから 1 度だけ書きます。通らなかったときは、何が通らなかったかと、次に何を渡せば通るかを返します。

受け付ける語（機能の分類、パッケージの仮説の状態）は設定ファイルが持ちます。語を変えるのに、この道具を作り直す必要はありません。

要件の書き方と番号の決まりは [README.md](README.md) にあります。

## REQ-109
設定ファイルの機能の分類の一覧を書き換えられたとき、accord は書き換えた後の分類で機能の登記を受け付ける。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_109`

## REQ-110
公開記録の ID を裏づけに渡されたとき、accord はその機能を機能の台帳に足す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_110`

## REQ-111
断りで返した候補の ID をそのまま裏づけに渡し直されたとき、accord はその機能を機能の台帳に足す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_111`

## REQ-112
機能の登記が通ったとき、accord は裏づけの節ごとの公開可否を返り値に入れる。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_112`

## REQ-113
機能の登記が通ったとき、accord は裏づけが公開記録である節の公開可否に、公開記録であることを書く。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_113`

## REQ-114
もし登記する機能の裏づけの節が公開不可なら、accord は対外の文面に出せないことを、その節の名前を添えて警告に返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_114`

## REQ-115
もし機能の必須の欄が空なら、accord はその機能を登記しない。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_115`

## REQ-116
もし機能の必須の欄が空なら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_116`

## REQ-117
もし機能の必須の欄が空なら、accord は欠けた欄の名前を断りの理由に書く。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_117`

## REQ-118
もし機能の必須の欄が空なら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_118`

## REQ-119
もし機能の必須の欄が空なら、accord は欠けた欄の名前の一覧を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_119`

## REQ-120
もし機能の必須の欄が空なら、accord は欠けた欄の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/models/ontology.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_120`

## REQ-121
もし機能の分類が設定の分類の一覧に無いなら、accord はその機能を登記しない。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_121`

## REQ-122
もし機能の分類が設定の分類の一覧に無いなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_122`

## REQ-123
もし機能の分類が設定の分類の一覧に無いなら、accord は渡された分類を断りの理由に書く。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_123`

## REQ-124
もし機能の分類が設定の分類の一覧に無いなら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_124`

## REQ-125
もし機能の分類が設定の分類の一覧に無いなら、accord は設定の分類の一覧を断りの候補に返す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_125`

## REQ-126
もし機能の分類が設定の分類の一覧に無いなら、accord は候補のどれかをそのまま渡す書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_126`

## REQ-127
もし機能の裏づけの節の ID が正本のどこにも無いなら、accord はその機能を登記しない。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_127`

## REQ-128
もし機能の裏づけの節の ID が正本のどこにも無いなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_128`

## REQ-129
もし機能の裏づけの節の ID が正本のどこにも無いなら、accord は渡された ID を断りの理由に書く。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_129`

## REQ-130
もし機能の裏づけの節の ID が正本のどこにも無いなら、accord は候補の表示名を断りの理由に書く。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_130`

## REQ-131
もし機能の裏づけの節の ID が正本のどこにも無いなら、accord は公開記録にも無いことを断りの理由に書く。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_131`

## REQ-132
もし機能の裏づけの節の ID が正本のどこにも無いなら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_132`

## REQ-133
もし機能の裏づけの節の ID が正本のどこにも無いなら、accord はそのまま渡せる実在の ID を断りの候補に返す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_133`

## REQ-134
もし機能の裏づけの節の ID が正本のどこにも無いなら、accord は候補をそのまま裏づけの節に渡して呼び直す書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_134`

## REQ-135
既にある名前のパッケージを改訂されたとき、accord はパッケージ定義のその名前の節の中身を差し替える。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_135`

## REQ-136
まだ節の無い名前のパッケージを改訂されたとき、accord はパッケージ定義に新しい節を足す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_136`

## REQ-137
パッケージの改訂が通ったとき、accord は渡された ID と仮説の状態と束ねる機能を、パッケージ定義に書く。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_137`

## REQ-138
パッケージの改訂が通ったとき、accord はそのパッケージの最終更新日を今日に進める。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_138`

## REQ-139
パッケージの改訂の入力に崩れる条件の欄が無いとき、accord は前の定義の崩れる条件をそのまま残す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_139`

## REQ-140
パッケージの改訂の入力に崩れる条件の欄が無いとき、accord は残したことを警告に返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_140`

## REQ-141
パッケージの改訂の入力に判定根拠か出典の欄が無いとき、accord は前の定義のその欄の値をそのまま残す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_141`

## REQ-142
パッケージの改訂の入力に判定根拠か出典の欄が無いとき、accord は残したことをその欄の名前を添えて警告に返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_142`

## REQ-143
断りで返した候補の ID をそのまま束ねる機能に渡し直されたとき、accord はそのパッケージを改訂する。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_143`

## REQ-144
もし束ねる機能の ID が機能の台帳に無いなら、accord はそのパッケージを改訂しない。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_144`

## REQ-145
もし束ねる機能の ID が機能の台帳に無いなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_145`

## REQ-146
もし束ねる機能の ID が機能の台帳に無いなら、accord は渡された ID を断りの理由に書く。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_146`

## REQ-147
もし束ねる機能の ID が機能の台帳に無いなら、accord は候補の表示名を断りの理由に書く。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_147`

## REQ-148
もし束ねる機能の ID が機能の台帳に無いなら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_148`

## REQ-149
もし束ねる機能の ID が機能の台帳に無いなら、accord は台帳にある近い ID を断りの候補に返す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_149`

## REQ-150
もし束ねる機能の ID が機能の台帳に無いなら、accord は先に機能を登記する操作の名前を断りの書き方の例に入れる。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_150`

## REQ-151
もしパッケージの仮説の状態が設定の語の一覧に無いなら、accord はそのパッケージを改訂しない。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_151`

## REQ-152
もしパッケージの仮説の状態が設定の語の一覧に無いなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_152`

## REQ-153
もしパッケージの仮説の状態が設定の語の一覧に無いなら、accord は渡された語を断りの理由に書く。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_153`

## REQ-154
もしパッケージの仮説の状態が設定の語の一覧に無いなら、accord は次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_154`

## REQ-155
もしパッケージの仮説の状態が設定の語の一覧に無いなら、accord は設定の語の一覧を断りの候補に返す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_155`

## REQ-156
もしパッケージの仮説の状態が設定の語の一覧に無いなら、accord は候補のどれかをそのまま渡す書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_156`

## REQ-320
もし機能の登記で 2 つ以上の制約が同時に外れているなら、accord は必須の欄・分類の語彙・ID の形と重なり・裏づけの節の順で先に当たった 1 件だけを断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_320`

## REQ-321
もしパッケージの改訂で 2 つ以上の制約が同時に外れているなら、accord は必須の欄・ID の形と重なり・仮説の状態・束ねる機能の順で先に当たった 1 件だけを断りに返す。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_321`

## REQ-370
もし登記する機能の裏づけの節が公開不可なら、accord は当たった制約の名前を警告に書く。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_offering.py -k REQ_370`

## 未決の質問

- 無し。

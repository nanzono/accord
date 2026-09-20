# 整合の検査

正本（売り方の決め、パッケージ定義、機能の台帳、受託案件、公開記録）と、そこから作った提示物や職務経歴書の台帳が食い違っていないかを調べる操作の要件です。この操作は正本を読むだけで、書き換えません。

返り値には 2 つの一覧があります。

- 違反: 直さないと食い違いが残るものです。どのファイルのどこを、何に合わせるかを添えて返します。
- 断り: 違反ではないが、知らせておくことです。たとえば、判定を保留したこと、読めなかったブロックがあること、範囲を絞ったので見ていないものがあること。

要件の書き方と番号の決まりは [README.md](README.md) にあります。

## REQ-001
範囲を渡さずに呼ばれたとき、accord は検査した範囲の名前として「全体」を返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_001`

## REQ-002
手を入れていない同梱の見本を検査されたとき、accord は違反を 1 件も返さない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_002`

## REQ-003
常に、accord は整合の検査で正本のファイルを 1 バイトも書き換えない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_003`

## REQ-004
常に、accord は整合の検査の返り値に、読んだ設定ファイルの場所と動いているソースの置き場と accord の版を入れる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_004`

## REQ-005
読み方の節を持たない設定で呼ばれたとき、accord は適用した読み方として「既定」の 1 件を返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_005`

## REQ-006
読み方の節を持つ設定で呼ばれたとき、accord は設定に書かれた読み方の鍵をすべて、節と欄をつないだ形で返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_006`

## REQ-007
媒体の名前を範囲に渡されたとき、accord はその媒体の提示物だけを検査する。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_007`

## REQ-008
範囲を絞って呼ばれたとき、accord は見ていないものがあることを断りに書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_008`

## REQ-009
もし渡された範囲の名前が媒体にも提示物にも無いなら、accord は違反を 1 件も返さない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_009`

## REQ-010
もし渡された範囲の名前が媒体にも提示物にも無いなら、accord はそのまま渡せる範囲の名前の一覧を断りに書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_010`

## REQ-011
もしパッケージ定義の最終更新が、その束を前面に出した決めの日付より古いなら、accord は決めの日付と定義の最終更新日の両方を直し先に書いた違反を 1 件挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_011`

## REQ-012
もし提示物が宣言する束が、その媒体に適用される決めの看板と違うなら、accord はいまの看板の束の ID を候補にした違反を挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_012`

## REQ-013
提示物が決めの例外の欄に書かれているとき、accord はその提示物の宣言を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_013`

## REQ-014
もし決めが 1 件も登記されていないなら、accord は提示物の宣言とパッケージ定義の鮮度を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_014`

## REQ-015
もし決めが 1 件も登記されていないなら、accord は判定を保留したことと、決めを登記する操作の名前と入力の欄の名前を断りに書く。

- 関係するファイル: `src/accord/services/consistency.py`、`src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_015`

## REQ-016
もし決めが前面に出す束がパッケージ定義に無いなら、accord は鮮度を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_016`

## REQ-017
もし決めが前面に出す束がパッケージ定義に無いなら、accord は鮮度を判定できないことと実在する束の ID を断りに書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_017`

## REQ-018
必須の欄を欠いた決めのブロックがあるとき、accord は 1 つ前の決めを看板として提示物の宣言を判定する。

- 関係するファイル: `src/accord/services/consistency.py`、`src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_018`

## REQ-019
もし職務経歴書の台帳が公開不可の受託案件を出典にしているなら、accord は公開可の受託案件の ID だけを候補にした違反を挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_019`

## REQ-020
もし提示物の未反映の注記が実在しない受託案件を指しているなら、accord は近い受託案件の ID を候補にした違反を挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_020`

## REQ-021
提示物に未反映の注記が残っているとき、accord はその件数を断りに書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_021`

## REQ-022
機能の裏づけが公開記録を指しているとき、accord はそれを実在する裏づけとして扱う。

- 関係するファイル: `src/accord/services/consistency.py`、`src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_022`

## REQ-023
もし公開記録の由来の節が実在しない節を指しているなら、accord はその公開記録のブロックを名指しした違反を 1 件挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_023`

## REQ-024
もし正本のブロックに必須の欄が無いなら、accord はそのブロックを読んでいないことを、正本のファイル名と場所と欠けた欄の名前と次に呼ぶ操作を添えた断りで返す。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_024`

## REQ-025
同じ正本の同じ欄が欠けた断りが複数あるとき、accord はそれらを、代表と件数を持つ 1 件の断りに束ねる。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_025`

## REQ-026
常に、accord は整合の検査が返す断りを、同じ種類を束ねた後の数で 30 件以内に収める。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_026`

## REQ-027
もし断りが 30 件を超えるなら、accord は打ち切った件数を末尾の 1 行に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_027`

## REQ-028
もし指された節が正本に実在しながら読み取り範囲の外にあるなら、accord はその節の深さと上位の見出しと外れた絞りの鍵を直し先に書いた、候補の無い違反を挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_028`

## REQ-029
もし指された節が、必須の欄が欠けて読めていないブロックなら、accord は欠けた欄の名前を直し先に書いた、候補の無い違反を挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_029`

## REQ-030
もし提示物が載せている URL が正本のどの公開記録にも無いなら、accord は公開記録を登記する操作の名前と渡す欄の名前を直し先に書き、近い URL を候補にした違反を挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_030`

## REQ-031
もし提示物の URL が、正本の公開記録と同じ場所を指しながら経路の書き方だけ違うなら、accord は相手の URL 1 件を候補にして、書き方が違うことを直し先に書いた違反を挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_031`

## REQ-032
提示物が載せた URL が正本の公開記録と、末尾のスラッシュ・http と https・ホストの大文字小文字・www.・末尾のクエリだけ違うとき、accord はそれを同じ URL として扱う。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_032`

## REQ-033
URL を持たない公開記録だけが正本にあるとき、accord は提示物の URL を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_033`

## REQ-034
提示物の URL のホストが正本のどの公開記録のホストとも違うとき、accord はその URL を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_034`

## REQ-035
もし設定に公開記録の置き場が無いなら、accord は提示物の URL を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_035`

## REQ-036
もし設定に公開記録の置き場が無いなら、accord は URL を照合させるために設定へ足す鍵の名前を断りに書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_036`

## REQ-037
看板の裏づけになっている公開記録がその範囲のどの提示物にも載っていないとき、accord はそれを違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_037`

## REQ-038
看板の裏づけになっている公開記録がその範囲のどの提示物にも載っていないとき、accord はその公開記録の名前を断りに書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_038`

## REQ-039
もし公開記録の種類か役割に、設定の語の一覧に無い語が書かれているなら、accord は設定の語の一覧を候補にした違反を 1 件挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_039`

## REQ-040
もし機能の台帳に、設定の語の一覧に無い見出しの節があるなら、accord はその節の機能を、設定の分類の語を候補にした違反として挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_040`

## REQ-041
もしパッケージが束ねる機能の ID が機能の台帳に無いなら、accord はパッケージ定義のその節を名指しし、近い機能の ID を候補にした違反を挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_041`

## REQ-042
提示物のファイル名を範囲に渡されたとき、accord はその提示物だけを検査する。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_042`

## REQ-043
媒体の名前を範囲に渡されたとき、accord は公開記録のうち、その媒体の看板が束ねる機能の裏づけになっているものだけを検査する。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_043`

## REQ-044
範囲を絞って呼ばれたとき、accord は ID の形式と一意性を正本全体で検査する。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_044`

## REQ-045
もし同じ提示物が、正本に無い同じ URL を 2 回載せているなら、accord はその URL の違反を 1 件だけ挙げる。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_045`

## 未決の質問

- 手を入れていない同梱の見本に違反が出ないことは、検査の振る舞いとも、見本そのものの出来とも読めます。見本に違反が出たときに、検査を直すのか見本を直すのかは、この文だけでは決まりません。実際に落ちたときに、落ちた理由から決めます。
- 範囲を絞ったときに「見ていないものがある」と断る文は、何をどこまで並べるかを決めていません。いまの文は、媒体で絞ったときと提示物で絞ったときで違い、テストは「見ていない」の語があることだけを見ています。並べる中身まで要件にするかは、文言を変える必要が出たときに決めます。

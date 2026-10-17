# 起動と置き場と正本の読み方

起動と、置き場と、正本の読み方（accord の形）の要件です。accord は設定ファイルを読みません。経歴データの置き場（`--data`）と提示物の置き場（`--presentations`）を起動の引数で受け、語彙を置き場の `vocabulary.md` から読み、正本を 1 通りの書き方（accord の形）で読みます。accord の形の全体は [docs/data-format.md](../data-format.md) にあり、同梱の見本（`samples/data/` と `samples/presentations/`）がその実例です。移行の操作（`migrate_data`）の要件もここに置きます。移行の操作は、前の版の設定ファイル `accord.toml` を持つ置き場を、`vocabulary.md` を持つ accord の形の置き場にします。

前の版では、読み方を設定ファイルの読み方の節で変えられました。その要件（読み方の鍵ごとの要件と、設定ファイルの書き方の要件）は、accord の形を 1 つに固定した要件に取って代わられ、状態の行を持ちます（そう決めた理由は [docs/decisions/0016-drop-the-settings-file-and-fix-one-form.md](../decisions/0016-drop-the-settings-file-and-fix-one-form.md)）。

要件の書き方と番号の決まりは [README.md](README.md) にあります。

## REQ-046
読み方の節を持たない設定で呼ばれたとき、accord は見出しで項目を区切る正本を、深さ 2 の見出しの節ごとに 1 つのブロックとして読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_046`
- status: superseded by REQ-506

## REQ-047
提示物の置き場を書いていない設定で呼ばれたとき、accord は設定が提示物として指したディレクトリの下のすべての Markdown を提示物として読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_047`
- status: superseded by REQ-506

## REQ-048
宣言の行での絞りを書いていない設定で呼ばれたとき、accord は宣言の行を持たない Markdown を、欄が足りない断りに出す。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_048`
- status: superseded by REQ-506

## REQ-049
媒体の規約の置き場を書いていない設定で呼ばれたとき、accord は媒体の規約を、見せ方の正本の中の媒体の名前の節から読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_049`
- status: superseded by REQ-506

## REQ-050
禁じた言い回しの節の見出しを書いていない設定で呼ばれたとき、accord はその節を「禁じた言い回し」という名前で探す。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_050`
- status: superseded by REQ-506

## REQ-051
禁じた言い回しの節を深さを問わず探す設定を書いていないとき、accord はその節を、見せ方の正本の読み方で選ばれる見出しの中だけから探す。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_051`
- status: superseded by REQ-506

## REQ-052
禁じた言い回しの読み方を書いていない設定で呼ばれたとき、accord は節の箇条書きから禁じた言い回しを読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_052`
- status: superseded by REQ-506

## REQ-053
読み方の節に `heading_levels` を書かれたとき、accord はその深さの見出しの節だけをブロックとして読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_053`
- status: superseded by REQ-506

## REQ-054
読み方の節に `under_headings` を書かれたとき、accord はその見出しの下にある節だけをブロックとして読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_054`
- status: superseded by REQ-506

## REQ-055
読み方の節に `heading_prefix` を書かれたとき、accord はその文字列で始まる見出しの節だけをブロックとして読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_055`
- status: superseded by REQ-506

## REQ-056
読み方の節に `skip_headings` を書かれたとき、accord はその見出しの節とその下の節をブロックとして読まない。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_056`
- status: superseded by REQ-506

## REQ-057
読み方の節で `skip_sections_without_fields` が有効な場合、accord は欄を 1 つも持たない節をブロックとして読まない。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_057`
- status: superseded by REQ-506

## REQ-058
2 つの種類の正本に同じファイル名を書いた設定で呼ばれたとき、accord はそれぞれの種類の読み方で、そのファイルから重なりのない項目を読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_058`
- status: superseded by REQ-506

## REQ-059
読み方の節で `fields_from_table` が有効な場合、accord は 2 列の表の行を、1 列目をラベル、2 列目を値とする欄として読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_059`
- status: superseded by REQ-506

## REQ-060
読み方の節で `fields_from_table` が有効な場合、accord は同じブロックの箇条書きの欄と表の欄を、1 つの欄の集合として読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_060`
- status: superseded by REQ-506

## REQ-061
読み方の節の `bare_labels` に挙げられたラベルで始まる行があるとき、accord は箇条書きの記号の無いその行も欄として読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_061`
- status: superseded by REQ-506

## REQ-062
読み方の節で `entry_number_from_heading` が有効な場合、accord は案件の番号を、見出しの前置きに続く数字から読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_062`
- status: superseded by REQ-506

## REQ-063
読み方の節で `strip_label_note` が有効な場合、accord は欄のラベルの末尾の括弧書きを落としてから欄の名前を照らし合わせる。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_063`
- status: superseded by REQ-506

## REQ-064
読み方の節の `labels` で 1 つのラベルに複数の欄の名前を書かれたとき、accord は同じ値をその欄すべてに入れる。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_064`
- status: superseded by REQ-506

## REQ-065
読み方の節の提示物の `directories` にディレクトリを挙げられたとき、accord は挙げられたすべてのディレクトリの下から提示物を読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_065`
- status: superseded by REQ-506

## REQ-066
読み方の節で提示物の `require_declaration` が有効な場合、accord は宣言の行を持つ Markdown だけを提示物として読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_066`
- status: superseded by REQ-506

## REQ-067
読み方の節で提示物の `require_declaration` が有効な場合、accord は宣言の行を持たない Markdown を、欄が足りない断りにも出さない。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_067`
- status: superseded by REQ-506

## REQ-068
媒体ごとのファイルから媒体の規約を読む設定で呼ばれたとき、accord はその媒体のファイルの箇条書きだけを媒体の規約として返す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_068`
- status: superseded by REQ-506

## REQ-069
もし媒体ごとの規約のファイルが無いなら、accord は媒体の規約を空の一覧として返す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_069`

## REQ-070
読み方の節で `forbidden_phrases_any_level` が有効な場合、accord は禁じた言い回しの節を、見出しの深さを問わず名前で探す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_070`
- status: superseded by REQ-506

## REQ-071
禁じた言い回しの節を名前で探すとき、accord は見出しの末尾の括弧書きを見ない。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_071`

## REQ-072
節の表から禁じた言い回しを読む設定で呼ばれたとき、accord はその節の最初の表の 1 列目だけを禁じた言い回しとして返す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_072`
- status: superseded by REQ-506

## REQ-073
読み方を広げた設定で正本にブロックを書き足したとき、accord はそのブロックを同じ設定で、欠けた欄の断り無しに読み直す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_073`
- status: superseded by REQ-506

## REQ-074
節の箇条書きから禁じた言い回しを読む設定で呼ばれたとき、accord はその節の最初の箇条書きの塊だけを禁じた言い回しとして返す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_074`
- status: superseded by REQ-506

## REQ-075
もし設定の最上位に書ける名前でない節があるなら、accord は書かれていた名前と書ける名前を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_075`
- status: superseded by REQ-506

## REQ-076
最上位が `source` と `vocabulary` と `reading` だけの設定で呼ばれたとき、accord はその設定を読み込む。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_076`
- status: superseded by REQ-506

## REQ-077
もし読み方の節に書ける名前でない鍵があるなら、accord は書かれていた鍵の名前と書ける鍵の名前を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_077`
- status: superseded by REQ-506

## REQ-078
もし読み方の節の `heading_levels` が空の一覧なら、accord はその鍵の名前を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_078`
- status: superseded by REQ-506

## REQ-079
もし選べる語が決まっている鍵に一覧の外の語が書かれているなら、accord は書かれていた語と選べる語を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_079`
- status: superseded by REQ-506

## REQ-080
もし公開記録の置き場を書いた設定に公開記録の種類か役割の語の一覧が無いなら、accord は足りない鍵の名前を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_080`
- status: superseded by REQ-506

## REQ-081
公開記録の置き場を書いていない設定で呼ばれたとき、accord は公開記録を 0 件として読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_081`
- status: superseded by REQ-505

## REQ-082
同梱の 2 つ目の見本（同じ中身を違う書き方で書いた正本）をその見本の設定で読まれたとき、accord は読めなかったブロックの断りを 1 件も返さない。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_compat.py -k REQ_082`
- status: superseded by REQ-507

## REQ-083
同梱の 2 つ目の見本（同じ中身を違う書き方で書いた正本）をその見本の設定で読まれたとき、accord は 8 種類の正本と見せ方の正本のすべてから 1 件以上を読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_compat.py -k REQ_083`
- status: superseded by REQ-507

## REQ-375
読み方の節で `frame_heading_prefix` が有効な場合、accord は見出しがその文字列で始まる台帳の節を、在籍職歴の枠のブロックとして読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_375`
- status: superseded by REQ-506

## REQ-376
常に、accord は台帳の在籍職歴の枠のブロックに、案件のブロックだけが持つ欄（規模・担当工程・役割と任され方・自分が決めたこと・終わりの状態）を求めない。

- 関係するファイル: `src/accord/ontology.yaml`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_376`

## REQ-377
もし台帳の在籍職歴の枠のブロックに見出し・期間・出典の節のどれかが無いなら、accord はそのブロックを読んでいないことを、欠けた欄の名前を添えた断りで返す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_377`

## REQ-378
読み方の節で `frame_heading_prefix` と `entry_number_from_heading` が有効な場合、accord は在籍職歴の枠の番号を、見出しのその前置きに続く数字から読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_378`
- status: superseded by REQ-506

## REQ-398
設定に提示物の置き場が書かれているとき、accord は提示物のディレクトリと媒体ごとの規約のファイルを、その置き場から読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_398`
- status: superseded by REQ-504

## REQ-399
設定に提示物の置き場が書かれていないとき、accord は提示物のディレクトリと媒体ごとの規約のファイルを、正本の置き場から読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_399`
- status: superseded by REQ-504

## REQ-400
提示物の置き場が相対の場所で書かれているとき、accord はそれを設定ファイルの置き場から見た場所として読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_400`
- status: superseded by REQ-504

## REQ-401
もし設定の提示物の置き場が実在するディレクトリでないなら、accord は書かれていた値を添えて起動をやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_401`
- status: superseded by REQ-545

## REQ-403
書き込みの記録が有効な場合、accord は書き込みの操作が正本のファイルを変えるたびに、変えたファイルだけを git にコミットする。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_403`
- status: superseded by REQ-513

## REQ-404
書き込みの記録が有効でない場合、accord は書き込みの操作で git を呼ばない。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_404`
- status: superseded by REQ-513

## REQ-405
もし書き込みの記録が有効で、書く前のファイルに未コミットの変更があるなら、accord は書かずに、そのファイルの名前と、先にその変更をコミットすることを断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_405`
- status: superseded by REQ-514
- 注: 断りの文のうち「先にその変更をコミットすること」は、置き場で git を直接操作する案内なので REQ-500 が改める（accord を通さない変更があるので書かなかったことを返す）。ファイルの名前を添えて書かずに断ることそのものは、この要件のまま変わらない。

## REQ-406
もし書き込みの記録が有効で、正本の置き場が git のリポジトリの中に無いなら、accord は設定の鍵の名前を添えて起動をやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_406`
- status: superseded by REQ-503

## REQ-502
起動されたとき、accord は引数 `--data` が指すディレクトリを経歴データの置き場として読み、設定ファイルを読まない。

- 関係するファイル: `src/accord/__main__.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_502`

## REQ-503
もし `--list` 以外の起動で `--data` が無いか、指す先が git の作業ツリーの根でないなら、accord はサーバーを開かずに、置き場の指定の書き方を標準エラーに書いて 0 でない終了コードで終わる。

- 関係するファイル: `src/accord/__main__.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_503`

## REQ-504
起動されたとき、accord は引数 `--presentations` が指すディレクトリから提示物と媒体ごとの規約を読み、引数が無ければ提示物を 0 件として読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_504`

## REQ-505
常に、accord は置き場の中の 7 ファイルを、決まった名前（career_master.md・keirekisho/daicho.md・misekata_master.md・product/features.md・product/packages.md・product/positioning.md・public_records.md）で読み、語彙を vocabulary.md から読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_505`

## REQ-506
常に、accord は正本を 1 通りの書き方（accord の形）で読み、読み方を変える設定も引数も受け付けない。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_506`

## REQ-507
常に、accord は accord の形を公開側の文書 1 つ（`docs/data-format.md`）に書き、その文書が指す見本の置き場の正本を整合の検査の違反 0 件で読む。

- 関係するファイル: `docs/data-format.md`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_507`

## REQ-545
もし `--presentations` が実在するディレクトリを指さないなら、accord はサーバーを開かずに、提示物の置き場の指定の書き方を標準エラーに書いて 0 でない終了コードで終わる。

- 関係するファイル: `src/accord/__main__.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_545`

## REQ-546
もし置き場に accord.toml も vocabulary.md も無いなら、accord はサーバーを開かずに、vocabulary.md が要ることを標準エラーに書いて 0 でない終了コードで終わる。

- 関係するファイル: `src/accord/__main__.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_546`

## REQ-522
もし置き場に accord.toml があり vocabulary.md が無いなら、accord は移行の操作のほかの操作を断り、移行の操作の名前を返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/server/app.py`、`src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_migration.py -k REQ_522`

## REQ-523
移行の操作が呼ばれたとき、accord は accord.toml の語彙の節から vocabulary.md を作り、accord.toml を消し、その 2 つを操作の名前を示す行を持つ 1 件のコミットにする。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/git_commits.py`、`src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_migration.py -k REQ_523`

## REQ-524
もし accord.toml の置き場の節か読み方の節が accord の形と違うなら、accord は移行せずに、違う鍵と、accord の形の値を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_migration.py -k REQ_524`

## REQ-544
もし移行済みの置き場で移行の操作が呼ばれたなら、accord は書かずに、移行済みであることを断りに返す。

- 関係するファイル: `src/accord/services/recording.py`
- 検証手順: `uv run pytest tests/test_migration.py -k REQ_544`

## 未決の質問

- 「読み方を広げた設定で正本にブロックを書き足したとき」（REQ-073）の「読み方を広げた設定」が、どこまでを指すかを決めていません。いまのテストは同梱の 2 つ目の見本の設定 1 つで確かめているので、別の広げ方（たとえば欄を表だけから読む設定）でも同じことを言うのかは、この文からは決まりません。別の広げ方で往復が壊れたときに決めます。
- 「8 種類の正本と見せ方の正本のすべてから 1 件以上を読む」（REQ-083）の、見せ方の正本の数え方を決めていません。見せ方の正本から返るのは媒体の規約と禁じた言い回しで、媒体の規約は宛先の媒体ごとに違います。いまのテストは媒体 1 つで見ています。どの媒体で見ても 1 件以上と言うのかは、この文からは決まりません。
- 「選べる語が決まっている鍵」（REQ-079）が、どの鍵を指すかを要件の文に書いていません。いまは 2 つ（媒体の規約の置き場の書き方と、禁じた言い回しの読み方）で、テストはそのうち 1 つで見ています。選べる語を持つ鍵を後から足したとき、同じ拒否を通すことをこの要件が求めるのかは、文からは決まりません。

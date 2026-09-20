# 正本の読み方の設定

正本は Markdown のまま持ちます。だから、見出しの深さも、欄を箇条書きで書くか表で書くかも、欄のラベルの言い方も、書く人によって違います。その違いを、設定ファイルの読み方の節が吸収する、という決めの要件です。読み方の節を書かなければ、すべての鍵が既定値になり、深さ 2 の見出しの節を 1 件ぶんとして読みます。

要件の文に出てくる `heading_levels` のような名前は、利用者が設定ファイルに書く鍵の名前です。設定に書ける鍵の一覧と書き方の例は、同梱の見本（`samples/accord.toml` と `samples/accord_alt.toml`）と [samples/README.md](../../samples/README.md) にあります。

同じ中身を違う書き方で書いた正本の上でも、整合の検査が同じ結果を返すことは、整合の検査の要件の番号を名前に持つテストが、同梱の 2 つ目の見本の上でも確かめています（[consistency-check.md](consistency-check.md) と `tests/test_compat.py`）。

要件の書き方と番号の決まりは [README.md](README.md) にあります。

## REQ-046
読み方の節を持たない設定で呼ばれたとき、accord は見出しで項目を区切る正本を、深さ 2 の見出しの節ごとに 1 つのブロックとして読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_046`

## REQ-047
提示物の置き場を書いていない設定で呼ばれたとき、accord は設定が提示物として指したディレクトリの下のすべての Markdown を提示物として読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_047`

## REQ-048
宣言の行での絞りを書いていない設定で呼ばれたとき、accord は宣言の行を持たない Markdown を、欄が足りない断りに出す。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_048`

## REQ-049
媒体の規約の置き場を書いていない設定で呼ばれたとき、accord は媒体の規約を、見せ方の正本の中の媒体の名前の節から読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_049`

## REQ-050
禁じた言い回しの節の見出しを書いていない設定で呼ばれたとき、accord はその節を「禁じた言い回し」という名前で探す。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_050`

## REQ-051
禁じた言い回しの節を深さを問わず探す設定を書いていないとき、accord はその節を、見せ方の正本の読み方で選ばれる見出しの中だけから探す。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_051`

## REQ-052
禁じた言い回しの読み方を書いていない設定で呼ばれたとき、accord は節の箇条書きから禁じた言い回しを読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_052`

## REQ-053
読み方の節に `heading_levels` を書かれたとき、accord はその深さの見出しの節だけをブロックとして読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_053`

## REQ-054
読み方の節に `under_headings` を書かれたとき、accord はその見出しの下にある節だけをブロックとして読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_054`

## REQ-055
読み方の節に `heading_prefix` を書かれたとき、accord はその文字列で始まる見出しの節だけをブロックとして読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_055`

## REQ-056
読み方の節に `skip_headings` を書かれたとき、accord はその見出しの節とその下の節をブロックとして読まない。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_056`

## REQ-057
読み方の節で `skip_sections_without_fields` が有効な場合、accord は欄を 1 つも持たない節をブロックとして読まない。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_057`

## REQ-058
2 つの種類の正本に同じファイル名を書いた設定で呼ばれたとき、accord はそれぞれの種類の読み方で、そのファイルから重なりのない項目を読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_058`

## REQ-059
読み方の節で `fields_from_table` が有効な場合、accord は 2 列の表の行を、1 列目をラベル、2 列目を値とする欄として読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_059`

## REQ-060
読み方の節で `fields_from_table` が有効な場合、accord は同じブロックの箇条書きの欄と表の欄を、1 つの欄の集合として読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_060`

## REQ-061
読み方の節の `bare_labels` に挙げられたラベルで始まる行があるとき、accord は箇条書きの記号の無いその行も欄として読む。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_061`

## REQ-062
読み方の節で `entry_number_from_heading` が有効な場合、accord は案件の番号を、見出しの前置きに続く数字から読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_062`

## REQ-063
読み方の節で `strip_label_note` が有効な場合、accord は欄のラベルの末尾の括弧書きを落としてから欄の名前を照らし合わせる。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_063`

## REQ-064
読み方の節の `labels` で 1 つのラベルに複数の欄の名前を書かれたとき、accord は同じ値をその欄すべてに入れる。

- 関係するファイル: `src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_064`

## REQ-065
読み方の節の提示物の `directories` にディレクトリを挙げられたとき、accord は挙げられたすべてのディレクトリの下から提示物を読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_065`

## REQ-066
読み方の節で提示物の `require_declaration` が有効な場合、accord は宣言の行を持つ Markdown だけを提示物として読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_066`

## REQ-067
読み方の節で提示物の `require_declaration` が有効な場合、accord は宣言の行を持たない Markdown を、欄が足りない断りにも出さない。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_067`

## REQ-068
媒体ごとのファイルから媒体の規約を読む設定で呼ばれたとき、accord はその媒体のファイルの箇条書きだけを媒体の規約として返す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_068`

## REQ-069
もし媒体ごとの規約のファイルが無いなら、accord は媒体の規約を空の一覧として返す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_069`

## REQ-070
読み方の節で `forbidden_phrases_any_level` が有効な場合、accord は禁じた言い回しの節を、見出しの深さを問わず名前で探す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_070`

## REQ-071
禁じた言い回しの節を名前で探すとき、accord は見出しの末尾の括弧書きを見ない。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_071`

## REQ-072
節の表から禁じた言い回しを読む設定で呼ばれたとき、accord はその節の最初の表の 1 列目だけを禁じた言い回しとして返す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_072`

## REQ-073
読み方を広げた設定で正本にブロックを書き足したとき、accord はそのブロックを同じ設定で、欠けた欄の断り無しに読み直す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_073`

## REQ-074
節の箇条書きから禁じた言い回しを読む設定で呼ばれたとき、accord はその節の最初の箇条書きの塊だけを禁じた言い回しとして返す。

- 関係するファイル: `src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_074`

## REQ-075
もし設定の最上位に書ける名前でない節があるなら、accord は書かれていた名前と書ける名前を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_075`

## REQ-076
最上位が `source` と `vocabulary` と `reading` だけの設定で呼ばれたとき、accord はその設定を読み込む。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_076`

## REQ-077
もし読み方の節に書ける名前でない鍵があるなら、accord は書かれていた鍵の名前と書ける鍵の名前を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_077`

## REQ-078
もし読み方の節の `heading_levels` が空の一覧なら、accord はその鍵の名前を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_078`

## REQ-079
もし選べる語が決まっている鍵に一覧の外の語が書かれているなら、accord は書かれていた語と選べる語を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_079`

## REQ-080
もし公開記録の置き場を書いた設定に公開記録の種類か役割の語の一覧が無いなら、accord は足りない鍵の名前を添えて設定の読み込みをやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_080`

## REQ-081
公開記録の置き場を書いていない設定で呼ばれたとき、accord は公開記録を 0 件として読む。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_reading_settings.py -k REQ_081`

## REQ-082
同梱の 2 つ目の見本（同じ中身を違う書き方で書いた正本）をその見本の設定で読まれたとき、accord は読めなかったブロックの断りを 1 件も返さない。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_compat.py -k REQ_082`

## REQ-083
同梱の 2 つ目の見本（同じ中身を違う書き方で書いた正本）をその見本の設定で読まれたとき、accord は 8 種類の正本と見せ方の正本のすべてから 1 件以上を読む。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_compat.py -k REQ_083`

## 未決の質問

- 「読み方を広げた設定で正本にブロックを書き足したとき」（REQ-073）の「読み方を広げた設定」が、どこまでを指すかを決めていません。いまのテストは同梱の 2 つ目の見本の設定 1 つで確かめているので、別の広げ方（たとえば欄を表だけから読む設定）でも同じことを言うのかは、この文からは決まりません。別の広げ方で往復が壊れたときに決めます。
- 「8 種類の正本と見せ方の正本のすべてから 1 件以上を読む」（REQ-083）の、見せ方の正本の数え方を決めていません。見せ方の正本から返るのは媒体の規約と禁じた言い回しで、媒体の規約は宛先の媒体ごとに違います。いまのテストは媒体 1 つで見ています。どの媒体で見ても 1 件以上と言うのかは、この文からは決まりません。
- 「選べる語が決まっている鍵」（REQ-079）が、どの鍵を指すかを要件の文に書いていません。いまは 2 つ（媒体の規約の置き場の書き方と、禁じた言い回しの読み方）で、テストはそのうち 1 つで見ています。選べる語を持つ鍵を後から足したとき、同じ拒否を通すことをこの要件が求めるのかは、文からは決まりません。

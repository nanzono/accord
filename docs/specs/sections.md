# 節の読み書きと書き出し

正本のファイルを、節（見出し 1 つとその本文）の単位で読み書きする操作と、正本を 1 つのファイルに書き出す操作の要件です。文面を書くセッションが、正本のファイルを直接開かずに、accord の操作だけで事実を確かめ、書き足し、直せるようにするためのものです。

読みの操作は 3 つです。節を一覧する操作、節を読む操作、事実を検索する操作で、どれも正本のファイルを 1 バイトも書き換えません。公開不可の節も返します。事実を確かめるための読みで、外に出す材料ではないからです。

書く操作は 7 つです。事実を登記する操作は、経歴の正本の節 1 つの末尾に 1 行を足します。節を書き換える操作は、正本のどのファイルの節 1 つの本文も置き換えます。構造の操作（見出しを変える・節を足す・節を消す・節を動かす）は節の並びと見出しを変え、公開可否を変える操作は ID の欄を持つ節の公開可否の欄だけを変えます。正本のファイルは人も AI のセッションも直接触らないので、7 つのファイルの中身の変更は、すべてこれらの操作で行います。どの操作も書く瞬間に守りを当て、通らなければ書かずに、何が通らなかったかと次の一手を返します。節を足す操作のほかは、読んだときの指紋を渡させ、読んだ後に誰かが直していれば上書きしません。書いた後の正本に、書く前に無かった整合の検査の違反か、必須の欄が欠けて読めないブロックが出るなら書きません。ただし「写しの鮮度」の違反は断る理由にせず、読み比べる写しとして返します。書き込みの操作は、変えたファイルをいつも 1 件のコミットにします。

書き出す操作は、正本の各ファイルを 1 つの Markdown につないで、呼ぶ側が渡した書き出し先に書きます。書き出し先は経歴データの置き場の外に限ります。返すのはファイルの名前と字数だけで、書き出し先の場所は返しません。

## 言葉

- **読みの操作**: 決めを読む・材料を取り出す・節を一覧する・節を読む・事実を検索する・書き出すの 6 つ。
- **書き出し先**: 書き出す操作に引数で渡す、経歴データの置き場の外のファイル 1 つ。
- **書き込みの操作**: 決めを登記する・機能を登記する・公開記録を登記する・パッケージを改訂する・事実を登記する・節を書き換える・見出しを変える・節を足す・節を消す・節を動かす・公開可否を変えるの 11 個。
- **構造の操作**: 見出しを変える・節を足す・節を消す・節を動かすの 4 つ。
- **正本のファイル**: 設定の `[source.files]` が指すファイルのうち、提示物（ディレクトリ）を除くもの。同じファイルを 2 つの役割が指すときは 1 つに数える。
- **見出しの道筋**: 最上位の見出しからその節の見出しまでを、` > ` でつないだ文字列。
- **指紋**: いまある関数 `section_fingerprint`（節の本文の SHA-256 の先頭 8 桁）で作った値。
- **適用先の語**: 設定の `[vocabulary]` に書く、媒体ではない決めの適用範囲（例: 会社のホームページ）。

要件の書き方と番号の決まりは [README.md](README.md) にあります。

## REQ-425
節の一覧を求められたとき、accord は正本の各ファイルの節を、ファイルの名前と見出しの道筋と指紋と字数を添えて、正本の並びの順に返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_425`

## REQ-426
節の一覧の節が ID の欄を持つとき、accord はその節の ID と公開可否を添える。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_426`

## REQ-427
ファイルの名前を渡されて節の一覧を求められたとき、accord はそのファイルの節だけを返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_427`

## REQ-428
もし渡されたファイルの名前が正本のファイルに無いなら、accord は正本のファイルの名前をすべて候補に返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_428`

## REQ-429
ID か見出しの道筋を渡されて節を読むとき、accord はその節の本文と指紋を返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_429`

## REQ-430
常に、accord は節の読みで返す本文に、下位の見出しの節の本文を含めない。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_430`

## REQ-431
もし渡された ID か見出しの道筋に当たる節が無いなら、accord は近い見出しの道筋を候補に返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_431`

## REQ-432
もし渡された見出しの道筋に当たる節が 2 つ以上あるなら、accord は本文を返さずに、当たった節をファイルの名前つきの見出しの道筋で候補に返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_432`

## REQ-433
語を渡されて事実を検索するとき、accord はその語を含む行を、ファイルの名前と見出しの道筋と行の文を添えて返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_433`

## REQ-434
事実を検索するとき、accord は全角と半角の違いと大文字と小文字の違いを同じ文字として扱う。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_434`

## REQ-435
もし事実の検索で当たった行が 50 件を超えるなら、accord は先頭の 50 件と当たった総数を返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_435`

## REQ-436
常に、accord は節の一覧と節の読みと事実の検索で、正本のファイルを 1 バイトも書き換えない。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_436`

## REQ-437
節と事実の文と出所と日付を渡されて事実を登記するとき、accord はその節の本文の末尾に、事実の文と日付と出所を書いた箇条の 1 行を足す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_437`

## REQ-438
もし事実の登記で渡された節が経歴の正本に無いなら、accord は書かずに、近い見出しの道筋を候補にして断る。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_438`

## REQ-439
もし事実の登記で事実の文か出所が空なら、accord は書かずに、欠けた欄の名前を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_439`

## REQ-440
もし事実の登記で日付が読めないなら、accord は書かずに、日付の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_440`

## REQ-441
もし事実の文が改行を含むなら、accord は書かずに、事実を 1 件 1 行で登記することを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_441`

## REQ-442
事実の登記が通ったとき、accord は足した行とその節の新しい指紋を返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_442`

## REQ-443
節と新しい本文と読んだときの指紋と理由を渡されて節を書き換えるとき、accord はその節の本文を新しい本文に置き換える。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_443`

## REQ-444
常に、accord は節の書き換えで、その節の見出しの行と下位の見出しの節を変えない。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_444`

## REQ-445
もし渡された指紋がその節のいまの指紋と違うなら、accord は書かずに、いまの指紋と節を読み直すことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_445`

## REQ-446
もし新しい本文が見出しの行を含むなら、accord は書かずに、節の新設と見出しの変更はこの操作でできないことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_446`

## REQ-447
もし新しい本文で節の ID の欄が消えるか値が変わるなら、accord は書かずに、ID の欄を元の値のまま残すことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_447`

## REQ-448
もし節の書き換えの理由が空なら、accord は書かずに、欠けた欄の名前を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_448`

## REQ-449
節の書き換えが通ったとき、accord はその節の新しい指紋を返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_449`

## REQ-450
節の書き換えか事実の登記が通ったとき、accord は書いたことで新しく出た「写しの鮮度」の違反を、読み比べる写しの名前を添えて返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_450`

## REQ-467
もし節の書き換えか事実の登記の後の正本に、書く前に無かった「写しの鮮度」以外の整合の検査の違反が出るなら、accord は書かずに、その違反を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_467`

## REQ-451
もし書き換える節が経歴の正本と職務経歴書の台帳と見せ方の正本のどれにも無いなら、accord は書かずに、その正本を書く操作の名前を候補に返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_451`
- status: superseded by REQ-485

## REQ-452
書き出しを求められたとき、accord は正本の各ファイルの中身を、ファイルの名前の見出しを付けて、設定の書き出し先の 1 つの Markdown のファイルに書く。

- 関係するファイル: `src/accord/services/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_452`
- status: superseded by REQ-525

## REQ-453
もし設定の書き出し先が正本の置き場か提示物の置き場の中なら、accord は書き出し先の鍵の名前を添えて起動をやめる。

- 関係するファイル: `src/accord/vocabulary/settings.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_453`
- status: superseded by REQ-525

## REQ-454
もし設定に書き出し先が書かれていないなら、accord は書き出しを求められても書かずに、設定に足す鍵の名前を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_454`
- status: superseded by REQ-525

## REQ-455
書き出しが通ったとき、accord は書いたファイルの名前と字数を返し、書き出し先の絶対パスを返さない。

- 関係するファイル: `src/accord/services/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_455`

## REQ-468
もし節の書き換えの新しい本文で節の公開可否の欄が消えるか値が変わるなら、accord は書かずに、公開可否の欄を元の値のまま残すことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_468`
- status: superseded by REQ-536
- 注: 断りの次の一手は REQ-501 が改める（公開可否を変える操作の名前を返す）。断ることそのものは、この要件のまま変わらない。

## REQ-469
もし事実の登記で足す行によって節の ID か公開可否の欄の値が変わるなら、accord は書かずに、事実の文を欄の書き方で書かないことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_469`

## REQ-470
節と新しい見出しと読んだときの指紋と理由を渡されて見出しを変えるとき、accord はその節の見出しの文字だけを置き換え、見出しの深さと本文と下位の節を変えない。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_470`

## REQ-471
もし新しい見出しが空か、改行を含むか、「#」で始まるなら、accord は書かずに、見出しの書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_471`

## REQ-472
親の節と見出しと本文と理由を渡されて節を足すとき、accord は親の節より 1 段深い見出しの節を、親の節の下位の節の末尾に足す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_472`

## REQ-473
節を足すときに前に置く節が渡されたとき、accord は足す節を、親の節の下位にあるその節の直前に置く。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_473`

## REQ-474
もし前に置く節が親の節の直下の節でないなら、accord は書かずに、親の節の直下の節の見出しの道筋を候補に返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_474`

## REQ-475
もし親の節の見出しの深さが 6 なら、accord は書かずに、それより深い見出しを作れないことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_475`

## REQ-476
節と読んだときの指紋と理由を渡されて節を消すとき、accord はその節の見出しの行と本文を消す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_476`

## REQ-477
もし消す節が下位の節を持つなら、accord は書かずに、先に下位の節を消すことと下位の節の見出しの道筋を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_477`

## REQ-491
節と新しい親の節と読んだときの指紋と理由を渡されて節を動かすとき、accord はその節を下位の節ごと新しい親の節の下位の節の末尾へ移し、見出しの深さを新しい親より 1 段深くそろえ、下位の節の深さも同じ段数だけずらし、1 回の書き込みとして記録する。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_491`

## REQ-492
節を動かすときに前に置く節が渡されたとき、accord は動かす節を、新しい親の節の直下にあるその節の直前に置く。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_492`

## REQ-493
もし新しい親の節が動かす節そのものか、その下位の節なら、accord は書かずに、自分の下へは動かせないことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_493`

## REQ-494
もし動かした後に深さが 6 を超える見出しが出るなら、accord は書かずに、深さが足りないことと超える見出しの道筋を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_494`

## REQ-495
もし動かす節と新しい親の節が別のファイルにあるなら、accord は書かずに、ファイルをまたいで動かせないことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_495`

## REQ-496
ID の欄を持つ節と新しい公開可否と読んだときの指紋と理由を渡されて公開可否を変えるとき、accord はその節の公開可否の欄の値だけを置き換え、欄が無ければ ID の欄の行の直後に公開可否の欄の行を足す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_496`

## REQ-497
もし公開可否を変える節が ID の欄を持たないなら、accord は書かずに、公開可否は ID の欄を持つ節にだけ置くことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_497`

## REQ-498
もし新しい公開可否が空か改行を含むなら、accord は書かずに、公開可否の書き方の例を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_498`

## REQ-499
公開可否を「公開不可」で始まる値からそれ以外の値へ変えることが通ったとき、accord はその節が材料の取り出しに新しく出ることと、元の値と新しい値と理由を返し、コミットの説明にも元の値と新しい値と理由を書く。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_499`

## REQ-478
もし見出しを変えるか節を足すか節を動かした後に、同じ親の下に同じ見出しの節が 2 つ以上できるなら、accord は書かずに、重なる見出しの道筋を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_478`

## REQ-479
もし見出しを変えるか節を消すか節を動かすか公開可否を変えるときに渡された指紋がその節のいまの指紋と違うなら、accord は書かずに、いまの指紋と節を読み直すことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_479`

## REQ-480
もし足す節の本文が見出しの行を含むなら、accord は書かずに、下位の節は節を足す操作を重ねて作ることを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_480`

## REQ-481
もし見出しを変えるか節を足すか節を消すか節を動かすか公開可否を変えるときの理由が空なら、accord は書かずに、欠けた欄の名前を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_481`

## REQ-482
もし見出しを変えるか節を足すか節を消すか節を動かすか公開可否を変えた後の正本に、書く前に無かった「写しの鮮度」以外の整合の検査の違反が出るなら、accord は書かずに、その違反を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_482`

## REQ-483
見出しを変えるか節を足すか節を消すか節を動かすか公開可否を変えることが通ったとき、accord は書いたことで新しく出た「写しの鮮度」の違反を、読み比べる写しの名前を添えて返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_483`

## REQ-490
もし事実の登記か節の書き換えか見出しの変更か節の追加か節の削除か節の移動か公開可否の変更の後の正本に、書く前に無かった、必須の欄が欠けて読めないブロックが出るなら、accord は書かずに、そのブロックと欠けた欄の名前を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_490`

## REQ-485
正本のどのファイルの節を書き換えるときも、accord は経歴の正本の節を書き換えるときと同じ断りの条件で書く。（REQ-451 に取って代わる）

- 関係するファイル: `src/accord/services/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_485`

## REQ-500
常に、accord は断りの理由と次の一手とサーバーの説明に、正本のファイルを人か AI のセッションが直接直すことも、置き場で git を直接操作することも書かない。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/services/recording.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_500`

## REQ-501
もし節の書き換えの新しい本文で公開可否の欄が消えるか値が変わるなら、accord は書かずに、公開可否を変える操作の名前を次の一手に返す。（REQ-468 の断りの次の一手を改める）

- 関係するファイル: `src/accord/services/sections.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_501`
- status: superseded by REQ-537

## REQ-487
起動されたとき、accord はサーバーの説明に、見出しの変更と節の追加と節の削除と節の移動と公開可否の変更も accord の操作で行うことを書く。

- 関係するファイル: `src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_smoke.py -k REQ_487`

## REQ-488
常に、accord は見出しの変更と節の追加と節の削除と節の移動と公開可否の変更で変えたファイルを 1 件の git のコミットにし、もし書き込みの記録が無効な置き場なら、書かずに書き込みの記録が要ることを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/services/recording.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_488`
- status: superseded by REQ-513

## REQ-530
親の節を渡されずにファイルと見出しと本文と理由を渡されて節を足すとき、accord はそのファイルの末尾に深さ 1 の節を足し、前に置く深さ 1 の節が渡されればその直前に置く。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_530`

## REQ-531
新しい親の節を渡されずに節を動かすとき、accord はその節を下位の節ごと同じファイルの深さ 1 の節として末尾へ移し、前に置く深さ 1 の節が渡されればその直前に置き、下位の節の深さも同じ段数だけずらす。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_531`

## REQ-528
正本全体の整合を検査するとき、accord はパッケージ定義の仮説の状態の欄の値から末尾の括弧書きの注を落とした語が、語彙のパッケージの仮説の状態の語のどれかであるかを見て、違えば違反を返す。

- 関係するファイル: `src/accord/services/consistency.py`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_528`

## REQ-529
正本全体の整合を検査するとき、accord は売り方の決めの適用範囲の欄の値から末尾の括弧書きの注を落とした語が、媒体の名前か決めの適用先の語か「全体」のどれかであるかを見て、違えば違反を返す。

- 関係するファイル: `src/accord/services/consistency.py`、`src/accord/ontology.yaml`
- 検証手順: `uv run pytest tests/test_consistency.py -k REQ_529`

## REQ-532
決めを読むか材料を取り出すときに媒体に当たる決めを選ぶとき、accord は適用範囲の値から末尾の括弧書きの注を落とした語で媒体の名前と比べる。

- 関係するファイル: `src/accord/services/positioning.py`
- 検証手順: `uv run pytest tests/test_positioning.py -k REQ_532`

## REQ-533
もし節を足すか動かすときに渡されたファイルが正本のファイルのどれでもないなら、accord は親の節を渡されていても書かずに、正本のファイルの名前を候補に返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_533`

## REQ-534
公開可否の欄の行を 2 行以上持つ節の公開可否を、何行目かの番号を渡されて変えるとき、accord はその番号の行の値だけを置き換える。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_534`

## REQ-535
もし公開可否の欄の行を 2 行以上持つ節の公開可否を変えるときに番号が渡されないか、番号に当たる行が無いなら、accord は書かずに、いまの公開可否の行を番号つきで候補に返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_535`

## REQ-536
節の書き換えで公開可否の行が変わるとき、もし呼ぶ側が書いた後の公開可否の行の並び（申告）を渡し、それが書いた後の実際の並びと一致するなら、accord は書き、返り値とコミットの説明に変わる前と後の公開可否の行をすべて載せる。（REQ-468 に取って代わる）

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_536`

## REQ-537
もし節の書き換えで公開可否の行が変わるのに申告が無いか、申告が書いた後の実際の並びと違うなら、accord は書かずに、書いた後の実際の並びと申告の欄の名前を断りに返す。（REQ-501 に取って代わる）

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_537`

## REQ-538
もし書く前に公開可否の行を 2 行以上持つ節で、書いた後に公開可否の行を持たない箇条書きの項目が増えるなら、accord は書かずに、その項目を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_538`

## REQ-539
公開可否の行が変わる節の書き換えが通り、節の公開可否が「公開不可」で始まる値から外れたとき、accord はその節が材料の取り出しに新しく出ることを返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_539`

## REQ-540
常に、accord は、accord の形の文書に書いた「変更の種類 × データの形」の表の各マスの変更を、accord の操作で行えるか、決めにある理由で断る。

- 関係するファイル: `docs/data-format.md`、`src/accord/services/sections.py`、`src/accord/repository/sections.py`
- 検証手順: `uv run pytest tests/test_completeness.py`

## REQ-541
もし書き込みの操作の後の正本に、書く前に無かった、欄の値が型に合わず読めないブロックが出るなら、accord は書かずに、そのブロックと欄の名前と読めなかった理由を断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/repository/markdown_repository.py`、`src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_541`

## REQ-525
書き出し先のパスを渡されて書き出すとき、accord は正本の各ファイルを 1 つにつないだ Markdown をそのパスに書き、もしそのパスが置き場の中なら書かずに断る。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_525`

## REQ-555
もし書き出し先のパスが提示物の置き場の中なら、accord は書かずに、置き場の外のパスで呼び直すことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_555`

## REQ-556
もし書き出し先のパスに既にファイルがあるなら、accord は書かずに、別の名前にするか先にそのファイルを消してから呼び直すことを断りに返す。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_556`

## REQ-557
もし書き出し先のパスが symlink なら、accord は書かずに断る。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_557`

## REQ-558
もし書き出し先の親ディレクトリが無いなら、accord はディレクトリを作らず、書かずに断る。

- 関係するファイル: `src/accord/services/sections.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_sections.py -k REQ_558`

## 未決の質問

- 「経歴の正本に無いなら」（REQ-438）の「経歴の正本」が、設定の `career` が指すファイルだけを指すのか、受託案件（`engagements`）が別のファイルのときにそのファイルも含むのかを決めていません。いまの実装は `career` が指すファイルだけに書きます。受託案件を別のファイルに置く正本（同梱の 1 つ目の見本）では、受託案件の節に事実を登記できません（節の書き換えでは直せます）。
- 「見出しの道筋」（REQ-429）に、最初の見出しより前の本文（見出しを持たない塊）をどう数えるかを決めていません。いまの実装は、その塊を節の一覧にも節の読みにも入れず、事実の検索だけが見出しの道筋を空にして行を返します。
- 「書く前に無かった違反」（REQ-467）の「同じ違反」の見分け方を決めていません。いまの実装は、写しの鮮度は直し先の文まで、ほかの違反は制約とファイルと場所で比べます。同じ場所の同じ違反の言い回しが変わっただけでは、新しい違反と数えません。

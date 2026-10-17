# 書きの守り

正本に書く操作は 4 つあります。機能の登記、パッケージの改訂、決めの登記、公開記録の登記です。
どれも、守るべきことを先に全部確かめ、通ると決まってから 1 度だけ正本に書きます。

このファイルは、その 4 つが断るときに必ず守ることを述べます。断りは 4 つの約束を持ちます。
次に呼ぶ操作の名前を返すこと、欠けた欄の名前と候補と書き方の例のうち少なくとも 1 つを返すこと、
何が通らなかったかを理由に返すこと、そして正本のファイルを 1 バイトも書き換えないことです。
はじめの 3 つは、断りを受け取った側が正本を読み直さずに呼び直せるようにするためです。最後の 1 つは、
途中まで書いてから断る経路を残さないためです。

どの制約に当たると断るか、その断りの理由に何を書くかは、このファイルではなく機能ごとの要件の
ファイルが持ちます。機能の登記とパッケージの改訂は [offering.md](offering.md)、決めの登記は
[positioning.md](positioning.md)、公開記録の登記は [public-records.md](public-records.md)、
ID の形式と ID の一意性は [id-reference.md](id-reference.md) です。要件の書き方と番号の決まりは
[README.md](README.md) にあります。

このファイルは、書き込みを git に記録することと、accord を通さない変更（置き場の未コミットの変更と、
accord 以外のコミット）を見つけて断ることと、取り消しの 2 つの操作（コミットを取り消す・未コミットの変更を
捨てる）の要件も持ちます。ここで使う言葉は次のとおりです。

- **移行のコミット**: 置き場の git の履歴のうち、`Accord-Operation: migrate_data` の行を持つ最古のコミット。accord が履歴から機械で見つけ、設定や引数では受けない。accord 以外のコミットの検出は、このコミットより後だけを見る。
- **accord 以外のコミット**: 移行のコミットより後の、操作の名前を示す行（`Accord-Operation: <操作の名前>`）を持たないコミット。後の accord の打ち消しのコミットが `Accord-Reverts: <長い識別子>` の行で名指ししたものは数えない。

## REQ-322
常に、accord は書きの操作が断るとき、次に呼ぶ操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/services/positioning.py`、`src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_write_guards.py -k REQ_322`

## REQ-323
常に、accord は書きの操作が断るとき、欠けた欄の名前と候補と書き方の例のうち少なくとも 1 つを断りに返す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/services/positioning.py`、`src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_write_guards.py -k REQ_323`

## REQ-324
常に、accord は書きの操作が断るとき、何が通らなかったかを断りの理由に返す。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/services/positioning.py`、`src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_write_guards.py -k REQ_324`

## REQ-325
常に、accord は書きの操作が断るとき、正本の置き場のファイルを 1 バイトも書き換えない。

- 関係するファイル: `src/accord/services/offering.py`、`src/accord/services/positioning.py`、`src/accord/services/public_records.py`
- 検証手順: `uv run pytest tests/test_write_guards.py -k REQ_325`

## REQ-513
常に、accord は書き込みの操作で変えたファイルを、書き込み 1 件につき 1 件の git のコミットに記録し、コミットの説明に操作の名前を示す行（`Accord-Operation: <操作の名前>`）を書く。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_513`

## REQ-514
もし書く前に置き場の中に未コミットの変更があるなら、accord は書かずに、accord を通さない変更があることと、変更のあるファイルの名前と、未コミットの変更を捨てる操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_514`

## REQ-515
もし移行のコミットより後に、操作の名前を示す行を持たないコミットが置き場の履歴にあるなら、accord は書かずに、そのコミットの短い識別子と、コミットを取り消す操作の名前を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_515`

## REQ-516
読みの操作が呼ばれたとき、もし未コミットの変更か accord 以外のコミットがあるなら、accord は返り値の知らせに、その件数と、捨てる操作か取り消す操作の名前を載せる。

- 関係するファイル: `src/accord/services/watch.py`、`src/accord/services/recording.py`、`src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_516`

## REQ-547
もし置き場の履歴に移行のコミットが無いなら、accord は根のコミットを起点にして、それより後の印の無いコミットを accord 以外のコミットと数え、根のコミットは取り消さない。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_547`

## REQ-550
もし操作の名前を示す行を持たないコミットを、それより後の accord の打ち消しのコミットが打ち消したコミットとして名指し（`Accord-Reverts: <長い識別子>` の行）しているなら、accord はそのコミットを accord 以外のコミットと数えない。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_write_commits.py -k REQ_550`

## REQ-517
コミットの識別子と理由を渡されてコミットを取り消すとき、accord はそのコミットの変更を打ち消すコミットを 1 件作る。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_history.py -k REQ_517`

## REQ-518
もし取り消すコミットが移行のコミットそのものか、それより前のコミットなら、accord は書かずに、取り消せる範囲を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_history.py -k REQ_518`

## REQ-519
もし打ち消しが後のコミットの変更とぶつかるなら、accord は書かずに置き場をそのままに戻し、ぶつかるファイルの名前と、後のコミットから順に取り消すことを断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_history.py -k REQ_519`

## REQ-520
もし打ち消した後の正本に、取り消す前に無かった「写しの鮮度」以外の整合の検査の違反が出るなら、accord は書かずに置き場をそのままに戻し、その違反を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_history.py -k REQ_520`

## REQ-521
理由を渡されて未コミットの変更を捨てるとき、accord は捨てる前の差分を返り値に載せ、置き場の作業ツリーを最後のコミットの状態に戻す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_history.py -k REQ_521`

## REQ-543
もし取り消すコミットの識別子が置き場の履歴に無いか、合流のコミットなら、accord は書かずに、取り消せるコミットの短い識別子を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_history.py -k REQ_543`

## REQ-548
もし未コミットの変更を捨てるときに捨てる変更が無いなら、accord は書かずに通し、空の差分と、捨てる変更が無かったことを返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_history.py -k REQ_548`

## REQ-553
もし取り消すコミットを、それより後の accord の打ち消しのコミットが既に打ち消しているなら、accord は書かずに、取り消せるコミットの短い識別子を断りに返す。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`、`src/accord/server/app.py`
- 検証手順: `uv run pytest tests/test_history.py -k REQ_553`

## REQ-551
移行の操作が呼ばれたとき、accord は操作の名前を示す行を持たないコミットが置き場の履歴にあっても、それを理由に移行を断らない。

- 関係するファイル: `src/accord/services/recording.py`
- 検証手順: `uv run pytest tests/test_migration.py -k REQ_551`

## REQ-552
移行の操作が呼ばれたとき、accord は書く前の未コミットの変更を vocabulary.md と accord.toml の 2 つのファイルだけで見る。

- 関係するファイル: `src/accord/services/recording.py`、`src/accord/repository/git_commits.py`
- 検証手順: `uv run pytest tests/test_migration.py -k REQ_552`

## 未決の質問

- この 4 件は、書きの操作が執行する制約をすべて覆っているかどうかを制約の単位で見ます。同じ制約を
  別の崩し方で外したとき（たとえば必須の欄のうち別の 1 つを欠いた入力）に同じ 4 つが守られるかは、
  要件からは決まりません。1 つの制約に確かめる経路が 1 本あれば、この 4 件は満たされます。

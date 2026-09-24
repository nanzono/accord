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

## 未決の質問

- この 4 件は、書きの操作が執行する制約をすべて覆っているかどうかを制約の単位で見ます。同じ制約を
  別の崩し方で外したとき（たとえば必須の欄のうち別の 1 つを欠いた入力）に同じ 4 つが守られるかは、
  要件からは決まりません。1 つの制約に確かめる経路が 1 本あれば、この 4 件は満たされます。

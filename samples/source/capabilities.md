<!-- fictional-data: この中身はすべて架空の人物と架空の案件です -->

# 機能の台帳

提供できる仕事を 1 行 1 つで持つ。節の見出しが分類で、選べる分類は設定ファイルの
`capability_categories` が決める。表の 1 列目が ID で、パッケージはこの ID で機能を束ねる。
裏づけの節には、`career.md` か `engagements.md` の節の ID、または `public_records.md` の
公開記録の ID を書き、複数あるときは半角の `/` で区切る。

## データの置き場をつくる

| ID | 機能名 | 説明 | 裏づけの節 |
|---|---|---|---|
| collect-sales-data | 分かれている売上データを 1 か所に集める | 部署や拠点ごとに分かれた数字を、1 つの置き場にそろえて入れる | teramina-delivery / yukinoha-quality |
| stable-daily-ingest | 日々の取り込みを止まらない形にする | 毎日の取り込みを自動で回し、止まったときに気づける形にする | teramina-delivery |

## 数字を読める形にする

| ID | 機能名 | 説明 | 裏づけの節 |
|---|---|---|---|
| metrics-by-role | 見る人の役割ごとに指標を決める | 誰が何を見て何を決めるかから、見る数字を絞る | teramina-delivery / yukinoha-quality |

## 決めて、進める

| ID | 機能名 | 説明 | 裏づけの節 |
|---|---|---|---|
| requirements-forum | 要件を決める場をつくる | 決まっていないことを一覧にし、決める人と決める日を置く | nagisa-publishing |
| plan-from-decisions | 決まったことを段取りに落とす | 決まったことを工程と期日に分け、遅れが出た時点で分かる形にする | nagisa-publishing / meetup-talk-publishing |

## 引き継げる形にする

| ID | 機能名 | 説明 | 裏づけの節 |
|---|---|---|---|
| handover-operations | 運用の手順を引き渡す | 自社の担当者だけで回せるところまで、手順と勘どころを渡す | yukinoha-quality / freelance-solo |

## 人と体制をつくる

| ID | 機能名 | 説明 | 裏づけの節 |
|---|---|---|---|
| grow-inhouse-owner | 内製の担当者を育てる | 引き渡した後の担当者に付き、最初の数か月の判断を一緒に行う | yukinoha-quality |

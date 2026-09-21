# ID で結ぶこと

正本の項目どうしは、見出しの文字ではなく ID で結びます。ID は人が振る短い名前で、英小文字・数字・
ハイフンで 3〜40 字、先頭と末尾は英数字です。見出しは人が読むための表示名なので、書き換えても
指した先は切れません。

ID を持つのは、指される側の 5 つの型です。職歴の枠・受託案件・公開記録・機能・パッケージがそれで、
どれも ID の欄を必須で持ち、同じ ID は正本全体で 1 つの項目にしか付きません。ID で指す側は 4 つ
あります。機能の裏づけの節、公開記録の由来の節、職務経歴書の台帳の出典の節、提示物の未反映の
注記が指す節です。この 4 つは、指す先の母集団が違うだけで、指された値が読めないときの言い分けは
同じです。

指された値が読めないとき、accord は 3 通りに言い分けます。値が ID の形に合わないとき、形は合うが
正本のどこにも無いとき、照らす相手が 1 件も読めていないときです。「無い」の一言で片づけると、
正本に実在する節を指したときにも、合っている側を書き換える誘導になります。とくに区切りを取り違えた
値（半角のスラッシュ以外でつないだもの）は、推測ではなく形の検査で断定します。

違反にも断りにも、候補はそのまま渡し直せる ID だけを載せます。どの項目のことかは、候補の欄ではなく
文の側に表示名を添えて示します。要件の書き方と番号の決まりは [README.md](README.md) にあります。

## REQ-247
機能の裏づけの節が正本にある ID を指しているとき、accord はその参照を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_247`

## REQ-248
もし機能の裏づけの節の値が ID の形に合わないなら、accord はその参照を違反に挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_248`

## REQ-249
もし機能の裏づけの節の値が ID の形に合わないなら、accord は ID の形を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_249`

## REQ-250
もし機能の裏づけの節の値が ID の形に合わないなら、accord は見出しや名前をその節の ID に置き換えることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_250`

## REQ-251
もし機能の裏づけの節の値が ID の形に合わないなら、accord は 2 つ以上を書くときの区切りが半角のスラッシュであることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_251`

## REQ-252
もし機能の裏づけの節の値が ID の形に合わないなら、accord は実在する ID を違反の候補に返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_252`

## REQ-253
もし機能の裏づけの節の値が ID の形に合わないなら、accord は候補の ID の表示名を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_253`

## REQ-254
もし機能の裏づけの節を照らす相手が 1 件も読めていないなら、accord は候補を出せる材料が無いことを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_254`

## REQ-255
もし機能の裏づけの節を照らす相手が 1 件も読めていないなら、accord は設定の読み方の絞りか正本の節の位置を確かめることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_255`

## REQ-256
もし機能の裏づけの節を照らす相手が 1 件も読めていないなら、accord は違反の候補を空で返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_256`

## REQ-257
公開記録の由来の節が正本にある ID を指しているとき、accord はその参照を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_257`

## REQ-258
もし公開記録の由来の節の値が ID の形に合わないなら、accord はその参照を違反に挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_258`

## REQ-259
もし公開記録の由来の節の値が ID の形に合わないなら、accord は ID の形を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_259`

## REQ-260
もし公開記録の由来の節の値が ID の形に合わないなら、accord は見出しや名前をその節の ID に置き換えることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_260`

## REQ-261
もし公開記録の由来の節の値が ID の形に合わないなら、accord は 2 つ以上を書くときの区切りが半角のスラッシュであることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_261`

## REQ-262
もし公開記録の由来の節の値が ID の形に合わないなら、accord は実在する ID を違反の候補に返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_262`

## REQ-263
もし公開記録の由来の節の値が ID の形に合わないなら、accord は候補の ID の表示名を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_263`

## REQ-264
もし公開記録の由来の節を照らす相手が 1 件も読めていないなら、accord は候補を出せる材料が無いことを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_264`

## REQ-265
もし公開記録の由来の節を照らす相手が 1 件も読めていないなら、accord は設定の読み方の絞りか正本の節の位置を確かめることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_265`

## REQ-266
もし公開記録の由来の節を照らす相手が 1 件も読めていないなら、accord は違反の候補を空で返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_266`

## REQ-267
職務経歴書の台帳の出典の節が正本にある ID を指しているとき、accord はその参照を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_267`

## REQ-268
もし職務経歴書の台帳の出典の節の値が ID の形に合わないなら、accord はその参照を違反に挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_268`

## REQ-269
もし職務経歴書の台帳の出典の節の値が ID の形に合わないなら、accord は ID の形を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_269`

## REQ-270
もし職務経歴書の台帳の出典の節の値が ID の形に合わないなら、accord は見出しや名前をその節の ID に置き換えることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_270`

## REQ-271
もし職務経歴書の台帳の出典の節の値が ID の形に合わないなら、accord は 2 つ以上を書くときの区切りが半角のスラッシュであることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_271`

## REQ-272
もし職務経歴書の台帳の出典の節の値が ID の形に合わないなら、accord は実在する ID を違反の候補に返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_272`

## REQ-273
もし職務経歴書の台帳の出典の節の値が ID の形に合わないなら、accord は候補の ID の表示名を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_273`

## REQ-274
もし職務経歴書の台帳の出典の節を照らす相手が 1 件も読めていないなら、accord は候補を出せる材料が無いことを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_274`

## REQ-275
もし職務経歴書の台帳の出典の節を照らす相手が 1 件も読めていないなら、accord は設定の読み方の絞りか正本の節の位置を確かめることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_275`

## REQ-276
もし職務経歴書の台帳の出典の節を照らす相手が 1 件も読めていないなら、accord は違反の候補を空で返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_276`

## REQ-277
提示物の未反映の注記が指す節が正本にある ID を指しているとき、accord はその参照を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_277`

## REQ-278
もし提示物の未反映の注記が指す節の値が ID の形に合わないなら、accord はその参照を違反に挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_278`

## REQ-279
もし提示物の未反映の注記が指す節の値が ID の形に合わないなら、accord は ID の形を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_279`

## REQ-280
もし提示物の未反映の注記が指す節の値が ID の形に合わないなら、accord は見出しや名前をその節の ID に置き換えることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_280`

## REQ-281
もし提示物の未反映の注記が指す節の値が ID の形に合わないなら、accord は 2 つ以上を書くときの区切りが半角のスラッシュであることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_281`

## REQ-282
もし提示物の未反映の注記が指す節の値が ID の形に合わないなら、accord は実在する ID を違反の候補に返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_282`

## REQ-283
もし提示物の未反映の注記が指す節の値が ID の形に合わないなら、accord は候補の ID の表示名を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_283`

## REQ-284
もし提示物の未反映の注記が指す節を照らす相手が 1 件も読めていないなら、accord は候補を出せる材料が無いことを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_284`

## REQ-285
もし提示物の未反映の注記が指す節を照らす相手が 1 件も読めていないなら、accord は設定の読み方の絞りか正本の節の位置を確かめることを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_285`

## REQ-286
もし提示物の未反映の注記が指す節を照らす相手が 1 件も読めていないなら、accord は違反の候補を空で返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_286`

## REQ-287
もし正本の項目を指す値が ID の形に合いながら正本のどこにも無いなら、accord はその参照を違反に挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_287`

## REQ-288
もし正本の項目を指す値が ID の形に合いながら正本のどこにも無いなら、accord はその値がいまの正本に読めている ID に無いことを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_288`

## REQ-289
もし正本の項目を指す値が ID の形に合いながら正本のどこにも無いなら、accord は近い ID を違反の候補に返す。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_289`

## REQ-290
もし正本の項目を指す値が ID の形に合いながら正本のどこにも無いなら、accord は候補の ID の表示名を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_290`

## REQ-291
常に、accord は職歴の枠と受託案件と公開記録と機能とパッケージの ID を、正本全体で形式と一意性に当てる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_291`

## REQ-292
もし正本の項目の ID が形に合わないなら、accord はその項目 1 件につき違反を 1 件挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_292`

## REQ-293
もし正本の項目の ID が形に合わないなら、accord はその項目の ID の欄を違反の場所に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_293`

## REQ-294
もし正本の項目の ID が形に合わないなら、accord はその ID を指している側も同じ値に直すことを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_294`

## REQ-295
もし同じ ID を 2 つ以上の項目が持つなら、accord はその ID を持つ項目ごとに違反を挙げる。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_295`

## REQ-296
もし同じ ID を 2 つ以上の項目が持つなら、accord は使われている数とその場所を違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_296`

## REQ-297
もし同じ ID を 2 つ以上の項目が持つなら、accord はどちらか一方を別の値に直し、その ID を指している側も直すことを違反の直し先に書く。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_297`

## REQ-298
もし設定に公開記録の置き場が無いなら、accord は公開記録の ID を形式と一意性の検査に入れない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_298`

## REQ-299
正本の項目の見出しが書き換えられたとき、accord はその項目を ID で指している参照を違反にしない。

- 関係するファイル: `src/accord/services/consistency.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_299`

## REQ-300
正本の項目の見出しが書き換えられたとき、accord は材料の裏づけの見出しに書き換えた後の見出しを返す。

- 関係するファイル: `src/accord/services/material.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_300`

## REQ-301
裏づけの節を材料に載せるとき、accord はその節の本文から ID の行を落とす。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_301`

## REQ-302
裏づけの節を材料に載せるとき、accord はその節の本文の ID 以外の欄の行を落とさない。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_302`

## REQ-303
ID のラベルを読み替える設定で呼ばれたとき、accord は読み替えた後のラベルの行を裏づけの本文から落とす。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_303`

## REQ-304
もし正本の節が ID の行を持たないなら、accord はその節を裏づけとして指せる節に入れない。

- 関係するファイル: `src/accord/repository/markdown_repository.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_304`

## REQ-305
もし書きの操作に渡された ID が形に合わないなら、accord はその項目を正本に書かない。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_305`

## REQ-306
もし書きの操作に渡された ID が形に合わないなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_306`

## REQ-307
もし書きの操作に渡された ID が形に合わないなら、accord は渡された ID と ID の形を断りの理由に書く。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_307`

## REQ-308
もし書きの操作に渡された ID が形に合わないなら、accord は正本にすでにある ID を例として断りの理由に書く。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_308`

## REQ-309
もし書きの操作に渡された ID が形に合わないなら、accord は呼ばれた操作の名前を次に呼ぶ操作として断りに返す。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_309`

## REQ-310
もし書きの操作に渡された ID が形に合わないなら、accord は正本にすでにある ID を断りの候補に返す。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_310`

## REQ-311
もし書きの操作に渡された ID が形に合わないなら、accord はID の書き方の例を断りに返す。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_311`

## REQ-312
もし書きの操作に渡された ID を別の項目がすでに使っているなら、accord はその項目を正本に書かない。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_312`

## REQ-313
もし書きの操作に渡された ID を別の項目がすでに使っているなら、accord は当たった制約の名前を断りに返す。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_313`

## REQ-314
もし書きの操作に渡された ID を別の項目がすでに使っているなら、accord はその ID を使っている項目の表示名を断りの理由に書く。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_314`

## REQ-315
もし書きの操作に渡された ID を別の項目がすでに使っているなら、accord はID が正本全体で 1 つの項目にしか付かないことを断りの理由に書く。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_315`

## REQ-316
もし書きの操作に渡された ID を別の項目がすでに使っているなら、accord は呼ばれた操作の名前を次に呼ぶ操作として断りに返す。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_316`

## REQ-317
もし書きの操作に渡された ID を別の項目がすでに使っているなら、accord は断りの候補を空で返す。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_317`

## REQ-318
もし書きの操作に渡された ID を別の項目がすでに使っているなら、accord はまだ使われていない ID を渡して呼び直すことを断りの書き方の例に入れる。

- 関係するファイル: `src/accord/models/results.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_318`

## REQ-319
パッケージの改訂で、差し替える節がすでに持っている ID を渡されたとき、accord はその ID を重なりとして断らない。

- 関係するファイル: `src/accord/services/offering.py`
- 検証手順: `uv run pytest tests/test_id_reference.py -k REQ_319`

## 未決の質問

- 「照らす相手が 1 件も読めていない」状態（REQ-254〜256、REQ-264〜266、REQ-274〜276、
  REQ-284〜286）を、4 つの指し方それぞれでどう作るかは、要件からは決まりません。指す側が読めた
  まま、照らす相手だけが空になる設定は、指し方ごとに違う正本を読めなくすることで作ります。どれか
  1 つの指し方でこの状態を作れないなら、その指し方の 3 件は確かめようがないので、要件の側を
  見直します。
- 「どこにも無い」ときの 4 件（REQ-287〜290）だけは、指し方ごとに割っていません。この分岐だけは
  返る文が指し方ごとに違い、その文の中身は整合の検査の要件（[consistency-check.md](consistency-check.md)）が
  すでに述べているためです。そのため、40 件は指し方ごとに並び、4 件は指し方に依らない形で並びます。
  この不揃いの理由を、要件の並びだけから読み取れるかは決まっていません。

"""公開記録を登記する操作のテスト。

見るのは 2 つ。通る入力が 1 ブロックとして積まれてそのまま読み戻せることと、置き場・必須の欄・
種類の語彙・役割の語彙・由来の節の 5 つの断りが、書かずに何を返すかである。断りは、返り値に
現れる欄 1 つにつきテストを 1 本置き、関数名の番号で docs/specs/public-records.md の要件を指す。
すべて同梱のサンプルの一時的な写しの上で走らせる。
"""

from __future__ import annotations

from pathlib import Path

from accord.models.results import ID_FORMAT_TEXT, PublicRecordDraft
from accord.repository.markdown_repository import MarkdownRepository
from accord.services.public_records import PublicRecordService
from accord.vocabulary.settings import Settings, load_settings
from conftest import source_digest

# 同梱のサンプルにある受託案件の ID と、その見出し。通る入力の土台にして、1 か所だけ崩す。
KNOWN_SECTION = "nagisa-publishing"
KNOWN_SECTION_HEADING = "ナギサ書房 刊行計画の進行管理"

# 語の一覧の外にある種類と役割。どちらも断りを起こすための値。
UNKNOWN_KIND = "ポッドキャスト"
UNKNOWN_ROLE = "司会"

# 公開記録の型が必須で持つ 6 つの欄。型の正本からは導かず、ここに文字どおり書く。
# 導くと、正本から欄を 1 つ消しても回す場合が 1 つ減るだけで、テストは通ってしまう。
PUBLIC_RECORD_REQUIRED_FIELDS = ("id", "name", "kind", "published_on", "publisher", "role")

# 同じ 6 つの欄の、入力の鍵と、断りに出る欄の名前の組。これも型の正本からは導かず、文字どおり書く。
# 1 つだけを空にした登記を 6 通り回し、どの欄を空にしても必須の欄の断りが返ることを見る。
# 型の正本からどれか 1 つの欄の必須の宣言を外すと、その欄の回は別のルールの断り
# （ID の形式、種類や役割の語彙）になるか、登記が通ってしまい、名前の比べで落ちる。
PUBLIC_RECORD_REQUIRED_FIELD_LABELS = (
    ("id", "ID"),
    ("name", "名前"),
    ("kind", "種類"),
    ("published_on", "日付"),
    ("publisher", "発行元か主催"),
    ("role", "役割"),
)

# 必須の欄が欠けたときの断りの名前。
PUBLIC_RECORD_REQUIRED_FIELDS_RULE = "公開記録の必須欄"

# 型の正本のルールの名前。断りにそのまま出る。
PUBLIC_RECORD_KIND_VOCABULARY = "公開記録の種類の語彙"
PUBLIC_RECORD_ROLE_VOCABULARY = "公開記録の役割の語彙"

# 設定から抜くと、公開記録を使わない正本（この段より前の設定と同じ形）になる 3 行の書き出し。
PUBLIC_RECORD_SETTING_LINES = (
    "public_records = ",
    "public_record_kinds = ",
    "public_record_roles = ",
)


def _register(settings: Settings, **changes) -> object:
    """通る公開記録の入力を土台に、渡された欄だけを差し替えて登記を呼ぶ。"""
    draft = {
        "id": "data-meetup-talk",
        "name": "配送データの集約を話した勉強会の発表",
        "kind": settings.public_record_kinds[1],
        "published_on": "2026-03-14",
        "url": "https://example.com/events/report/data-meetup/",
        "publisher": "データの置き場づくりを持ち寄る勉強会（架空の催し）",
        "role": settings.public_record_roles[0],
        "origin_section": KNOWN_SECTION,
    }
    draft.update(changes)
    return PublicRecordService(settings).register(PublicRecordDraft(**draft))


def _without_public_records(settings: Settings) -> Settings:
    """写しの設定から、公開記録の置き場と語彙の 3 行を抜いて読み直す。"""
    path: Path = settings.config_path
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not line.startswith(PUBLIC_RECORD_SETTING_LINES)]
    assert len(kept) == len(lines) - 3, "写しの設定から抜く 3 行が見つからない"
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return load_settings(path)


def _register_without_the_file(settings: Settings) -> tuple[Settings, object]:
    """置き場を書いていない設定で登記を呼び、その設定と返り値を返す。"""
    plain = _without_public_records(settings)
    result = PublicRecordService(plain).register(
        PublicRecordDraft(
            id="data-meetup-talk",
            name="配送データの集約を話した勉強会の発表",
            kind="登壇",
            published_on="2026-03-14",
            publisher="データの置き場づくりを持ち寄る勉強会（架空の催し）",
            role="登壇者",
        )
    )
    return plain, result


def _records(settings: Settings) -> list:
    """写しの正本を読み直して、公開記録の一覧を返す。"""
    return MarkdownRepository(settings).load().public_records


# ------------------------------------------------------------ 通る入力


def test_REQ_207_an_accepted_public_record_is_appended_as_one_block(settings: Settings) -> None:
    """通る入力は末尾に 1 ブロック積まれ、読み直すと渡した欄がそのまま読める。"""
    before = len(_records(settings))

    result = _register(settings)

    assert result.accepted is True, result.model_dump()
    records = _records(settings)
    assert len(records) == before + 1
    written = records[-1]
    assert written.id == "data-meetup-talk"
    assert written.name == "配送データの集約を話した勉強会の発表"
    assert written.url == "https://example.com/events/report/data-meetup/"
    assert written.origin_section == KNOWN_SECTION


def test_REQ_208_an_accepted_public_record_leaves_the_earlier_blocks_unchanged(
    settings: Settings,
) -> None:
    """通る入力は末尾に積むだけで、過去のブロックは書き換えない。"""
    before = len(_records(settings))

    _register(settings)

    records = _records(settings)
    assert [record.name for record in records[:before]] == [
        record.name for record in _records(settings)[:before]
    ]


def test_REQ_209_an_accepted_public_record_is_returned_in_the_result(settings: Settings) -> None:
    """通る登記は、登記した公開記録そのものを返り値に入れる。"""
    result = _register(settings)

    recorded = result.recorded["公開記録"]
    assert recorded["id"] == "data-meetup-talk", recorded
    assert recorded["name"] == "配送データの集約を話した勉強会の発表", recorded


def test_REQ_210_a_public_record_without_a_url_is_accepted(settings: Settings) -> None:
    """URL を渡さない入力は、そのまま受け付けられる。"""
    result = _register(
        settings, id="paper-progress-article", name="紙の雑誌に書いた進行管理の記事", url=None
    )

    assert result.accepted is True, result.model_dump()


def test_REQ_211_a_public_record_without_a_url_is_written_as_having_none(
    settings: Settings,
) -> None:
    """URL を渡さない入力は「- URL: なし」で書かれ、読み戻すと URL を持たない。"""
    _register(
        settings, id="paper-progress-article", name="紙の雑誌に書いた進行管理の記事", url=None
    )

    text = settings.path_for("public_records").read_text(encoding="utf-8")
    assert "- URL: なし" in text
    written = _records(settings)[-1]
    assert written.name == "紙の雑誌に書いた進行管理の記事"
    assert written.url is None


def test_REQ_212_a_url_given_as_an_empty_word_is_recorded_as_no_url(settings: Settings) -> None:
    """URL を空を表す語で渡した入力は通り、URL を持たないものとして積まれる。"""
    result = _register(
        settings, id="paper-progress-article", name="紙の雑誌に書いた進行管理の記事", url="なし"
    )

    assert result.accepted is True, result.model_dump()
    written = _records(settings)[-1]
    assert written.name == "紙の雑誌に書いた進行管理の記事"
    assert written.url is None


def test_REQ_213_a_public_record_without_an_origin_section_is_accepted(
    settings: Settings,
) -> None:
    """由来の節を渡さない入力は、由来の節を確かめずに受け付けられる。"""
    result = _register(
        settings,
        id="paper-progress-article",
        name="紙の雑誌に書いた進行管理の記事",
        origin_section=None,
    )

    assert result.accepted is True, result.model_dump()
    written = _records(settings)[-1]
    assert written.name == "紙の雑誌に書いた進行管理の記事"
    assert written.origin_section is None


# ------------------------------------------------------------ 置き場の断り


def test_REQ_214_a_settings_file_without_the_public_records_file_records_nothing(
    settings: Settings,
) -> None:
    """置き場を書いていない設定では受け付けず、正本のバイト列も変えない。"""
    plain = _without_public_records(settings)
    before = source_digest(plain.source_dir)

    result = PublicRecordService(plain).register(
        PublicRecordDraft(
            id="data-meetup-talk",
            name="配送データの集約を話した勉強会の発表",
            kind="登壇",
            published_on="2026-03-14",
            publisher="データの置き場づくりを持ち寄る勉強会（架空の催し）",
            role="登壇者",
        )
    )

    assert result.accepted is False
    assert result.rejection is not None
    assert source_digest(plain.source_dir) == before


def test_REQ_215_missing_public_records_file_rejection_names_the_constraint(
    settings: Settings,
) -> None:
    """置き場が無いときの断りは、当たった制約の名前を返す。"""
    _, result = _register_without_the_file(settings)

    assert result.rejection is not None
    assert result.rejection.constraint == "公開記録の置き場の設定"


def test_REQ_216_missing_public_records_file_rejection_names_the_settings_file(
    settings: Settings,
) -> None:
    """置き場が無いときの断りは、設定ファイルの名前と書き足す先が決まらないことを理由に書く。"""
    plain, result = _register_without_the_file(settings)

    assert result.rejection is not None
    reason = result.rejection.reason
    assert plain.config_path.name in reason, reason
    assert "書き足す先が決まらない" in reason, reason


def test_REQ_217_missing_public_records_file_rejection_names_the_next_operation(
    settings: Settings,
) -> None:
    """置き場が無いときの断りは、次に呼ぶ操作の名前を返す。"""
    _, result = _register_without_the_file(settings)

    assert result.rejection is not None
    assert result.rejection.next_action.operation == "register_public_record"


def test_REQ_218_missing_public_records_file_rejection_lists_the_three_keys(
    settings: Settings,
) -> None:
    """置き場が無いときの断りは、設定に足す 3 つの鍵の名前を書き方の例に入れる。"""
    _, result = _register_without_the_file(settings)

    assert result.rejection is not None
    listed = result.rejection.next_action.model_dump_json()
    for key in ("public_records", "public_record_kinds", "public_record_roles"):
        assert key in listed, listed
    # 置き場の鍵は、足す先の節の名前とともに書く。この 1 行が無いと、
    # 「public_records」はファイル名「public_records.md」の中にも現れるので、
    # 鍵を 1 つも書かない例でもこのテストが通ってしまう。
    assert "[source.files] に public_records = " in listed, listed


# ------------------------------------------------------------ 必須の欄の断り


def test_REQ_219_missing_required_fields_are_not_registered(settings: Settings) -> None:
    """必須の 6 つの欄それぞれを空にした入力を、どれも受け付けず、正本のバイト列も変えない。

    欄の顔ぶれは上の定数に文字どおり書いてあり、型の正本からは導かない。導くと、正本から欄を
    1 つ消したときにこのテストが回す場合も 1 つ減り、断らなくなったことに気づけない。
    """
    before = source_digest(settings.source_dir)

    for field in PUBLIC_RECORD_REQUIRED_FIELDS:
        result = _register(settings, **{field: ""})

        assert result.accepted is False, field
        assert result.rejection is not None, field
        assert source_digest(settings.source_dir) == before, field


def test_REQ_220_missing_required_fields_rejection_names_the_constraint(
    settings: Settings,
) -> None:
    """必須の欄を空にした入力の断りは、当たった制約の名前を返す。

    2 つを空にした 1 通りに加えて、6 つの欄を 1 つずつ空にした 6 通りでも同じ名前が返ることを見る。
    """
    result = _register(settings, name="", role="")

    assert result.rejection is not None
    assert result.rejection.constraint == PUBLIC_RECORD_REQUIRED_FIELDS_RULE

    for field, label in PUBLIC_RECORD_REQUIRED_FIELD_LABELS:
        single = _register(settings, **{field: ""})

        assert single.rejection is not None, label
        assert single.rejection.constraint == PUBLIC_RECORD_REQUIRED_FIELDS_RULE, (
            label,
            single.rejection.constraint,
        )


def test_REQ_221_missing_required_fields_rejection_names_them_in_the_reason(
    settings: Settings,
) -> None:
    """必須の欄を空にした入力の断りは、欠けた欄の名前を理由の文に書く。

    理由の定型文にも「名前」「役割」の語が出るので、欠けた欄として並べた側だけが持つ
    かぎかっこ付きの形で見る。定型文だけでは、欄の名前を 1 つも書かない実装も通ってしまう。
    """
    result = _register(settings, name="", role="")

    assert result.rejection is not None
    reason = result.rejection.reason
    assert "「名前」" in reason, reason
    assert "「役割」" in reason, reason

    # 6 つの欄を 1 つずつ空にすると、空にした欄の名前だけがかぎかっこ付きで理由に並ぶ。
    for field, label in PUBLIC_RECORD_REQUIRED_FIELD_LABELS:
        single = _register(settings, **{field: ""})

        assert single.rejection is not None, label
        single_reason = single.rejection.reason
        assert f"「{label}」" in single_reason, (label, single_reason)
        others = [
            other for _, other in PUBLIC_RECORD_REQUIRED_FIELD_LABELS if other != label
        ]
        assert [other for other in others if f"「{other}」" in single_reason] == [], (
            label,
            single_reason,
        )


def test_REQ_222_missing_required_fields_rejection_names_the_next_operation(
    settings: Settings,
) -> None:
    """必須の欄を空にした入力の断りは、次に呼ぶ操作の名前を返す。"""
    result = _register(settings, name="", role="")

    assert result.rejection is not None
    assert result.rejection.next_action.operation == "register_public_record"


def test_REQ_223_missing_required_fields_rejection_lists_the_missing_fields(
    settings: Settings,
) -> None:
    """必須の欄を空にした入力の断りは、欠けた欄の名前の一覧を返す。"""
    result = _register(settings, name="", role="")

    assert result.rejection is not None
    next_action = result.rejection.next_action
    assert next_action.missing_fields == ["名前", "役割"]

    # 6 つの欄を 1 つずつ空にすると、欠けた欄の一覧はその欄 1 つだけになる。
    for field, label in PUBLIC_RECORD_REQUIRED_FIELD_LABELS:
        single = _register(settings, **{field: ""})

        assert single.rejection is not None, label
        assert single.rejection.next_action.missing_fields == [label], (
            label,
            single.rejection.next_action.missing_fields,
        )


def test_REQ_224_missing_required_fields_rejection_carries_an_example(
    settings: Settings,
) -> None:
    """必須の欄を空にした入力の断りは、欠けた欄の書き方の例を返す。"""
    result = _register(settings, name="", role="")

    assert result.rejection is not None
    next_action = result.rejection.next_action
    assert "名前" in next_action.example
    assert "役割" in next_action.example


# ------------------------------------------------------------ 種類の語彙の断り


def test_REQ_225_a_kind_outside_the_vocabulary_is_not_registered(settings: Settings) -> None:
    """設定に無い種類の語は受け付けず、正本のバイト列も変えない。"""
    before = source_digest(settings.source_dir)

    result = _register(settings, kind=UNKNOWN_KIND)

    assert result.accepted is False
    assert result.rejection is not None
    assert source_digest(settings.source_dir) == before


def test_REQ_226_a_kind_outside_the_vocabulary_rejection_names_the_constraint(
    settings: Settings,
) -> None:
    """設定に無い種類の語の断りは、当たった制約の名前を返す。"""
    result = _register(settings, kind=UNKNOWN_KIND)

    assert result.rejection is not None
    assert result.rejection.constraint == PUBLIC_RECORD_KIND_VOCABULARY


def test_REQ_227_a_kind_outside_the_vocabulary_rejection_names_it_in_the_reason(
    settings: Settings,
) -> None:
    """設定に無い種類の語の断りは、渡された種類と設定ファイルの鍵の名前を理由に書く。"""
    result = _register(settings, kind=UNKNOWN_KIND)

    assert result.rejection is not None
    reason = result.rejection.reason
    assert UNKNOWN_KIND in reason, reason
    assert "public_record_kinds" in reason, reason


def test_REQ_228_a_kind_outside_the_vocabulary_rejection_names_the_next_operation(
    settings: Settings,
) -> None:
    """設定に無い種類の語の断りは、次に呼ぶ操作の名前を返す。"""
    result = _register(settings, kind=UNKNOWN_KIND)

    assert result.rejection is not None
    assert result.rejection.next_action.operation == "register_public_record"


def test_REQ_229_a_kind_outside_the_vocabulary_rejection_lists_the_kinds(
    settings: Settings,
) -> None:
    """設定に無い種類の語の断りは、設定が持つ種類の語をそのまま候補に返す。"""
    result = _register(settings, kind=UNKNOWN_KIND)

    assert result.rejection is not None
    assert result.rejection.next_action.candidates == settings.public_record_kinds


def test_REQ_230_a_kind_outside_the_vocabulary_rejection_carries_an_example(
    settings: Settings,
) -> None:
    """設定に無い種類の語の断りは、種類の書き方の例を返す。"""
    result = _register(settings, kind=UNKNOWN_KIND)

    assert result.rejection is not None
    example = result.rejection.next_action.example
    assert "種類" in example, example
    assert settings.public_record_kinds[0] in example, example


# ------------------------------------------------------------ 役割の語彙の断り


def test_REQ_231_a_role_outside_the_vocabulary_is_not_registered(settings: Settings) -> None:
    """設定に無い役割の語も受け付けず、正本のバイト列も変えない。"""
    before = source_digest(settings.source_dir)

    result = _register(settings, role=UNKNOWN_ROLE)

    assert result.accepted is False
    assert result.rejection is not None
    assert source_digest(settings.source_dir) == before


def test_REQ_232_a_role_outside_the_vocabulary_rejection_names_the_constraint(
    settings: Settings,
) -> None:
    """設定に無い役割の語の断りは、役割の語彙の制約の名前を返す（種類の語彙とは別の名前）。"""
    result = _register(settings, role=UNKNOWN_ROLE)

    assert result.rejection is not None
    assert result.rejection.constraint == PUBLIC_RECORD_ROLE_VOCABULARY


def test_REQ_233_a_role_outside_the_vocabulary_rejection_names_it_in_the_reason(
    settings: Settings,
) -> None:
    """設定に無い役割の語の断りは、渡された役割と設定ファイルの鍵の名前を理由に書く。"""
    result = _register(settings, role=UNKNOWN_ROLE)

    assert result.rejection is not None
    reason = result.rejection.reason
    assert UNKNOWN_ROLE in reason, reason
    assert "public_record_roles" in reason, reason


def test_REQ_234_a_role_outside_the_vocabulary_rejection_names_the_next_operation(
    settings: Settings,
) -> None:
    """設定に無い役割の語の断りは、次に呼ぶ操作の名前を返す。"""
    result = _register(settings, role=UNKNOWN_ROLE)

    assert result.rejection is not None
    assert result.rejection.next_action.operation == "register_public_record"


def test_REQ_235_a_role_outside_the_vocabulary_rejection_lists_the_roles(
    settings: Settings,
) -> None:
    """設定に無い役割の語の断りは、設定が持つ役割の語をそのまま候補に返す。"""
    result = _register(settings, role=UNKNOWN_ROLE)

    assert result.rejection is not None
    assert result.rejection.next_action.candidates == settings.public_record_roles


def test_REQ_236_a_role_outside_the_vocabulary_rejection_carries_an_example(
    settings: Settings,
) -> None:
    """設定に無い役割の語の断りは、役割の書き方の例を返す。"""
    result = _register(settings, role=UNKNOWN_ROLE)

    assert result.rejection is not None
    example = result.rejection.next_action.example
    assert "役割" in example, example
    assert settings.public_record_roles[0] in example, example


# ------------------------------------------------------------ 由来の節の断り


def test_REQ_237_an_origin_section_missing_from_the_source_is_not_registered(
    settings: Settings,
) -> None:
    """正本に無い ID を由来の節にした入力は受け付けず、正本のバイト列も変えない。"""
    before = source_digest(settings.source_dir)

    result = _register(settings, origin_section="nagisa-publishng")

    assert result.accepted is False
    assert result.rejection is not None
    assert source_digest(settings.source_dir) == before


def test_REQ_238_an_origin_section_missing_from_the_source_rejection_names_the_constraint(
    settings: Settings,
) -> None:
    """正本に無い ID を由来の節にした入力の断りは、当たった制約の名前を返す。"""
    result = _register(settings, origin_section="nagisa-publishng")

    assert result.rejection is not None
    assert result.rejection.constraint == "由来の節の実在"


def test_REQ_239_an_origin_section_missing_from_the_source_is_named_in_the_reason(
    settings: Settings,
) -> None:
    """正本に無い ID を由来の節にした入力の断りは、どちらにも無い ID であることを理由に書く。"""
    result = _register(settings, origin_section="nagisa-publishng")

    assert result.rejection is not None
    reason = result.rejection.reason
    assert "nagisa-publishng" in reason, reason
    assert "職歴の枠にも受託案件にも無い ID" in reason, reason


def test_REQ_240_an_origin_section_that_is_not_an_id_is_named_in_the_reason(
    settings: Settings,
) -> None:
    """見出しをそのまま由来の節に渡すと、ID の形と、節の ID に置き換えることを理由に書く。"""
    result = _register(settings, origin_section=KNOWN_SECTION_HEADING)

    assert result.rejection is not None
    reason = result.rejection.reason
    assert ID_FORMAT_TEXT in reason, reason
    assert "その節の ID に置き換える" in reason, reason


def test_REQ_241_an_origin_section_rejection_names_the_candidate_labels(
    settings: Settings,
) -> None:
    """由来の節の断りは、候補の表示名を理由の文に書く。"""
    result = _register(settings, origin_section="nagisa-publishng")

    assert result.rejection is not None
    assert KNOWN_SECTION_HEADING in result.rejection.reason, result.rejection.reason


def test_REQ_242_an_origin_section_rejection_names_the_next_operation(
    settings: Settings,
) -> None:
    """由来の節の断りは、次に呼ぶ操作の名前を返す。"""
    result = _register(settings, origin_section="nagisa-publishng")

    assert result.rejection is not None
    assert result.rejection.next_action.operation == "register_public_record"


def test_REQ_243_an_origin_section_rejection_lists_close_ids(settings: Settings) -> None:
    """由来の節の断りは、職歴の枠と受託案件にある近い ID を候補に返す。

    候補はそのまま渡せる ID だけで、表示名は拒否の文の側に出る。
    """
    headings = MarkdownRepository(settings).load().section_headings()

    result = _register(settings, origin_section="nagisa-publishng")

    assert result.rejection is not None
    candidates = result.rejection.next_action.candidates
    assert candidates
    assert all(candidate in headings for candidate in candidates)
    assert KNOWN_SECTION in candidates, candidates


def test_REQ_244_an_origin_section_rejection_carries_an_example(settings: Settings) -> None:
    """由来の節の断りは、由来の節の書き方の例を返す。"""
    result = _register(settings, origin_section="nagisa-publishng")

    assert result.rejection is not None
    example = result.rejection.next_action.example
    assert "由来の節" in example, example
    assert "register_public_record" in example, example


def test_REQ_246_only_the_first_broken_rule_is_returned_when_registering(
    settings: Settings,
) -> None:
    """制約が同時に外れていても、置き場・必須の欄・種類・役割・由来の節の順で先の 1 件だけが返る。

    ID の形と重なりの段は見ていない。その断りの中身を述べる要件がまだ無いためである。
    """
    # 由来の節だけが正本に無い ID なら、いちばん後に見る由来の節の断りが返る。
    origin_only = _register(settings, origin_section="nagisa-publishng")
    assert origin_only.rejection is not None
    assert origin_only.rejection.constraint == "由来の節の実在"

    # 同じ入力の種類も語の一覧の外にすると、由来の節より先に見る種類の断りが返る。
    kind_before_origin = _register(
        settings, kind=UNKNOWN_KIND, origin_section="nagisa-publishng"
    )
    assert kind_before_origin.rejection is not None
    assert kind_before_origin.rejection.constraint == PUBLIC_RECORD_KIND_VOCABULARY
    assert UNKNOWN_KIND in kind_before_origin.rejection.reason, kind_before_origin.rejection.reason

    # 種類と役割の両方が語の一覧の外にあると、先に見る種類の断りが返る。
    both_words = _register(settings, kind=UNKNOWN_KIND, role=UNKNOWN_ROLE)
    assert both_words.rejection is not None
    assert both_words.rejection.constraint == PUBLIC_RECORD_KIND_VOCABULARY
    assert UNKNOWN_KIND in both_words.rejection.reason, both_words.rejection.reason
    assert UNKNOWN_ROLE not in both_words.rejection.reason, both_words.rejection.reason

    # 必須の欄も欠くと、語彙より先に見る必須の欄の断りが返る。
    missing_field = _register(settings, name="", kind=UNKNOWN_KIND, role=UNKNOWN_ROLE)
    assert missing_field.rejection is not None
    assert missing_field.rejection.constraint == "公開記録の必須欄"

    # 置き場の無い設定では、必須の欄より先に見る置き場の断りが返る。
    plain = _without_public_records(settings)
    no_file = PublicRecordService(plain).register(
        PublicRecordDraft(
            id="data-meetup-talk",
            name="",
            kind=UNKNOWN_KIND,
            published_on="2026-03-14",
            publisher="データの置き場づくりを持ち寄る勉強会（架空の催し）",
            role=UNKNOWN_ROLE,
        )
    )
    assert no_file.rejection is not None
    assert no_file.rejection.constraint == "公開記録の置き場の設定"

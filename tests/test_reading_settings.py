"""起動の引数と、置き場と、accord の形（正本の書き方の 1 通り）のテスト。

accord は設定ファイルを読まない。経歴データの置き場（--data）と提示物の置き場（--presentations）を
起動の引数で受け、語彙を置き場の vocabulary.md から読み、正本は accord の形の 1 通りで読む。
置き場はどれも、同梱の見本の一時的な写し（経歴データの置き場は git の作業ツリーの根）の上で見る。
"""

from __future__ import annotations

import ast
import re
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from accord.__main__ import main
from accord.repository.markdown_repository import MarkdownRepository
from accord.services.consistency import ConsistencyService
from accord.vocabulary import settings as settings_module
from accord.vocabulary.settings import (
    ACCORD_FORM,
    FILE_KEYS,
    PACKAGE_FIELD_LABELS,
    load_settings,
)
from conftest import REPO_ROOT, add_vocabulary_terms, commit_all, git

FORBIDDEN_PHRASES = ["フルスタック", "幅広く対応可能", "〜に強みがあります"]
FORBIDDEN_HEADING = "### 本人が禁じた言い回し（見本。表の 1 列目を読む）"
FRAME_HEADING = "枠1｜2021-04〜現在 フリーランス"
FRAME_KIND = "在籍職歴の枠"
ENTRY_KIND = "案件"
# 案件のブロックだけが持つ 5 つの欄の、型の欄の名前。
ENTRY_ONLY_FIELDS = ("scale", "process", "role", "decisions", "closing")
# accord の形の 7 つのファイルの名前。
SEVEN_FILES = [
    "career_master.md",
    "keirekisho/daicho.md",
    "misekata_master.md",
    "product/features.md",
    "product/packages.md",
    "product/positioning.md",
    "public_records.md",
]
DATA_FORMAT = REPO_ROOT / "docs" / "data-format.md"
SETTINGS_SOURCE = REPO_ROOT / "src" / "accord" / "vocabulary" / "settings.py"


def _rewrite_ledger(settings, old: str, new: str) -> None:
    """写しの台帳の 1 か所を書き換える。狙った文字列が無ければ、テストの前提が崩れたとして落とす。"""
    path = settings.path_for("resume_ledger")
    text = path.read_text(encoding="utf-8")
    assert old in text, f"写しに「{old}」が無い: {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _plain_git_dir(tmp_path: Path, name: str = "plain") -> Path:
    """中身の無い git の作業ツリーの根を作って返す。"""
    directory = tmp_path / name
    directory.mkdir()
    git(directory, "init", "-q")
    return directory


# ---------------------------------------------------------------- 起動の引数と置き場


def test_REQ_502_the_data_argument_is_the_place_and_no_settings_file_is_read(sample_copy) -> None:
    """--data の置き場を経歴データとして読み、置き場に設定ファイルがあっても読まない。"""
    data = sample_copy / "data"
    (data / "accord.toml").write_text("これは設定ファイルとして読めない中身\n[[[", encoding="utf-8")
    commit_all(data)

    settings = load_settings(data, sample_copy / "presentations")

    assert settings.source_dir == data.resolve()
    assert settings.needs_migration is False
    assert settings.channels == ["tsukikusa", "nagiho"]
    assert main(["--data", str(data), "--list"]) == 0


def test_REQ_502_the_config_argument_is_not_accepted(sample_copy, capsys) -> None:
    """--config は起動の引数として受け付けない。"""
    with pytest.raises(SystemExit) as stopped:
        main(["--config", str(sample_copy / "data" / "accord.toml"), "--list"])
    assert stopped.value.code != 0
    assert "--config" in capsys.readouterr().err


def test_REQ_503_without_the_data_argument_the_server_does_not_open(capsys) -> None:
    """--list 以外の起動で --data が無ければ、置き場の指定の書き方を標準エラーに書いて 0 でない終了コードで終わる。"""
    assert main([]) != 0
    error = capsys.readouterr().err
    assert "--data" in error
    assert "git の作業ツリーの根" in error


@pytest.mark.parametrize("where", ["not_git", "inside_git"])
def test_REQ_503_a_data_place_that_is_not_a_git_root_is_refused(sample_copy, tmp_path, capsys, where) -> None:
    """--data が git の作業ツリーの根でなければ、サーバーを開かずに置き場の指定の書き方を書いて終わる。"""
    if where == "not_git":
        target = tmp_path / "not_git"
        shutil.copytree(sample_copy / "data", target)
        shutil.rmtree(target / ".git")
    else:
        target = sample_copy / "data" / "product"

    assert main(["--data", str(target)]) != 0
    error = capsys.readouterr().err
    assert "git の作業ツリーの根" in error
    assert "--data" in error


def test_REQ_503_list_runs_without_the_data_argument(capsys) -> None:
    """--list だけは --data なしで動く。"""
    assert main(["--list"]) == 0
    assert "read_section" in capsys.readouterr().out


def test_REQ_504_presentations_are_read_from_the_presentations_argument(sample_copy) -> None:
    """--presentations の置き場から、提示物と媒体ごとの規約を読む。"""
    settings = load_settings(sample_copy / "data", sample_copy / "presentations")
    repository = MarkdownRepository(settings)

    snapshot = repository.load()

    assert sorted(item.path for item in snapshot.presentations) == [
        "nagiho/skill_sheet.md",
        "tsukikusa/profile.md",
    ]
    assert repository.channel_rules("tsukikusa")


def test_REQ_504_without_the_presentations_argument_there_are_no_presentations(sample_copy) -> None:
    """--presentations が無ければ、提示物を 0 件として読み、媒体ごとの規約も空になる。"""
    settings = load_settings(sample_copy / "data")
    repository = MarkdownRepository(settings)

    assert repository.load().presentations == []
    assert repository.channel_rules("tsukikusa") == []
    assert main(["--data", str(sample_copy / "data"), "--list"]) == 0


def test_REQ_505_the_seven_files_have_fixed_names(settings) -> None:
    """置き場の中の 7 ファイルを決まった名前で読む。"""
    assert sorted(settings.source_file_names()) == sorted(SEVEN_FILES)
    for name in SEVEN_FILES:
        assert (settings.source_dir / name).is_file(), name
    assert MarkdownRepository(settings).load().public_records


def test_REQ_505_the_vocabulary_is_read_from_vocabulary_md(settings) -> None:
    """語彙を vocabulary.md から読む。語を足せば、読み直した語彙に入る。"""
    path = settings.vocabulary_path
    assert path.name == "vocabulary.md"
    assert settings.capability_categories[0] == "データの置き場をつくる"
    assert settings.positioning_targets == []

    text = path.read_text(encoding="utf-8").replace("## 決めの適用先\n", "## 決めの適用先\n\n- 見本の適用先\n", 1)
    path.write_text(text, encoding="utf-8")

    assert load_settings(settings.source_dir).positioning_targets == ["見本の適用先"]


# ---------------------------------------------------------------- accord の形


def test_REQ_506_the_form_is_fixed_and_no_reading_argument_is_accepted(settings, capsys) -> None:
    """読み方は accord の形の 1 通りで、読み方を変える引数を受け付けない。"""
    assert settings.reading == replace(ACCORD_FORM, presentation_directories=("tsukikusa", "nagiho"))
    assert list(load_settings.__code__.co_varnames[: load_settings.__code__.co_argcount]) == [
        "data",
        "presentations",
    ]
    with pytest.raises(SystemExit):
        main(["--data", str(settings.source_dir), "--reading", "x", "--list"])
    assert "--reading" in capsys.readouterr().err


def test_REQ_506_a_note_section_without_package_fields_is_skipped(settings) -> None:
    """パッケージ定義で、パッケージの型の欄を 1 つも持たない節は読み飛ばす。"""
    snapshot = MarkdownRepository(settings).load()

    assert [item.id for item in snapshot.packages] == ["requirements-and-progress", "data-platform-setup"]
    assert [defect.model_dump() for defect in snapshot.defects] == []


def test_REQ_506_a_package_that_lost_its_id_is_still_reported(settings) -> None:
    """ID を書き忘れても、ほかの型の欄を持つ節は読み飛ばさず、読めないブロックとして出る。"""
    path = settings.path_for("packages")
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("- ID: data-platform-setup\n", "", 1), encoding="utf-8")

    defects = MarkdownRepository(settings).load().defects

    assert [defect.missing_fields for defect in defects] == [["ID"]]


def test_REQ_506_the_package_field_labels_match_the_ontology() -> None:
    """パッケージとして読む節を見分ける欄のラベルは、型の正本のパッケージの欄と同じ。"""
    document = yaml.safe_load((REPO_ROOT / "src" / "accord" / "ontology.yaml").read_text(encoding="utf-8"))
    package = next(item for item in document["types"] if item["name"] == "Package")

    assert sorted(PACKAGE_FIELD_LABELS) == sorted(field["label"] for field in package["fields"])


def test_REQ_507_the_document_points_at_the_sample_which_reads_without_violations(settings) -> None:
    """accord の形の文書が見本を指し、その見本を整合の検査の違反 0 件・読めないブロック 0 件で読む。"""
    text = DATA_FORMAT.read_text(encoding="utf-8")
    assert "`samples/data/`" in text
    assert "`samples/presentations/`" in text

    report = ConsistencyService(settings).inspect(None)
    snapshot = MarkdownRepository(settings).load()

    assert [item.model_dump() for item in report.violations] == []
    assert [item.model_dump() for item in snapshot.defects] == []
    assert snapshot.positionings and snapshot.packages and snapshot.capabilities
    assert snapshot.career_frames and snapshot.engagements and snapshot.ledger_entries
    assert snapshot.public_records and snapshot.presentations


def _form_names_in_code() -> set[str]:
    """settings.py の「accord の形を決める名前」の区間にある文字列の定数（正本の役割の名前を除く）。"""
    source = SETTINGS_SOURCE.read_text(encoding="utf-8")
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines) if "accord の形を決める名前" in line and line.startswith("# ---"))
    end = next(i for i, line in enumerate(lines) if "accord の形を決める名前の終わり" in line)
    names: set[str] = set()
    for node in ast.parse(source).body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or not start < node.lineno - 1 < end:
            continue
        for inner in ast.walk(node.value):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                names.add(inner.value)
    return names - set(FILE_KEYS)


def _form_names_in_document() -> set[str]:
    """docs/data-format.md の「形を決める名前」の節に、バッククォートで書いた名前。"""
    text = DATA_FORMAT.read_text(encoding="utf-8")
    section = text.split("## 形を決める名前", 1)[1].split("\n## ", 1)[0]
    listed = section.split("これ以外の見出し・値は", 1)[0]
    body = "\n".join(line for line in listed.splitlines() if line.startswith("- "))
    return set(re.findall(r"`([^`]+)`", body))


def test_REQ_507_the_form_names_in_the_document_match_the_code() -> None:
    """コードが名前で使う語は、accord の形の文書の一覧と一致する（一覧に無い名前をコードが使えば落ちる）。"""
    in_code = _form_names_in_code()
    in_document = _form_names_in_document()

    assert in_code - in_document == set(), "一覧に無い名前をコードが使っている"
    assert in_document - in_code == set(), "コードが使っていない名前が一覧にある"
    assert "これ以外の見出し・値は利用者のデータの中身で" in DATA_FORMAT.read_text(encoding="utf-8")
    assert settings_module.LEGACY_CONFIG_FILE not in in_code


def test_REQ_545_a_presentations_place_that_does_not_exist_is_refused(sample_copy, capsys) -> None:
    """--presentations が実在するディレクトリでなければ、指定の書き方を書いて 0 でない終了コードで終わる。"""
    missing = sample_copy / "no_such_place"

    assert main(["--data", str(sample_copy / "data"), "--presentations", str(missing)]) != 0
    error = capsys.readouterr().err
    assert "--presentations" in error
    assert "実在するディレクトリ" in error


def test_REQ_546_a_place_without_vocabulary_or_settings_is_refused(tmp_path, capsys) -> None:
    """置き場に accord.toml も vocabulary.md も無ければ、vocabulary.md が要ることを書いて終わる。"""
    data = _plain_git_dir(tmp_path)

    assert main(["--data", str(data)]) != 0
    assert "vocabulary.md" in capsys.readouterr().err


def test_REQ_546_a_place_with_only_the_old_settings_file_still_starts(tmp_path) -> None:
    """accord.toml があり vocabulary.md が無い置き場は、移行を待つ置き場として読める（断らない）。"""
    data = _plain_git_dir(tmp_path)
    (data / "accord.toml").write_text("[source]\n", encoding="utf-8")

    settings = load_settings(data)

    assert settings.needs_migration is True
    assert settings.channels == []


# ---------------------------------------------------------------- 見せ方の正本と台帳（accord の形の中の決まり）


def test_REQ_069_unknown_channel_returns_no_rules(alt_settings) -> None:
    """媒体ごとの規約のファイルが無い媒体を渡すと、拒否ではなく空の一覧が返る。"""
    repository = MarkdownRepository(alt_settings)

    assert repository.channel_rules("shiokaze") == []


def _outside_rules(sample_copy: Path) -> Path:
    """提示物の置き場の外に、媒体ごとの規約と同じ名前のファイルを置いて、そのディレクトリを返す。"""
    outside = sample_copy / "outside"
    outside.mkdir()
    (outside / "channel.md").write_text("# 置き場の外\n\n- 置き場の外の規約\n", encoding="utf-8")
    return outside


def test_REQ_560_a_channel_with_a_parent_step_reads_no_rules_outside(sample_copy) -> None:
    """媒体の名前に .. が入り、規約のファイルのパスが提示物の置き場の外に解決されるなら、読まずに空を返す。"""
    outside = _outside_rules(sample_copy)
    settings = load_settings(sample_copy / "data", sample_copy / "presentations")
    repository = MarkdownRepository(settings)
    # 守りが無ければ読めてしまうファイルであることを先に確かめる。
    assert (settings.presentations_dir / "../outside/channel.md").resolve() == outside / "channel.md"

    assert repository.channel_rules("../outside") == []
    assert repository.channel_rules("tsukikusa")


def test_REQ_560_a_channel_directory_linked_outside_reads_no_rules(sample_copy) -> None:
    """提示物の置き場の媒体のディレクトリが置き場の外への symlink なら、その先の規約を読まずに空を返す。"""
    outside = _outside_rules(sample_copy)
    (sample_copy / "presentations" / "linked").symlink_to(outside, target_is_directory=True)
    settings = load_settings(sample_copy / "data", sample_copy / "presentations")
    repository = MarkdownRepository(settings)

    assert (settings.presentations_dir / "linked" / "channel.md").is_file()
    assert repository.channel_rules("linked") == []


def _outside_presentation(sample_copy: Path) -> Path:
    """提示物の置き場の外に、宣言を持つ提示物と媒体ごとの規約を置いて、そのディレクトリを返す。"""
    outside = _outside_rules(sample_copy)
    shutil.copy(sample_copy / "presentations" / "tsukikusa" / "profile.md", outside / "profile.md")
    return outside


def test_REQ_561_a_channel_with_a_parent_step_is_not_walked_for_presentations(sample_copy) -> None:
    """語彙に直接書いた媒体の名前が置き場の外に解決されるなら、そのディレクトリの Markdown を提示物にも規約にも読まない。"""
    outside = _outside_presentation(sample_copy)
    settings = add_vocabulary_terms(
        load_settings(sample_copy / "data", sample_copy / "presentations"), "媒体", ["../outside"]
    )
    assert "../outside" in settings.channels
    # 守りが無ければたどれてしまうディレクトリであることを先に確かめる。
    assert (settings.presentations_dir / "../outside").resolve() == outside
    repository = MarkdownRepository(settings)

    paths = sorted(item.path for item in repository.load().presentations)

    assert paths == ["nagiho/skill_sheet.md", "tsukikusa/profile.md"]
    assert repository.channel_rules("../outside") == []


def test_REQ_561_a_channel_directory_linked_outside_is_not_walked(sample_copy) -> None:
    """媒体のディレクトリが置き場の外への symlink なら、その先の Markdown を提示物として読まない。"""
    outside = _outside_presentation(sample_copy)
    (sample_copy / "presentations" / "linked").symlink_to(outside, target_is_directory=True)
    settings = add_vocabulary_terms(
        load_settings(sample_copy / "data", sample_copy / "presentations"), "媒体", ["linked"]
    )
    assert (settings.presentations_dir / "linked" / "profile.md").is_file()

    paths = sorted(item.path for item in MarkdownRepository(settings).load().presentations)

    assert paths == ["nagiho/skill_sheet.md", "tsukikusa/profile.md"]


def test_REQ_071_forbidden_phrases_heading_note_is_ignored_when_matching(settings) -> None:
    """見出しの末尾の括弧書きは、名前を照らし合わせるときに見ない。"""
    rules_file = settings.path_for("presentation_rules")
    text = rules_file.read_text(encoding="utf-8")
    assert FORBIDDEN_HEADING in text
    rules_file.write_text(
        text.replace(FORBIDDEN_HEADING, "### 本人が禁じた言い回し（2030-01-01 に 1 行足した）"),
        encoding="utf-8",
    )

    assert MarkdownRepository(settings).forbidden_phrases() == FORBIDDEN_PHRASES


def test_REQ_376_frame_blocks_do_not_need_the_entry_only_fields(alt_settings) -> None:
    """在籍職歴の枠のブロックは、案件だけの 5 欄を持たなくても型にでき、断りにならない。"""
    snapshot = MarkdownRepository(alt_settings).load()
    frames = [item for item in snapshot.ledger_entries if item.kind == FRAME_KIND]

    assert frames, "在籍職歴の枠が 1 件も読めていない"
    for name in ENTRY_ONLY_FIELDS:
        assert getattr(frames[0], name) is None, name
    assert [defect.model_dump() for defect in snapshot.defects] == []


def test_REQ_376_the_ontology_says_which_fields_only_entry_blocks_need() -> None:
    """型の正本が、案件だけの 5 欄を「案件のブロックでだけ必須」と定めている（資源を読めば分かる）。"""
    from accord.models.ontology import load_ontology

    ledger = load_ontology().type_named("ResumeLedger")
    assert ledger is not None
    fields = {item.name: item for item in ledger.fields}
    for name in ENTRY_ONLY_FIELDS:
        assert fields[name].required is False, name
        assert fields[name].required_for_kinds == [ENTRY_KIND], name
    for name in ("heading", "period", "source_section"):
        assert fields[name].required is True, name


def test_REQ_376_entry_blocks_still_need_the_entry_only_fields(alt_settings) -> None:
    """案件のブロックの必須欄は変わらない。案件だけの欄を消せば、今までどおり読めない。"""
    _rewrite_ledger(alt_settings, "| 規模 | 従業員 35 名 |\n", "")

    snapshot = MarkdownRepository(alt_settings).load()

    missing = [defect.missing_fields for defect in snapshot.defects]
    assert missing == [["規模"]], missing


@pytest.mark.parametrize(
    ("old", "new", "label"),
    [
        ("| 期間 | 2021-04〜現在 |\n", "", "期間"),
        ("- 出典の節: freelance-solo\n", "", "出典の節"),
    ],
)
def test_REQ_377_frame_block_without_a_required_field_is_named_in_a_note(
    alt_settings, old: str, new: str, label: str
) -> None:
    """在籍職歴の枠に期間か出典の節が無いと、読んでいないことを欠けた欄の名前つきで断る。"""
    from accord.services.consistency import ConsistencyService

    _rewrite_ledger(alt_settings, old, new)

    snapshot = MarkdownRepository(alt_settings).load()
    assert [(defect.heading, defect.missing_fields) for defect in snapshot.defects] == [
        (FRAME_HEADING, [label])
    ]
    notes = "\n".join(ConsistencyService(alt_settings).inspect().notes)
    assert FRAME_HEADING in notes, notes
    assert f"「{label}」" in notes, notes



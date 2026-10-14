"""移行の操作（migrate_data）のテスト。

移行の前の置き場は、前の版の設定ファイル accord.toml を持ち、語彙のファイル vocabulary.md を持たない。
テストは同梱の見本の一時的な写しから、語彙のファイルを消し、同じ語彙と accord の形の読み方を書いた
設定ファイルを置いて、移行の前の置き場を作る。本物のデータの置き場には触れない。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from accord.server.app import TOOL_NAMES, create_server
from accord.services.recording import (
    ALREADY_MIGRATED,
    FORM_DIFFERENCE,
    PRE_MIGRATION,
    MigrationService,
)
from accord.vocabulary.settings import (
    CAREER_SECTION_HEADING,
    FORM_FILES,
    LABEL_ALIASES,
    VOCABULARY_KINDS,
    load_settings,
    parse_vocabulary,
)
from conftest import commit_all, git, source_digest

# 見本のパッケージ定義で、型の欄を 1 つも持たない節（覚え書きの節）の見出し。
NOTE_HEADING = "見本の覚え書き"

# 移行の前の設定ファイルの、語彙の節の鍵。並びは語彙の種類の並び。
VOCABULARY_KEYS = (
    "channels",
    "positioning_targets",
    "capability_categories",
    "package_hypothesis_states",
    "public_record_kinds",
    "public_record_roles",
)

# 7 つの正本のファイル（移行の前と後で 1 バイトも変わらないことを見る）。
SEVEN_FILES = sorted(set(name for key, name in FORM_FILES.items() if key != "presentations"))


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(value)


def _form_config(vocabulary: dict[str, list[str]]) -> dict[str, dict]:
    """accord の形と同じ読み方を書いた、移行の前の設定ファイルの中身（節の名前から鍵と値への対応）。"""
    channels = vocabulary["媒体"]
    return {
        "source": {"directory": "."},
        "source.files": {key: name for key, name in FORM_FILES.items()},
        "vocabulary": {
            key: vocabulary[kind] for key, (kind, _) in zip(VOCABULARY_KEYS, VOCABULARY_KINDS)
        },
        "reading": {"strip_label_note": True},
        "reading.labels": {label: list(names) for label, names in LABEL_ALIASES.items()},
        "reading.packages": {"skip_headings": [NOTE_HEADING]},
        "reading.career": {"heading_levels": [3], "under_headings": [CAREER_SECTION_HEADING]},
        "reading.engagements": {
            "heading_levels": [4, 5],
            "under_headings": [CAREER_SECTION_HEADING],
            "skip_sections_without_fields": True,
        },
        "reading.resume_ledger": {
            "heading_prefix": "案件",
            "frame_heading_prefix": "枠",
            "fields_from_table": True,
            "bare_labels": ["畳み行"],
            "entry_number_from_heading": True,
        },
        "reading.presentations": {"directories": channels, "require_declaration": True},
        "reading.presentation_rules": {
            "channel_rules_from": "per_channel_file",
            "channel_rules_file": "{channel}/channel.md",
            "forbidden_phrases_heading": "本人が禁じた言い回し",
            "forbidden_phrases_any_level": True,
            "forbidden_phrases_from": "table",
        },
    }


def _toml_text(config: dict[str, dict]) -> str:
    lines: list[str] = []
    for table, values in config.items():
        lines.append(f"[{table}]")
        for key, value in values.items():
            name = key if key.isascii() and key.isidentifier() else json.dumps(key, ensure_ascii=False)
            lines.append(f"{name} = {_toml_value(value)}")
        lines.append("")
    return "\n".join(lines)


def _make_pre_migration(data, config: dict[str, dict] | None = None, text: str | None = None) -> dict:
    """写しの置き場を移行の前の置き場にしてコミットし、元の語彙を返す。"""
    vocabulary_path = data / "vocabulary.md"
    vocabulary = parse_vocabulary(vocabulary_path.read_text(encoding="utf-8"))
    config = config if config is not None else _form_config(vocabulary)
    vocabulary_path.unlink()
    (data / "accord.toml").write_text(text if text is not None else _toml_text(config), encoding="utf-8")
    commit_all(data, "移行の前の置き場")
    return vocabulary


@pytest.fixture
def legacy(sample_copy):
    """移行の前の置き場の、経歴データの置き場と、元の語彙と、設定。"""
    data = sample_copy / "data"
    vocabulary = _make_pre_migration(data)
    settings = load_settings(data, sample_copy / "presentations")
    assert settings.needs_migration is True
    return data, vocabulary, settings


def _commit_count(data) -> int:
    return int(git(data, "rev-list", "--count", "HEAD").strip())


def _call(server, name: str, arguments: dict) -> dict:
    """MCP の口からツールを呼び、返り値の型の中身を辞書で返す。"""
    result = asyncio.run(server.call_tool(name, arguments))
    structured = getattr(result, "structured_content", None)
    if structured is None and isinstance(result, tuple):
        structured = result[1]
    if structured is None:
        structured = getattr(result, "structuredContent", None)
    assert isinstance(structured, dict), result
    return structured.get("result", structured) if set(structured) == {"result"} else structured


# 移行のほかの 18 の操作を呼ぶ引数。どれも、移行の前でなければ通るか、別の理由で断られる形でよい。
OTHER_CALLS = {
    "get_positioning": {},
    "assemble_material": {"channel": "tsukikusa"},
    "record_positioning": {
        "decided_on": "2026-10-14",
        "scope": "全体",
        "headline_package": "requirements-and-progress",
        "rationale": "移行の前に断られることを見るための決め。",
    },
    "register_capability": {
        "id": "migration-check",
        "name": "名前",
        "description": "説明",
        "category": "データの置き場をつくる",
        "evidence_sections": ["freelance-solo"],
    },
    "register_public_record": {
        "id": "migration-record",
        "name": "名前",
        "kind": "記事",
        "published_on": "2026",
        "publisher": "発行元",
        "role": "著者",
    },
    "revise_package": {
        "id": "requirements-and-progress",
        "name": "要件定義と進行管理",
        "capabilities": [],
        "buyer": "買い手",
        "hypothesis_state": "検証中",
    },
    "check_consistency": {},
    "list_sections": {},
    "read_section": {"section": "freelance-solo"},
    "search_facts": {"query": "見本"},
    "record_fact": {
        "section": "freelance-solo",
        "fact": "移行の前に断られることを見る",
        "source": "本人の申告",
        "date": "2026-10-14",
    },
    "revise_section": {
        "section": "freelance-solo",
        "body": "本文",
        "fingerprint": "00000000",
        "reason": "移行の前に断られることを見るため",
    },
    "rename_heading": {
        "section": "freelance-solo",
        "heading": "新しい見出し",
        "fingerprint": "00000000",
        "reason": "移行の前に断られることを見るため",
    },
    "add_section": {
        "heading": "足す節",
        "body": "本文",
        "reason": "移行の前に断られることを見るため",
        "file": "career_master.md",
    },
    "remove_section": {
        "section": "freelance-solo",
        "fingerprint": "00000000",
        "reason": "移行の前に断られることを見るため",
    },
    "move_section": {
        "section": "freelance-solo",
        "fingerprint": "00000000",
        "reason": "移行の前に断られることを見るため",
    },
    "set_disclosure": {
        "section": "freelance-solo",
        "disclosure": "公開可",
        "fingerprint": "00000000",
        "reason": "移行の前に断られることを見るため",
    },
    "export_source": {"path": "/nonexistent-migration-check/all.md"},
}


# ---------------------------------------------------------------- 移行の前の断り


def test_REQ_522_every_other_operation_is_refused_before_migration(legacy) -> None:
    """移行の前の置き場では、移行のほかの 18 の操作がどれも断り、移行の操作の名前を返す。"""
    data, _, settings = legacy
    server = create_server(settings)
    assert set(OTHER_CALLS) == set(TOOL_NAMES) - {"migrate_data"}
    before = source_digest(data)
    commits = _commit_count(data)

    for name, arguments in OTHER_CALLS.items():
        result = _call(server, name, arguments)
        rejection = result.get("rejection")
        assert rejection is not None, (name, result)
        assert rejection["constraint"] == PRE_MIGRATION, (name, rejection)
        assert rejection["next_action"]["operation"] == "migrate_data", (name, rejection)

    assert source_digest(data) == before
    assert _commit_count(data) == commits


def test_REQ_522_the_refusal_comes_before_any_other_check(legacy) -> None:
    """移行の前の断りは、引数の誤りの断りより先に返る（欠けた欄だらけの決めでも、移行を指す）。"""
    _, _, settings = legacy
    server = create_server(settings)

    result = _call(server, "record_positioning", {"decided_on": "", "scope": "", "headline_package": "", "rationale": ""})

    assert result["rejection"]["constraint"] == PRE_MIGRATION


def test_REQ_522_other_operations_work_after_migration(legacy) -> None:
    """移行の操作が通った後は、同じサーバーのほかの操作が断らずに読める。"""
    _, vocabulary, settings = legacy
    server = create_server(settings)

    assert _call(server, "migrate_data", {})["accepted"] is True
    listed = _call(server, "list_sections", {})
    report = _call(server, "check_consistency", {})

    assert listed.get("rejection") is None
    assert listed["sections"]
    assert report.get("rejection") is None
    assert report["violations"] == []
    assert settings.channels == vocabulary["媒体"]


# ---------------------------------------------------------------- 移行の操作


def test_REQ_523_migration_makes_the_vocabulary_file_and_removes_the_settings_file_in_one_commit(legacy) -> None:
    """移行は vocabulary.md を作り、accord.toml を消し、その 2 つを操作の名前の行を持つ 1 件のコミットにする。"""
    data, vocabulary, settings = legacy
    seven = {name: digest for name, digest in source_digest(data).items() if name in SEVEN_FILES}
    commits = _commit_count(data)

    result = MigrationService(settings).migrate_data()

    assert result.accepted is True, result.rejection
    assert (data / "vocabulary.md").is_file()
    assert not (data / "accord.toml").exists()
    assert _commit_count(data) == commits + 1
    changed = sorted(git(data, "show", "--name-only", "--format=", "HEAD").split())
    assert changed == ["accord.toml", "vocabulary.md"]
    assert "Accord-Operation: migrate_data" in git(data, "log", "-1", "--format=%B")
    assert git(data, "status", "--porcelain").strip() == ""
    after = {name: digest for name, digest in source_digest(data).items() if name in SEVEN_FILES}
    assert after == seven
    assert parse_vocabulary((data / "vocabulary.md").read_text(encoding="utf-8")) == vocabulary


def test_REQ_523_the_result_names_the_files_and_counts_the_terms(legacy) -> None:
    """返り値は、作ったファイル・消したファイル・種類ごとの語の数を持ち、コミットしたことを知らせる。"""
    _, vocabulary, settings = legacy

    result = MigrationService(settings).migrate_data()

    assert result.recorded["作ったファイル"] == "vocabulary.md"
    assert result.recorded["消したファイル"] == "accord.toml"
    assert result.recorded["語の数"] == {kind: len(words) for kind, words in vocabulary.items()}
    assert any("git にコミットした" in line for line in result.warnings)


def test_REQ_523_the_vocabulary_file_is_written_in_the_form(legacy) -> None:
    """作る vocabulary.md は、語彙の見出しの下に 6 つの種類の節を持ち、語が 0 件の種類も節を置く。"""
    data, _, settings = legacy

    MigrationService(settings).migrate_data()
    text = (data / "vocabulary.md").read_text(encoding="utf-8")

    assert text.splitlines()[0] == "# 語彙"
    headings = [line[3:] for line in text.splitlines() if line.startswith("## ")]
    assert headings == [kind for kind, _ in VOCABULARY_KINDS]
    assert "## 決めの適用先\n\n## 機能の分類" in text


def test_REQ_523_the_migrated_place_reads_the_same_as_the_sample(legacy, alt_settings) -> None:
    """移行した置き場を読み直すと、語彙も読み方も、移行の前から語彙を持つ見本（別の写し）と同じになる。"""
    data, _, legacy_settings = legacy
    MigrationService(legacy_settings).migrate_data()

    reloaded = load_settings(data, legacy_settings.presentations_dir)

    assert reloaded.needs_migration is False
    assert reloaded.vocabulary() == alt_settings.vocabulary()
    assert reloaded.reading == alt_settings.reading


def test_REQ_405_migration_does_not_write_over_an_uncommitted_change_to_the_settings_file(legacy) -> None:
    """移行が消す accord.toml に accord を通さない未コミットの変更があれば、移行しない。"""
    data, _, settings = legacy
    config = data / "accord.toml"
    config.write_text(config.read_text(encoding="utf-8") + "\n# 書きかけ\n", encoding="utf-8")
    before = source_digest(data)
    commits = _commit_count(data)

    result = MigrationService(settings).migrate_data()

    assert result.accepted is False
    assert "accord.toml" in result.rejection.reason
    assert source_digest(data) == before
    assert _commit_count(data) == commits


# ---------------------------------------------------------------- accord の形との違い


def _change(config: dict[str, dict], table: str, key: str, value) -> dict[str, dict]:
    changed = {name: dict(values) for name, values in config.items()}
    changed.setdefault(table, {})[key] = value
    return changed


@pytest.mark.parametrize(
    ("table", "key", "value", "expected"),
    [
        ("source", "directory", "source", 'source.directory: .'),
        ("source.files", "capabilities", "product/capabilities.md", "source.files.capabilities: product/features.md"),
        ("reading", "strip_label_note", False, "reading.strip_label_note: true"),
        ("reading.career", "heading_levels", [2], "reading.career.heading_levels: [3]"),
        ("reading.presentation_rules", "forbidden_phrases_from", "bullets", 'reading.presentation_rules.forbidden_phrases_from: "table"'),
        ("reading.presentations", "directories", ["tsukikusa"], 'reading.presentations.directories: ["tsukikusa", "nagiho"]'),
        ("reading.career", "unknown_key", True, "reading.career.unknown_key: （accord の形に無い鍵）"),
        ("reading.packages", "skip_headings", ["要件定義と進行管理"], "reading.packages.skip_headings: パッケージの型の欄を 1 つも持たない節を読み飛ばす"),
    ],
)
def test_REQ_524_a_settings_file_that_differs_from_the_form_is_not_migrated(sample_copy, table, key, value, expected) -> None:
    """置き場の節か読み方の節が accord の形と違えば、移行せずに、違う鍵と accord の形の値を返す。"""
    data = sample_copy / "data"
    vocabulary = parse_vocabulary((data / "vocabulary.md").read_text(encoding="utf-8"))
    _make_pre_migration(data, _change(_form_config(vocabulary), table, key, value))
    settings = load_settings(data, sample_copy / "presentations")
    before = source_digest(data)
    commits = _commit_count(data)

    result = MigrationService(settings).migrate_data()

    assert result.accepted is False
    assert result.rejection.constraint == FORM_DIFFERENCE
    assert any(candidate.startswith(expected) for candidate in result.rejection.next_action.candidates), (
        result.rejection.next_action.candidates
    )
    assert source_digest(data) == before
    assert _commit_count(data) == commits
    assert settings.needs_migration is True


def test_REQ_524_connection_keys_are_not_compared(sample_copy) -> None:
    """置き場の節の接続の鍵（提示物の置き場・書き込みの記録・書き出し先）は accord の形に入らないので比べない。"""
    data = sample_copy / "data"
    vocabulary = parse_vocabulary((data / "vocabulary.md").read_text(encoding="utf-8"))
    config = _form_config(vocabulary)
    config["source"].update({"presentations_root": "../presentations", "commit_writes": False, "export_path": "../out.md"})
    _make_pre_migration(data, config)
    settings = load_settings(data, sample_copy / "presentations")

    result = MigrationService(settings).migrate_data()

    assert result.accepted is True, result.rejection


def test_REQ_524_an_unreadable_settings_file_is_refused_as_a_difference(sample_copy) -> None:
    """accord.toml が TOML として読めなければ、移行せずに accord の形との違いとして断る。"""
    data = sample_copy / "data"
    _make_pre_migration(data, text="これは TOML として読めない中身\n[[[")
    settings = load_settings(data, sample_copy / "presentations")

    result = MigrationService(settings).migrate_data()

    assert result.accepted is False
    assert result.rejection.constraint == FORM_DIFFERENCE
    assert (data / "accord.toml").is_file()
    assert not (data / "vocabulary.md").exists()


# ---------------------------------------------------------------- 移行済みの置き場


def test_REQ_544_migration_on_a_migrated_place_is_refused(settings) -> None:
    """移行済みの置き場（vocabulary.md がある）で移行を呼ぶと、書かずに移行済みであることを返す。"""
    data = settings.source_dir
    before = source_digest(data)
    commits = _commit_count(data)

    result = _call(create_server(settings), "migrate_data", {})

    assert result["accepted"] is False
    assert result["rejection"]["constraint"] == ALREADY_MIGRATED
    assert "移行済み" in result["rejection"]["reason"]
    assert result["rejection"]["next_action"]["operation"] == "list_sections"
    assert source_digest(data) == before
    assert _commit_count(data) == commits


def test_REQ_544_a_second_migration_is_refused(legacy) -> None:
    """移行が通った後に、もう一度移行を呼ぶと、書かずに移行済みであることを返す。"""
    data, _, settings = legacy
    server = create_server(settings)
    assert _call(server, "migrate_data", {})["accepted"] is True
    commits = _commit_count(data)

    second = _call(server, "migrate_data", {})

    assert second["accepted"] is False
    assert second["rejection"]["constraint"] == ALREADY_MIGRATED
    assert _commit_count(data) == commits

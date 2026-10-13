"""書き込みの記録（書いたら git にコミットする）のテスト。

設定の `[source] commit_writes` を true にした写しを、一時の場所で git のリポジトリにして確かめる。
見るのは、変えたファイルだけがコミットされること、無効なら git を呼ばないこと、人の手の
未コミットの変更があれば書かないこと、git の外なら起動をやめることの 4 つである。
同梱のサンプルの一時的な写しの上で走らせ、本物のデータの置き場には触れない。
"""

from __future__ import annotations

import subprocess
from datetime import date

import pytest

from accord.__main__ import main
from accord.models.results import PositioningDraft
from accord.services.positioning import PositioningService
from accord.services.sections import SectionService
from accord.vocabulary.settings import load_settings
from conftest import add_config_lines, git, init_git

FACT = ("freelance-solo", "引き渡しの手順書を 3 社とも同じ形にそろえた", "本人の申告", "2026-10-01")


def _commit_count(directory) -> int:
    return int(git(directory, "rev-list", "--count", "HEAD").strip())


def _committing(sample_copy):
    """写しを git のリポジトリにし、書き込みの記録を有効にした設定を返す。"""
    init_git(sample_copy)
    settings = add_config_lines(sample_copy / "accord.toml", "source", ["commit_writes = true"])
    git(sample_copy, "commit", "-q", "-am", "書き込みの記録を有効にする")
    return settings


def test_REQ_403_a_write_commits_only_the_changed_file(sample_copy) -> None:
    """書き込みの操作が正本のファイルを変えると、変えたファイルだけを git にコミットする。"""
    settings = _committing(sample_copy)
    packages = settings.path_for("packages")
    packages.write_text(packages.read_text(encoding="utf-8") + "\n人の手の追記\n", encoding="utf-8")
    git(sample_copy, "add", str(packages))
    before = _commit_count(sample_copy)

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is True, result.rejection
    assert _commit_count(sample_copy) == before + 1
    changed = git(sample_copy, "show", "--name-only", "--format=", "HEAD").split()
    assert changed == ["source/career.md"]
    # 人の手で索引に積んだ別のファイルの変更は、コミットに混ぜずに残っている。
    assert "source/packages.md" in git(sample_copy, "diff", "--cached", "--name-only")


def test_REQ_403_existing_write_operations_commit_too(sample_copy) -> None:
    """いまある書き込みの操作（決めの登記）も、書いたファイルだけをコミットする。"""
    settings = _committing(sample_copy)
    before = _commit_count(sample_copy)

    result = PositioningService(settings).record(
        PositioningDraft(
            decided_on=date(2026, 9, 16),
            scope="全体",
            headline_package="requirements-and-progress",
            rationale="コミットされることを見るための決め。",
        )
    )

    assert result.accepted is True, result.rejection
    assert _commit_count(sample_copy) == before + 1
    changed = git(sample_copy, "show", "--name-only", "--format=", "HEAD").split()
    assert changed == ["source/positioning.md"]


def test_REQ_404_without_the_setting_no_git_is_called(settings, monkeypatch) -> None:
    """書き込みの記録が有効でなければ、書き込みの操作で git を呼ばない。"""
    original = subprocess.run
    calls: list[list[str]] = []

    def watching(args, *rest, **kwargs):
        if args and args[0] == "git":
            calls.append(list(args))
        return original(args, *rest, **kwargs)

    monkeypatch.setattr(subprocess, "run", watching)

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is True, result.rejection
    assert calls == []


def test_REQ_405_an_uncommitted_change_by_hand_stops_the_write(sample_copy) -> None:
    """書く前のファイルに未コミットの変更があれば、書かずに、ファイルの名前とコミットを先にすることを返す。"""
    settings = _committing(sample_copy)
    career = settings.path_for("career")
    edited = career.read_text(encoding="utf-8") + "\n人の手の書きかけ\n"
    career.write_text(edited, encoding="utf-8")
    before = _commit_count(sample_copy)

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is False
    assert "career.md" in result.rejection.reason
    assert "コミット" in result.rejection.reason
    assert career.read_text(encoding="utf-8") == edited
    assert _commit_count(sample_copy) == before


def test_REQ_406_commit_writes_outside_git_stops_the_start(sample_copy, capsys) -> None:
    """書き込みの記録が有効で、正本の置き場が git の中に無いなら、鍵の名前を添えて起動をやめる。"""
    config = sample_copy / "accord.toml"
    text = config.read_text(encoding="utf-8").replace(
        "[source]\n", "[source]\ncommit_writes = true\n", 1
    )
    config.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="commit_writes"):
        load_settings(config)
    assert main(["--config", str(config), "--list"]) == 2
    assert "commit_writes" in capsys.readouterr().err

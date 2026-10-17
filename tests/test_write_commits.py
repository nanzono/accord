"""書き込みの記録（書いたら git にコミットする）と、accord を通さない変更の検出のテスト。

経歴データの置き場は起動のときに git の作業ツリーの根であることを確かめてあるので、書き込みの記録は
いつも働く。見るのは、書き込み 1 件が変えたファイルだけの 1 件のコミットになり、説明に操作の名前の行が
入ること、置き場に accord を通さない未コミットの変更か accord 以外のコミットがあれば書かないこと、
読みの操作の知らせにその件数と直す操作の名前が載ることである。
同梱の見本の一時的な写しの上で走らせ、本物のデータの置き場には触れない。
"""

from __future__ import annotations

from datetime import date

from accord.models.results import PositioningDraft
from accord.services.positioning import PositioningService
from accord.services.recording import (
    FOREIGN_COMMIT,
    UNCOMMITTED_CHANGE,
    HistoryService,
    WriteRecorder,
)
from accord.services.sections import SectionService
from conftest import git

FACT = ("freelance-solo", "引き渡しの手順書を 3 社とも同じ形にそろえた", "本人の申告", "2026-10-01")
REASON = "テストで取り消す"


def _commit_count(directory) -> int:
    return int(git(directory, "rev-list", "--count", "HEAD").strip())


def _direct_commit(settings, text: str = "\n直接の直し\n") -> str:
    """git を直接叩いて、操作の名前を示す行を持たないコミットを 1 件足し、短い識別子を返す。"""
    career = settings.path_for("career")
    career.write_text(career.read_text(encoding="utf-8") + text, encoding="utf-8")
    git(settings.source_dir, "commit", "-q", "-am", "直接の直し")
    return git(settings.source_dir, "rev-parse", "--short", "HEAD").strip()


# ---------------------------------------------------------------- 1 件 1 コミット


def test_REQ_513_a_write_commits_only_the_changed_file_with_the_operation_line(settings) -> None:
    """書き込みの操作は、変えたファイルだけを 1 件のコミットにし、説明に操作の名前を示す行を書く。"""
    data = settings.source_dir
    before = _commit_count(data)

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is True, result.rejection
    assert _commit_count(data) == before + 1
    changed = git(data, "show", "--name-only", "--format=", "HEAD").split()
    assert changed == ["career_master.md"]
    assert "Accord-Operation: record_fact" in git(data, "log", "-1", "--format=%B")


def test_REQ_513_existing_write_operations_commit_too(settings) -> None:
    """いまある書き込みの操作（決めの登記）も、書いたファイルだけを 1 件のコミットにする。"""
    data = settings.source_dir
    before = _commit_count(data)

    result = PositioningService(settings).record(
        PositioningDraft(
            decided_on=date(2026, 9, 16),
            scope="全体",
            headline_package="requirements-and-progress",
            rationale="コミットされることを見るための決め。",
        )
    )

    assert result.accepted is True, result.rejection
    assert _commit_count(data) == before + 1
    changed = git(data, "show", "--name-only", "--format=", "HEAD").split()
    assert changed == ["product/positioning.md"]
    assert "Accord-Operation: record_positioning" in git(data, "log", "-1", "--format=%B")


# ---------------------------------------------------------------- 未コミットの変更


def test_REQ_514_an_uncommitted_change_in_the_written_file_stops_the_write(settings) -> None:
    """書くファイルに accord を通さない未コミットの変更があれば、書かずに、ファイルの名前と捨てる操作を返す。"""
    data = settings.source_dir
    career = settings.path_for("career")
    edited = career.read_text(encoding="utf-8") + "\n書きかけ\n"
    career.write_text(edited, encoding="utf-8")
    before = _commit_count(data)

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is False
    assert result.rejection.constraint == UNCOMMITTED_CHANGE
    assert "accord を通さない変更" in result.rejection.reason
    assert "career_master.md" in result.rejection.reason
    assert result.rejection.next_action.operation == "discard_uncommitted"
    assert result.rejection.next_action.candidates == ["career_master.md"]
    assert career.read_text(encoding="utf-8") == edited
    assert _commit_count(data) == before


def test_REQ_514_an_uncommitted_change_in_another_file_stops_the_write(settings) -> None:
    """書かないファイルの変更（索引に積んだもの・追跡していないファイル）でも、書かずに断る。"""
    data = settings.source_dir
    packages = settings.path_for("packages")
    packages.write_text(packages.read_text(encoding="utf-8") + "\n索引に積んだ別の変更\n", encoding="utf-8")
    git(data, "add", str(packages))
    (data / "memo.md").write_text("追跡していないファイル\n", encoding="utf-8")
    before = _commit_count(data)

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is False
    assert result.rejection.constraint == UNCOMMITTED_CHANGE
    assert set(result.rejection.next_action.candidates) == {"product/packages.md", "memo.md"}
    assert _commit_count(data) == before


def test_REQ_514_an_ignored_file_does_not_stop_the_write(settings) -> None:
    """`.gitignore` で外したファイルは、未コミットの変更に数えない。"""
    data = settings.source_dir
    (data / ".gitignore").write_text("scratch.txt\n", encoding="utf-8")
    git(data, "add", ".gitignore")
    git(data, "commit", "-q", "--amend", "--no-edit")
    (data / "scratch.txt").write_text("外したファイル\n", encoding="utf-8")

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is True, result.rejection


# ---------------------------------------------------------------- accord 以外のコミット


def test_REQ_515_a_commit_without_the_operation_line_stops_the_write(settings) -> None:
    """移行のコミットより後に操作の名前を示す行の無いコミットがあれば、書かずに、短い識別子と取り消す操作を返す。"""
    data = settings.source_dir
    short = _direct_commit(settings)
    before = _commit_count(data)

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is False
    assert result.rejection.constraint == FOREIGN_COMMIT
    assert result.rejection.next_action.operation == "revert_commit"
    assert result.rejection.next_action.candidates == [short]
    assert short in result.rejection.reason
    assert _commit_count(data) == before


def test_REQ_515_commits_before_the_migration_commit_are_not_counted(settings) -> None:
    """移行のコミットより前の、印の無いコミットは数えない。"""
    data = settings.source_dir
    _direct_commit(settings)
    git(data, "commit", "-q", "--allow-empty", "-m", "accord: migrate_data（見本）\n\nAccord-Operation: migrate_data")

    assert WriteRecorder(settings).foreign_commits() == []
    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is True, result.rejection


def test_REQ_547_without_a_migration_commit_the_root_is_the_starting_point(settings) -> None:
    """移行のコミットが無ければ、根のコミットを起点にし、根のコミットは数えず、その後の印の無いコミットを数える。"""
    data = settings.source_dir
    root = git(data, "rev-list", "--max-parents=0", "HEAD").strip()
    assert "Accord-Operation" not in git(data, "log", "-1", "--format=%B", root)
    assert WriteRecorder(settings).foreign_commits() == []

    short = _direct_commit(settings)

    assert [entry.short for entry in WriteRecorder(settings).foreign_commits()] == [short]


def test_REQ_547_the_root_commit_is_not_revertible(settings) -> None:
    """移行のコミットが無い置き場で、根のコミットは取り消さない。"""
    data = settings.source_dir
    root = git(data, "rev-parse", "--short", "HEAD").strip()

    result = HistoryService(settings).revert_commit(root, REASON)

    assert result.accepted is False
    assert result.rejection.constraint == "取り消せるコミットの範囲"
    assert _commit_count(data) == 1


def test_REQ_550_a_commit_reverted_by_accord_is_no_longer_counted(settings) -> None:
    """accord の打ち消しのコミットが名指しした印の無いコミットは、accord 以外のコミットに数えない。"""
    data = settings.source_dir
    first = _direct_commit(settings, "\n1 つ目の直接の直し\n")
    second = _direct_commit(settings, "\n2 つ目の直接の直し\n")

    result = HistoryService(settings).revert_commit(second, REASON)

    assert result.accepted is True, result.rejection
    full = git(data, "rev-parse", second).strip()
    assert f"Accord-Reverts: {full}" in git(data, "log", "-1", "--format=%B")
    assert [entry.short for entry in WriteRecorder(settings).foreign_commits()] == [first]


def test_REQ_550_after_reverting_every_foreign_commit_the_write_goes_through(settings) -> None:
    """accord 以外のコミットをすべて取り消した後は、書き込みが通る。"""
    short = _direct_commit(settings)
    assert SectionService(settings).record_fact(*FACT).accepted is False

    assert HistoryService(settings).revert_commit(short, REASON).accepted is True
    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is True, result.rejection


# ---------------------------------------------------------------- 読みの知らせ


def test_REQ_516_reading_carries_the_count_of_uncommitted_changes(settings) -> None:
    """未コミットの変更があれば、読みの返り値の知らせに件数と捨てる操作の名前を載せる（違反が 0 件でも）。"""
    (settings.source_dir / "memo.md").write_text("追跡していないファイル\n", encoding="utf-8")

    notice = SectionService(settings).list_sections().consistency_notice

    assert notice is not None
    assert notice.violation_count == 0
    assert notice.uncommitted_change_count == 1
    assert notice.foreign_commit_count == 0
    assert any("discard_uncommitted" in line for line in notice.fixes)


def test_REQ_516_reading_carries_the_count_of_foreign_commits(settings) -> None:
    """accord 以外のコミットがあれば、読みの返り値の知らせに件数と取り消す操作の名前を載せる。"""
    short = _direct_commit(settings)

    notice = SectionService(settings).read_section("freelance-solo").consistency_notice

    assert notice is not None
    assert notice.foreign_commit_count == 1
    assert notice.uncommitted_change_count == 0
    assert any("revert_commit" in line and short in line for line in notice.fixes)


def test_REQ_516_a_clean_place_carries_no_counts(settings) -> None:
    """未コミットの変更も accord 以外のコミットも違反も無ければ、知らせを載せない。"""
    assert SectionService(settings).search_facts("置き場").consistency_notice is None

"""書き込みの記録（書いたら git にコミットする）のテスト。

経歴データの置き場は起動のときに git の作業ツリーの根であることを確かめてあるので、書き込みの記録は
いつも働く。見るのは、書き込み 1 件が変えたファイルだけの 1 件のコミットになり、説明に操作の名前の行が
入ること、accord を通さない未コミットの変更があれば書かないことである。
同梱の見本の一時的な写しの上で走らせ、本物のデータの置き場には触れない。
"""

from __future__ import annotations

from datetime import date

from accord.models.results import PositioningDraft
from accord.services.positioning import PositioningService
from accord.services.sections import SectionService
from conftest import git

FACT = ("freelance-solo", "引き渡しの手順書を 3 社とも同じ形にそろえた", "本人の申告", "2026-10-01")


def _commit_count(directory) -> int:
    return int(git(directory, "rev-list", "--count", "HEAD").strip())


def test_REQ_513_a_write_commits_only_the_changed_file_with_the_operation_line(settings) -> None:
    """書き込みの操作は、変えたファイルだけを 1 件のコミットにし、説明に操作の名前を示す行を書く。"""
    data = settings.source_dir
    packages = settings.path_for("packages")
    packages.write_text(packages.read_text(encoding="utf-8") + "\n索引に積んだ別の変更\n", encoding="utf-8")
    git(data, "add", str(packages))
    before = _commit_count(data)

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is True, result.rejection
    assert _commit_count(data) == before + 1
    changed = git(data, "show", "--name-only", "--format=", "HEAD").split()
    assert changed == ["career_master.md"]
    assert "Accord-Operation: record_fact" in git(data, "log", "-1", "--format=%B")
    # 索引に積んだ別のファイルの変更は、コミットに混ぜずに残っている。
    assert "product/packages.md" in git(data, "diff", "--cached", "--name-only")


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


def test_REQ_405_an_uncommitted_change_stops_the_write(settings) -> None:
    """書く前のファイルに accord を通さない未コミットの変更があれば、書かずに、ファイルの名前を返す。"""
    data = settings.source_dir
    career = settings.path_for("career")
    edited = career.read_text(encoding="utf-8") + "\n書きかけ\n"
    career.write_text(edited, encoding="utf-8")
    before = _commit_count(data)

    result = SectionService(settings).record_fact(*FACT)

    assert result.accepted is False
    assert "career_master.md" in result.rejection.reason
    assert "コミット" in result.rejection.reason
    assert career.read_text(encoding="utf-8") == edited
    assert _commit_count(data) == before

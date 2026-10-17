"""取り消しの 2 つの操作（コミットを取り消す・未コミットの変更を捨てる）のテスト。

コミットを取り消す操作は、移行のコミットより後のコミット 1 件を打ち消すコミットを作る。後のコミットと
ぶつかるときと、打ち消した後に新しい違反が出るときは、置き場をそのままに戻して断る。未コミットの変更を
捨てる操作は、捨てる前の差分を返してから、作業ツリーを最後のコミットの状態に戻す。
同梱の見本の一時的な写しの上で走らせ、本物のデータの置き場には触れない。
"""

from __future__ import annotations

from accord.models.results import CapabilityDraft, PublicRecordDraft
from accord.services.offering import OfferingService
from accord.services.public_records import PublicRecordService
from accord.services.recording import REVERT_CONFLICT, REVERT_RANGE, HistoryService
from accord.services.sections import SectionService
from conftest import git, source_digest

REASON = "テストで取り消す"
SECTION = "freelance-solo"


def _commit_count(directory) -> int:
    return int(git(directory, "rev-list", "--count", "HEAD").strip())


def _tree(directory) -> dict[str, str]:
    """置き場の作業ツリーの全ファイルの指紋（git の管理の置き場 .git の中は見ない）。"""
    return {name: digest for name, digest in source_digest(directory).items() if not name.startswith(".git/")}


def _head(directory) -> str:
    return git(directory, "rev-parse", "--short", "HEAD").strip()


def _fact(settings, text: str) -> str:
    """accord の事実の登記を 1 件通し、そのコミットの短い識別子を返す。"""
    result = SectionService(settings).record_fact(SECTION, text, "本人の申告", "2026-10-01")
    assert result.accepted is True, result.rejection
    return _head(settings.source_dir)


def _mark_migration(settings) -> str:
    """移行のコミット（操作の名前が migrate_data の行を持つコミット）を 1 件足し、短い識別子を返す。"""
    git(settings.source_dir, "commit", "-q", "--allow-empty", "-m", "accord: migrate_data（見本）\n\nAccord-Operation: migrate_data")
    return _head(settings.source_dir)


# ---------------------------------------------------------------- 打ち消す


def test_REQ_517_reverting_a_write_makes_one_commit_that_undoes_it(settings) -> None:
    """accord の書き込み 1 件を取り消すと、打ち消しのコミットが 1 件でき、中身が書く前に戻り、履歴に 2 件が残る。"""
    data = settings.source_dir
    before = _tree(data)
    commits = _commit_count(data)
    written = _fact(settings, "取り消すための事実")

    result = HistoryService(settings).revert_commit(written, REASON)

    assert result.accepted is True, result.rejection
    assert _tree(data) == before
    assert _commit_count(data) == commits + 2
    message = git(data, "log", "-1", "--format=%B")
    assert "Accord-Operation: revert_commit" in message
    assert f"Accord-Reverts: {git(data, 'rev-parse', written).strip()}" in message
    assert result.recorded["取り消したコミット"] == written
    assert result.recorded["打ち消しのコミット"] == _head(data)
    assert result.recorded["ファイル"] == ["career_master.md"]
    assert result.recorded["理由"] == REASON
    assert any("git にコミットした" in note for note in result.warnings)


def test_REQ_517_a_long_identifier_is_accepted(settings) -> None:
    """取り消すコミットは、長い識別子でも渡せる。"""
    written = _fact(settings, "長い識別子で取り消す事実")
    full = git(settings.source_dir, "rev-parse", written).strip()

    result = HistoryService(settings).revert_commit(full, REASON)

    assert result.accepted is True, result.rejection


def test_REQ_517_an_empty_reason_is_refused(settings) -> None:
    """理由が空なら、取り消さずに、欠けた欄の名前を返して断る。"""
    written = _fact(settings, "理由なしで取り消す事実")
    commits = _commit_count(settings.source_dir)

    result = HistoryService(settings).revert_commit(written, "")

    assert result.accepted is False
    assert result.rejection.next_action.missing_fields == ["理由"]
    assert _commit_count(settings.source_dir) == commits


def test_REQ_518_the_migration_commit_and_earlier_commits_are_not_reverted(settings) -> None:
    """移行のコミットそのものと、それより前のコミットは取り消さず、取り消せる範囲を返す。"""
    data = settings.source_dir
    earlier = _fact(settings, "移行の前の事実")
    migration = _mark_migration(settings)
    later = _fact(settings, "移行の後の事実")
    before = _tree(data)

    for target in (migration, earlier):
        result = HistoryService(settings).revert_commit(target, REASON)
        assert result.accepted is False, target
        assert result.rejection.constraint == REVERT_RANGE
        assert result.rejection.next_action.candidates == [later]
    assert _tree(data) == before


def test_REQ_519_a_conflicting_revert_leaves_the_place_as_it_was(settings) -> None:
    """打ち消しが後のコミットの変更とぶつかるなら、置き場をそのままにし、ぶつかるファイルと後のコミットを返す。"""
    data = settings.source_dir
    first = _fact(settings, "1 つ目の事実")
    second = _fact(settings, "2 つ目の事実")
    third = _fact(settings, "3 つ目の事実")
    before = _tree(data)
    commits = _commit_count(data)

    result = HistoryService(settings).revert_commit(first, REASON)

    assert result.accepted is False
    assert result.rejection.constraint == REVERT_CONFLICT
    assert "career_master.md" in result.rejection.reason
    assert result.rejection.next_action.operation == "revert_commit"
    assert result.rejection.next_action.candidates == [third, second]
    assert _tree(data) == before
    assert _commit_count(data) == commits
    assert git(data, "status", "--porcelain") == ""


def test_REQ_520_a_revert_that_makes_a_new_violation_is_refused(settings) -> None:
    """打ち消した後の正本に、取り消す前に無かった違反が出るなら、置き場をそのままにし、その違反を返す。"""
    data = settings.source_dir
    record = PublicRecordService(settings).register(
        PublicRecordDraft(
            id="sample-revert-talk",
            name="取り消しを見るための見本の発表",
            kind=settings.public_record_kinds[1],
            published_on="2026-03-14",
            url="https://example.com/events/sample-revert/",
            publisher="見本の勉強会（架空の催し）",
            role=settings.public_record_roles[0],
        )
    )
    assert record.accepted is True, record.rejection
    recorded = _head(data)
    capability = OfferingService(settings).register_capability(
        CapabilityDraft(
            id="sample-revert-capability",
            name="取り消しを見るための見本の機能",
            description="公開記録を裏づけに持つ見本の機能",
            category=settings.capability_categories[0],
            evidence_sections=["sample-revert-talk"],
        )
    )
    assert capability.accepted is True, capability.rejection
    before = _tree(data)
    commits = _commit_count(data)

    result = HistoryService(settings).revert_commit(recorded, REASON)

    assert result.accepted is False
    assert result.rejection.constraint == "裏づけ節名の実在"
    assert "sample-revert-talk" in result.rejection.reason
    assert _tree(data) == before
    assert _commit_count(data) == commits
    assert git(data, "status", "--porcelain") == ""


def test_REQ_543_an_unknown_identifier_is_refused_with_the_revertible_commits(settings) -> None:
    """履歴に無い識別子は、取り消さずに、取り消せるコミットの短い識別子を返す。"""
    written = _fact(settings, "候補に出る事実")

    for identifier in ("deadbeef", "", "HEAD", "--all"):
        result = HistoryService(settings).revert_commit(identifier, REASON)
        assert result.accepted is False, identifier
        assert result.rejection.constraint == REVERT_RANGE
        assert result.rejection.next_action.candidates == [written]


def test_REQ_543_a_merge_commit_is_refused(settings) -> None:
    """合流のコミットは取り消さない。"""
    data = settings.source_dir
    branch = git(data, "rev-parse", "--abbrev-ref", "HEAD").strip()
    git(data, "checkout", "-q", "-b", "side")
    (data / "side.md").write_text("脇の変更\n", encoding="utf-8")
    git(data, "add", "side.md")
    git(data, "commit", "-q", "-m", "accord: 脇\n\nAccord-Operation: add_section")
    git(data, "checkout", "-q", branch)
    written = _fact(settings, "合流の前の事実")
    git(data, "merge", "-q", "--no-ff", "side", "-m", "accord: 合流\n\nAccord-Operation: add_section")
    merge = _head(data)

    result = HistoryService(settings).revert_commit(merge, REASON)

    assert result.accepted is False
    assert result.rejection.constraint == REVERT_RANGE
    assert merge not in result.rejection.next_action.candidates
    assert written in result.rejection.next_action.candidates


def test_REQ_553_an_already_reverted_commit_is_refused(settings) -> None:
    """後の accord の打ち消しのコミットが既に打ち消しているコミットは、取り消さずに、取り消せるコミットを返す。"""
    data = settings.source_dir
    written = _fact(settings, "2 度取り消す事実")
    first = HistoryService(settings).revert_commit(written, REASON)
    assert first.accepted is True, first.rejection
    commits = _commit_count(data)

    result = HistoryService(settings).revert_commit(written, REASON)

    assert result.accepted is False
    assert result.rejection.constraint == REVERT_RANGE
    assert written not in result.rejection.next_action.candidates
    assert first.recorded["打ち消しのコミット"] in result.rejection.next_action.candidates
    assert _commit_count(data) == commits


# ---------------------------------------------------------------- 捨てる


def test_REQ_521_discarding_returns_the_diff_and_restores_the_last_commit(settings) -> None:
    """未コミットの変更を捨てると、捨てる前の差分を返し、作業ツリーを最後のコミットの状態に戻す。"""
    data = settings.source_dir
    before = _tree(data)
    career = settings.path_for("career")
    career.write_text(career.read_text(encoding="utf-8") + "\n捨てる書きかけ\n", encoding="utf-8")
    (data / "memo.md").write_text("追跡していない覚え書き\n", encoding="utf-8")
    commits = _commit_count(data)

    result = HistoryService(settings).discard_uncommitted(REASON)

    assert result.accepted is True, result.rejection
    assert "+捨てる書きかけ" in result.recorded["差分"]
    assert "memo.md" in result.recorded["差分"]
    assert "追跡していない覚え書き" in result.recorded["差分"]
    assert set(result.recorded["ファイル"]) == {"career_master.md", "memo.md"}
    assert result.recorded["理由"] == REASON
    assert _tree(data) == before
    assert git(data, "status", "--porcelain") == ""
    assert _commit_count(data) == commits


def test_REQ_521_after_discarding_the_write_goes_through(settings) -> None:
    """捨てた後は、未コミットの変更で断られていた書き込みが通る。"""
    career = settings.path_for("career")
    career.write_text(career.read_text(encoding="utf-8") + "\n書きかけ\n", encoding="utf-8")
    service = SectionService(settings)
    assert service.record_fact(SECTION, "捨てた後の事実", "本人の申告", "2026-10-01").accepted is False

    assert HistoryService(settings).discard_uncommitted(REASON).accepted is True
    result = service.record_fact(SECTION, "捨てた後の事実", "本人の申告", "2026-10-01")

    assert result.accepted is True, result.rejection


def test_REQ_521_an_empty_reason_is_refused(settings) -> None:
    """理由が空なら、捨てずに、欠けた欄の名前を返して断る。"""
    data = settings.source_dir
    (data / "memo.md").write_text("残る覚え書き\n", encoding="utf-8")

    result = HistoryService(settings).discard_uncommitted("")

    assert result.accepted is False
    assert result.rejection.next_action.missing_fields == ["理由"]
    assert (data / "memo.md").is_file()


def test_REQ_548_nothing_to_discard_passes_with_an_empty_diff(settings) -> None:
    """捨てる変更が無ければ、何もせずに通し、空の差分と、捨てる変更が無かったことを返す。"""
    data = settings.source_dir
    before = _tree(data)

    result = HistoryService(settings).discard_uncommitted(REASON)

    assert result.accepted is True
    assert result.recorded["差分"] == ""
    assert result.recorded["ファイル"] == []
    assert any("捨てる変更は無かった" in note for note in result.warnings)
    assert _tree(data) == before

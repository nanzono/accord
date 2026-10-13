"""起動時と読みの前の整合の検査と、返り値に正本の置き場の絶対パスを出さないことのテスト。

起動時の検査は、標準入出力のサーバーを子のプロセスで起動して標準エラーを見る（入力を閉じると
サーバーは終わる）。読みの前の知らせは、読みの操作の返り値の欄で見る。13 の操作をすべて
一時の写しの上で呼び、返り値を JSON にした文字列に写しの絶対パスが現れないことも見る。
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys

from accord.models.results import MaterialRequest
from accord.server.app import create_server
from accord.services.consistency import ConsistencyService
from accord.services.material import MaterialService
from accord.services.positioning import PositioningService
from accord.services.sections import SectionService
from accord.services.watch import SourceWatch
from conftest import add_config_lines

# 職歴の枠の ID の行を消すと、その ID を指す裏づけと出典が読めなくなり、違反が出る。
BROKEN_ID_LINE = "- ID: freelance-solo\n"


def _break_the_source(settings) -> None:
    """経歴の正本の ID の行を人の手で消す（違反が出る形に壊す）。"""
    career = settings.path_for("career")
    text = career.read_text(encoding="utf-8")
    assert BROKEN_ID_LINE in text
    career.write_text(text.replace(BROKEN_ID_LINE, "", 1), encoding="utf-8")


def _start_server(settings) -> subprocess.CompletedProcess[str]:
    """標準入出力のサーバーを起動し、入力を閉じて終わらせる。"""
    return subprocess.run(
        [sys.executable, "-m", "accord", "--config", str(settings.config_path)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_REQ_456_the_start_writes_the_counts_to_standard_error(settings) -> None:
    """起動すると、正本全体の整合の検査の違反と断りの件数を標準エラーに書く。"""
    report = ConsistencyService(settings).inspect()

    completed = _start_server(settings)

    expected = f"違反 {len(report.violations)} 件・断り {len(report.notes)} 件"
    assert expected in completed.stderr, completed.stderr
    assert completed.stdout == ""


def test_REQ_457_the_start_goes_on_with_violations(settings) -> None:
    """起動時の整合の検査で違反が見つかっても、起動を続ける。"""
    _break_the_source(settings)
    violations = len(ConsistencyService(settings).inspect().violations)
    assert violations > 0

    completed = _start_server(settings)

    assert completed.returncode == 0, completed.stderr
    assert f"違反 {violations} 件" in completed.stderr


def test_REQ_458_reading_a_broken_source_carries_the_notice(settings) -> None:
    """読みの時点の正本に違反があれば、違反の件数と直し先を返り値の知らせに載せる。"""
    _break_the_source(settings)
    violations = ConsistencyService(settings).inspect().violations
    watch = SourceWatch(settings)

    views = [
        PositioningService(settings, watch=watch).current(),
        MaterialService(settings, watch=watch).assemble(MaterialRequest(channel="tsukikusa")),
        SectionService(settings, watch=watch).list_sections(),
        SectionService(settings, watch=watch).read_section("freelance-solo"),
        SectionService(settings, watch=watch).search_facts("置き場"),
        SectionService(settings, watch=watch).export_source(),
    ]

    for view in views:
        assert view.consistency_notice is not None, type(view).__name__
        assert view.consistency_notice.violation_count == len(violations)
        assert view.consistency_notice.fixes[0] == violations[0].as_note()


def test_REQ_458_a_clean_source_carries_no_notice(settings) -> None:
    """違反の無い正本では、知らせを載せない。"""
    view = SectionService(settings).list_sections()

    assert view.consistency_notice is None


def test_REQ_458_a_source_broken_before_the_start_is_noticed_on_the_first_read(
    settings,
) -> None:
    """サーバーを作る前に壊した正本も、作った後の最初の読みで知らせる。"""
    _break_the_source(settings)
    server = create_server(settings)

    result = asyncio.run(server.call_tool("list_sections", {}))

    assert "consistency_notice" in str(result)
    assert "violation_count" in str(result)


def test_REQ_459_an_unchanged_source_is_not_checked_again(settings, monkeypatch) -> None:
    """前回の検査の後に正本が変わっていなければ、検査を走らせ直さずに前回の結果を使う。"""
    calls: list[str | None] = []
    original = ConsistencyService.inspect

    def counting(self, scope=None, allow_targets=False):
        calls.append(scope)
        return original(self, scope, allow_targets)

    monkeypatch.setattr(ConsistencyService, "inspect", counting)
    service = SectionService(settings)

    service.list_sections()
    service.search_facts("置き場")
    assert calls == [None]

    _break_the_source(settings)
    service.list_sections()
    assert calls == [None, None]


def _call_every_tool(settings) -> list[str]:
    """13 の操作を、書き出し先を設定した写しの上ですべて呼び、返り値の文字列を集める。"""
    server = create_server(settings)
    calls = {
        "get_positioning": {},
        "assemble_material": {"channel": "tsukikusa"},
        "record_positioning": {
            "decided_on": "2026-09-16",
            "scope": "どこか",
            "headline_package": "requirements-and-progress",
            "rationale": "置き場が返り値に出ないことを見るため。",
        },
        "register_capability": {
            "id": "x",
            "name": "名前",
            "description": "説明",
            "category": "無い分類",
            "evidence_sections": ["missing-section"],
        },
        "register_public_record": {
            "id": "y",
            "name": "名前",
            "kind": "無い種類",
            "published_on": "2026",
            "publisher": "発行元",
            "role": "無い役割",
        },
        "revise_package": {
            "id": "requirements-and-progress",
            "name": "要件定義と進行管理",
            "capabilities": ["missing-capability"],
            "buyer": "買い手",
            "hypothesis_state": "検証中",
        },
        "check_consistency": {},
        "list_sections": {"file": "missing.md"},
        "read_section": {"section": "missing"},
        "search_facts": {"query": "置き場"},
        "record_fact": {
            "section": "freelance-solo",
            "fact": "置き場が返り値に出ないことを見るための事実",
            "source": "テスト",
            "date": "2026-10-01",
        },
        "revise_section": {
            "section": "freelance-solo",
            "body": "中身",
            "fingerprint": "00000000",
            "reason": "置き場が返り値に出ないことを見るため",
        },
        "export_source": {},
    }
    assert set(calls) == {tool.name for tool in asyncio.run(server.list_tools())}
    return [str(asyncio.run(server.call_tool(name, arguments))) for name, arguments in calls.items()]


def test_REQ_461_no_operation_returns_the_absolute_source_location(settings, tmp_path) -> None:
    """どの操作の返り値にも、正本の置き場の絶対パスを入れない。"""
    settings = add_config_lines(
        settings.config_path, "source", ['export_path = "../export/all.md"']
    )
    _break_the_source(settings)

    outputs = _call_every_tool(settings)

    forbidden = [
        str(settings.source_dir),
        str(settings.config_path.parent),
        json.dumps(str(settings.source_dir))[1:-1],
    ]
    for output in outputs:
        for text in forbidden:
            assert text not in output, output[:400]

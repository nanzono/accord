"""読みの前に正本全体の整合を検査し、違反があれば知らせにする。

accord を通さない変更で正本が壊れたとき（accord を使い始める前からの食い違いを含む）、次に読んだセッションがそれを知らずに文面を書かないように、
読みの操作はどれも、返り値の欄「整合の知らせ」に違反の件数と直し先を載せる。違反が残っている間は、
読むたびに載せる。起動の前に壊れていた正本も、最初の読みで知らせる。

検査は、前回の検査の後に正本のファイルの中身が変わったときだけ走らせ直す。変わったかは、
正本のファイルの中身の指紋で見る（更新時刻では見ない）。この判定と知らせの組み立ては、この文書の
1 か所に置き、読みの操作を持つサービスはどれもここを呼ぶ。
"""

from __future__ import annotations

from accord.models.results import ConsistencyNotice, ConsistencyReport
from accord.repository.markdown_repository import MarkdownRepository
from accord.vocabulary.settings import Settings

# 知らせに直し先を名前で並べる数。残りは件数に畳む。
FIX_SAMPLE_COUNT = 10

# 知らせの末尾に添える、全件を見るための次の一手。
INSPECT_OPERATION = "check_consistency"


class SourceWatch:
    """正本全体の整合の検査の結果を、正本の中身の指紋ごとに 1 つだけ持つ。"""

    def __init__(self, settings: Settings, repository: MarkdownRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or MarkdownRepository(settings)
        self._digest: str | None = None
        self._report: ConsistencyReport | None = None

    def report(self) -> ConsistencyReport:
        """正本全体の整合の検査の結果を返す。正本が前回から変わっていなければ、前回の結果を使う。"""
        digest = self.repository.source_digest()
        # spec: REQ-459
        if self._report is not None and digest == self._digest:
            return self._report
        # 整合の検査は決めと材料のサービスを読み込むので、輪にならないよう関数の中で読み込む。
        from accord.services.consistency import ConsistencyService

        self._report = ConsistencyService(self.settings, self.repository).inspect(None)
        self._digest = digest
        return self._report

    def notice(self) -> ConsistencyNotice | None:
        """正本全体に違反があれば、件数と直し先の知らせを返す。無ければ None。"""
        violations = self.report().violations
        if not violations:
            return None
        # spec: REQ-458
        fixes = [violation.as_note() for violation in violations[:FIX_SAMPLE_COUNT]]
        rest = len(violations) - FIX_SAMPLE_COUNT
        if rest > 0:
            fixes.append(f"ほかに {rest} 件ある。全件は {INSPECT_OPERATION} で見る。")
        return ConsistencyNotice(violation_count=len(violations), fixes=fixes)

    def counts(self) -> tuple[int, int]:
        """正本全体の整合の検査の、違反の件数と断りの件数を返す。"""
        report = self.report()
        return len(report.violations), len(report.notes)

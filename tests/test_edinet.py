from datetime import date

import pytest

from it_recruit_data.edinet import Filing, iter_dates


def test_iter_dates_includes_both_ends() -> None:
    assert list(iter_dates(date(2026, 7, 29), date(2026, 7, 31))) == [
        date(2026, 7, 29),
        date(2026, 7, 30),
        date(2026, 7, 31),
    ]


def test_iter_dates_rejects_reverse_range() -> None:
    with pytest.raises(ValueError):
        list(iter_dates(date(2026, 8, 1), date(2026, 7, 31)))


def test_filing_from_api_normalizes_nulls() -> None:
    filing = Filing.from_api(
        {
            "docID": "S100TEST",
            "edinetCode": "E07801",
            "filerName": "株式会社リクルートホールディングス",
            "docTypeCode": "120",
            "periodStart": "2025-04-01",
            "periodEnd": "2026-03-31",
            "submitDateTime": "2026-06-20 10:00",
            "docDescription": "有価証券報告書",
            "parentDocID": None,
        }
    )

    assert filing.doc_id == "S100TEST"
    assert filing.parent_doc_id == ""


from __future__ import annotations

from datetime import date

import pytest
import requests

import it_recruit_data.sec as sec
from it_recruit_data.sec import (
    SecClient,
    SecError,
    SecFiling,
    cache_filing_package,
    normalize_cik,
    select_filings,
    validate_user_agent,
)


def submissions_payload(
    accessions: list[str],
    forms: list[str],
    filing_dates: list[str],
) -> dict:
    return {
        "cik": 1018724,
        "name": "Amazon.com, Inc.",
        "filings": {
            "recent": {
                "accessionNumber": accessions,
                "form": forms,
                "filingDate": filing_dates,
                "reportDate": ["2023-12-31"] * len(accessions),
                "acceptanceDateTime": ["2024-02-01T12:00:00.000Z"]
                * len(accessions),
                "primaryDocument": ["amzn-20231231.htm"] * len(accessions),
            }
        },
    }


def test_normalize_cik() -> None:
    assert normalize_cik("1018724") == "0001018724"
    assert normalize_cik(1018724) == "0001018724"
    assert normalize_cik("0001018724") == "0001018724"
    for invalid in ("", "CIK1018724", "-1", "12345678901", "0000000000"):
        with pytest.raises(ValueError):
            normalize_cik(invalid)


def test_validate_user_agent_requires_real_monitored_contact() -> None:
    assert (
        validate_user_agent("IT Recruit data team sec-ops@it-recruit.jp")
        == "IT Recruit data team sec-ops@it-recruit.jp"
    )
    for invalid in (
        "",
        "IT Recruit data team",
        "Example example@example.com",
        "noreply@noreply.example.jp",
        "ops@it-recruit.jp",
    ):
        with pytest.raises(ValueError):
            validate_user_agent(invalid)


def test_select_filings_uses_history_exact_form_and_filing_date() -> None:
    recent = submissions_payload(
        ["0001018724-24-000006", "0001018724-24-000007"],
        ["10-K", "10-K/A"],
        ["2024-02-02", "2024-02-09"],
    )
    history = {
        "accessionNumber": ["0001018724-23-000004", "0001018724-23-000005"],
        "form": ["10-K", "8-K"],
        "filingDate": ["2023-02-03", "2023-02-03"],
        "reportDate": ["2022-12-31", "2022-12-31"],
        "acceptanceDateTime": ["2023-02-03T12:00:00Z"] * 2,
        "primaryDocument": ["amzn-20221231.htm", "amzn-8k.htm"],
    }

    filings = select_filings(
        [recent, history],
        cik="0001018724",
        filer_name="Amazon.com, Inc.",
        start=date(2023, 1, 1),
        end=date(2024, 12, 31),
        form="10-K",
    )

    assert [filing.accession_number for filing in filings] == [
        "0001018724-23-000004",
        "0001018724-24-000006",
    ]
    assert filings[-1].report_date == "2023-12-31"
    assert filings[-1].primary_document == "amzn-20231231.htm"
    assert filings[-1].filer_name == "Amazon.com, Inc."
    assert filings[-1].cik == "0001018724"

    with_amendments = select_filings(
        [recent],
        cik="0001018724",
        filer_name="Amazon.com, Inc.",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        form="10-K",
        include_amendments=True,
    )
    assert [filing.form for filing in with_amendments] == ["10-K", "10-K/A"]


def test_select_filings_rejects_mismatched_response_cik() -> None:
    payload = submissions_payload(
        ["0001018724-24-000006"], ["10-K"], ["2024-02-02"]
    )
    payload["cik"] = 1652044
    with pytest.raises(SecError, match="CIK does not match"):
        select_filings(
            [payload],
            cik="0001018724",
            filer_name="Amazon.com, Inc.",
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            form="10-K",
        )


class FakeResponse:
    def __init__(self, status_code: int, retry_after: str | None = None) -> None:
        self.status_code = status_code
        self.headers = {"Retry-After": retry_after} if retry_after else {}
        self.content = b"ok"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.headers: dict[str, str] = {}
        self.urls: list[str] = []

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        self.urls.append(url)
        return next(self.responses)


def test_sec_client_retries_429_and_503_respecting_retry_after(monkeypatch) -> None:
    session = FakeSession(
        [FakeResponse(429, "3"), FakeResponse(503, "1"), FakeResponse(200)]
    )
    sleeps: list[float] = []
    monkeypatch.setattr(sec.time, "sleep", sleeps.append)
    monkeypatch.setattr(sec, "_LAST_REQUEST_AT", 0.0)
    client = SecClient(
        "IT Recruit sec-ops@it-recruit.jp",
        request_interval=0,
        max_attempts=3,
        session=session,
    )

    assert client.get_bytes("https://data.sec.gov/test") == b"ok"
    assert sleeps == [3.0, 2.0]
    assert session.headers["Accept-Encoding"] == "gzip, deflate"
    assert session.headers["User-Agent"] == "IT Recruit sec-ops@it-recruit.jp"


def test_sec_client_stops_after_retry_limit(monkeypatch) -> None:
    session = FakeSession([FakeResponse(503), FakeResponse(503)])
    monkeypatch.setattr(sec.time, "sleep", lambda _: None)
    monkeypatch.setattr(sec, "_LAST_REQUEST_AT", 0.0)
    client = SecClient(
        "IT Recruit sec-ops@it-recruit.jp",
        request_interval=0,
        max_attempts=2,
        session=session,
    )
    with pytest.raises(SecError, match="after 2 attempts"):
        client.get_bytes("https://data.sec.gov/test")


def test_sec_client_retries_502_then_succeeds(monkeypatch) -> None:
    session = FakeSession([FakeResponse(502), FakeResponse(200)])
    monkeypatch.setattr(sec.time, "sleep", lambda _: None)
    monkeypatch.setattr(sec, "_LAST_REQUEST_AT", 0.0)
    client = SecClient(
        "IT Recruit sec-ops@it-recruit.jp",
        request_interval=0,
        max_attempts=2,
        session=session,
    )

    assert client.get_bytes("https://data.sec.gov/test") == b"ok"
    assert len(session.urls) == 2


def test_sec_client_exhausted_504_raises_sec_error(monkeypatch) -> None:
    session = FakeSession([FakeResponse(504), FakeResponse(504)])
    monkeypatch.setattr(sec.time, "sleep", lambda _: None)
    monkeypatch.setattr(sec, "_LAST_REQUEST_AT", 0.0)
    client = SecClient(
        "IT Recruit sec-ops@it-recruit.jp",
        request_interval=0,
        max_attempts=2,
        session=session,
    )

    with pytest.raises(SecError, match="504.*after 2 attempts"):
        client.get_bytes("https://data.sec.gov/test")
    assert len(session.urls) == 2


def test_sec_client_404_fails_once_as_sec_error(monkeypatch) -> None:
    session = FakeSession([FakeResponse(404)])
    monkeypatch.setattr(sec.time, "sleep", lambda _: None)
    monkeypatch.setattr(sec, "_LAST_REQUEST_AT", 0.0)
    client = SecClient(
        "IT Recruit sec-ops@it-recruit.jp",
        request_interval=0,
        max_attempts=5,
        session=session,
    )

    with pytest.raises(SecError, match="non-retryable HTTP 404"):
        client.get_bytes("https://data.sec.gov/test")
    assert len(session.urls) == 1


class CacheClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get_json(self, url: str) -> dict:
        self.urls.append(url)
        return {
            "directory": {
                "item": [
                    {"name": "amzn-20231231.htm"},
                    {"name": "amzn-20231231_htm.xml"},
                    {"name": "amzn-20231231_cal.xml"},
                ]
            }
        }

    def get_bytes(self, url: str) -> bytes:
        self.urls.append(url)
        return b"filing content"


def test_cache_filing_package_uses_archive_urls_and_skips_existing(tmp_path) -> None:
    filing = SecFiling(
        accession_number="0001018724-24-000006",
        form="10-K",
        filing_date="2024-02-02",
        report_date="2023-12-31",
        acceptance_timestamp="2024-02-02T18:06:24.000Z",
        primary_document="amzn-20231231.htm",
        filer_name="Amazon.com, Inc.",
        cik="0001018724",
    )
    destination = tmp_path / "0001018724" / filing.accession_number
    client = CacheClient()
    kwargs = {
        "submissions_payload": {"name": "Amazon.com, Inc."},
        "historical_submissions": {},
        "companyfacts_payload": {"facts": {}},
    }

    assert cache_filing_package(client, filing, destination, **kwargs)
    first_urls = list(client.urls)
    assert not cache_filing_package(client, filing, destination, **kwargs)
    assert client.urls == first_urls
    assert (destination / "submissions.json").exists()
    assert (destination / "companyfacts.json").exists()
    assert (destination / "index.json").exists()
    assert (destination / "amzn-20231231.htm").exists()
    assert (destination / "amzn-20231231_htm.xml").exists()
    assert all(
        url.startswith(
            "https://www.sec.gov/Archives/edgar/data/1018724/000101872424000006/"
        )
        for url in first_urls
    )

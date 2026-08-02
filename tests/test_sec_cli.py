from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

import pytest

import it_recruit_data.sec_cli as sec_cli
from it_recruit_data.sec import SecError, SecFiling
from it_recruit_data.sec_cli import create_parser, run
from it_recruit_data.sec_normalize_cli import run as normalize_run
from it_recruit_data.store import (
    COMPANY_FIELDS,
    METRIC_FIELDS,
    SEGMENT_FIELDS,
    SOURCE_FIELDS,
)


def write_companies(path: Path, sec_cik: str = "1018724") -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COMPANY_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "company_id": "amazon-com",
                "display_name": "Amazon",
                "legal_name": "Amazon.com, Inc.",
                "securities_code": "",
                "corporate_number": "",
                "website_url": "https://www.amazon.com/",
                "edinet_code": "",
                "sec_cik": sec_cik,
                "ticker": "AMZN",
                "exchange": "NASDAQ",
                "country_code": "US",
                "is_active": "true",
            }
        )


def test_sec_fetch_parser_requires_exact_contract_options() -> None:
    parser = create_parser()
    args = parser.parse_args(
        [
            "amazon-com",
            "--start",
            "2024-01-01",
            "--end",
            "2024-12-31",
            "--form",
            "10-K",
            "--all",
            "--interval",
            "0.2",
            "--data-dir",
            "custom-data",
        ]
    )
    assert args.company_id == "amazon-com"
    assert args.form == "10-K"
    assert args.all is True
    assert args.interval == 0.2
    assert args.data_dir == Path("custom-data")
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "amazon-com",
                "--start",
                "2024-01-01",
                "--end",
                "2024-12-31",
                "--form",
                "10-Q",
            ]
        )


def test_sec_fetch_requires_user_agent_before_network(tmp_path: Path, monkeypatch) -> None:
    write_companies(tmp_path / "companies.csv")
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    args = argparse.Namespace(
        company_id="amazon-com",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        form="10-K",
        all=False,
        interval=0.1,
        data_dir=tmp_path,
    )
    with pytest.raises(SecError, match="SEC_USER_AGENT"):
        run(args)


def test_sec_fetch_does_not_fall_back_to_securities_code(
    tmp_path: Path, monkeypatch
) -> None:
    write_companies(tmp_path / "companies.csv", sec_cik="")
    monkeypatch.setenv("SEC_USER_AGENT", "IT Recruit sec-ops@it-recruit.jp")
    args = argparse.Namespace(
        company_id="amazon-com",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        form="10-K",
        all=False,
        interval=0.1,
        data_dir=tmp_path,
    )
    with pytest.raises(SecError, match="do not reuse"):
        run(args)


def test_sec_normalize_requires_matching_source_row(tmp_path: Path) -> None:
    write_companies(tmp_path / "companies.csv")
    accession = "0001018724-24-000006"
    filing_dir = tmp_path / "raw" / "sec" / "0001018724" / accession
    filing_dir.mkdir(parents=True)
    (filing_dir / "filing.json").write_text(
        json.dumps(
            {
                "accession_number": accession,
                "form": "10-K",
                "filing_date": "2024-02-02",
                "report_date": "2023-12-31",
                "acceptance_timestamp": "2024-02-02T18:06:24.000Z",
                "primary_document": "amzn-20231231.htm",
                "filer_name": "Amazon.com, Inc.",
                "cik": "0001018724",
            }
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        company_id="amazon-com",
        accession_number=accession,
        data_dir=tmp_path,
    )
    with pytest.raises(SecError, match="source row is missing"):
        normalize_run(args)


def test_sec_fetch_validation_failure_preserves_all_csvs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_companies(tmp_path / "companies.csv")
    paths = {
        "sources": tmp_path / "sources.csv",
        "metrics": tmp_path / "metrics.csv",
        "segments": tmp_path / "segments.csv",
    }
    for name, fields in (
        ("sources", SOURCE_FIELDS),
        ("metrics", METRIC_FIELDS),
        ("segments", SEGMENT_FIELDS),
    ):
        paths[name].write_text(",".join(fields) + "\n", encoding="utf-8")
    before = {name: path.read_bytes() for name, path in paths.items()}

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
    companyfacts = {
        "cik": 1018724,
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "start": "2023-01-01",
                                "end": "2023-12-31",
                                "val": 100,
                                "accn": filing.accession_number,
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                }
            }
        },
    }

    class FakeSecClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def discover_filings(self, *args, **kwargs):
            return [filing], {}, {}

        def companyfacts(self, cik: str) -> dict:
            return companyfacts

    def fake_cache(client, selected, destination, **kwargs) -> bool:
        destination.mkdir(parents=True)
        (destination / "filing.json").write_text(
            json.dumps(selected.__dict__),
            encoding="utf-8",
        )
        (destination / "companyfacts.json").write_text(
            json.dumps(kwargs["companyfacts_payload"]),
            encoding="utf-8",
        )
        (destination / "index.json").write_text(
            json.dumps(
                {
                    "directory": {
                        "item": [{"name": "amzn-20231231_htm.xml"}]
                    }
                }
            ),
            encoding="utf-8",
        )
        return True

    monkeypatch.setattr(sec_cli, "SecClient", FakeSecClient)
    monkeypatch.setattr(sec_cli, "cache_filing_package", fake_cache)
    monkeypatch.setenv("SEC_USER_AGENT", "IT Recruit sec-ops@it-recruit.jp")
    args = argparse.Namespace(
        company_id="amazon-com",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        form="10-K",
        all=False,
        interval=0.1,
        data_dir=tmp_path,
    )

    with pytest.raises(SecError, match="Required extracted XBRL instance is missing"):
        run(args)
    assert {name: path.read_bytes() for name, path in paths.items()} == before

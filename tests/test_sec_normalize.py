from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from it_recruit_data.sec import SecError
from it_recruit_data.sec_normalize import (
    normalize_aws_segments,
    normalize_companyfacts,
    normalize_sec_filing,
    read_xbrl_instance,
    select_aws_segments,
    select_companyfacts,
)

ACCESSION = "0001018724-24-000006"


def annual_fact(
    value: int,
    start: str,
    end: str,
    *,
    accession: str = ACCESSION,
    form: str = "10-K",
) -> dict:
    return {
        "start": start,
        "end": end,
        "val": value,
        "accn": accession,
        "form": form,
        "fy": 2023,
        "fp": "FY",
        "filed": "2024-02-02",
    }


def companyfacts_fixture() -> dict:
    revenue = [
        annual_fact(100, "2023-01-01", "2023-12-31"),
        annual_fact(90, "2022-01-01", "2022-12-31"),
        annual_fact(80, "2021-01-01", "2021-12-31"),
        annual_fact(
            999,
            "2023-01-01",
            "2023-12-31",
            accession="0001018724-23-000004",
        ),
        {
            **annual_fact(25, "2023-10-01", "2023-12-31"),
            "fp": "Q4",
        },
    ]
    return {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": revenue}
                },
                "Revenues": {
                    "units": {
                        "USD": [annual_fact(100, "2023-01-01", "2023-12-31")]
                    }
                },
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [annual_fact(12, "2023-01-01", "2023-12-31")]
                    }
                },
                "AssetsCurrent": {
                    "units": {
                        "USD": [
                            {
                                "end": "2023-12-31",
                                "val": 75,
                                "accn": ACCESSION,
                                "form": "10-K",
                                "fp": "FY",
                            },
                            {
                                "end": "2022-12-31",
                                "val": 65,
                                "accn": ACCESSION,
                                "form": "10-K",
                                "fp": "FY",
                            },
                        ]
                    }
                },
            },
            "dei": {
                "EntityNumberOfEmployees": {
                    "units": {
                        "employees": [
                            {
                                "end": "2023-12-31",
                                "val": 1500000,
                                "accn": ACCESSION,
                                "form": "10-K",
                                "fp": "FY",
                            }
                        ]
                    }
                }
            },
        }
    }


def test_select_companyfacts_keeps_selected_filing_comparatives() -> None:
    records = select_companyfacts(
        companyfacts_fixture(),
        accession_number=ACCESSION,
        form="10-K",
    )
    revenue = [record for record in records if record["metric_key"] == "revenue"]
    assert [(record["fiscal_year"], record["value"]) for record in revenue] == [
        ("2021", "80"),
        ("2022", "90"),
        ("2023", "100"),
    ]
    assert all(record["accounting_standard"] == "USGAAP" for record in records)
    assert next(
        record for record in records if record["metric_key"] == "employee_count"
    )["unit"] == "persons"


def test_select_companyfacts_rejects_inconsistent_aliases() -> None:
    payload = companyfacts_fixture()
    payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["val"] = 101
    with pytest.raises(SecError, match="Inconsistent canonical"):
        select_companyfacts(payload, accession_number=ACCESSION, form="10-K")


def test_select_companyfacts_rejects_zero_supported_metrics() -> None:
    with pytest.raises(SecError, match="no supported annual facts"):
        select_companyfacts(
            {"facts": {"ifrs-full": {}}},
            accession_number=ACCESSION,
            form="10-K",
        )


def test_select_companyfacts_rejects_unsupported_20f() -> None:
    with pytest.raises(SecError, match="Form 20-F taxonomy is unsupported"):
        select_companyfacts(
            companyfacts_fixture(),
            accession_number=ACCESSION,
            form="20-F",
        )


def test_companyfacts_csv_upserts_are_idempotent(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.csv"
    kwargs = {
        "company_id": "amazon-com",
        "payload": companyfacts_fixture(),
        "accession_number": ACCESSION,
        "form": "10-K",
        "source_id": "sec-0001018724-24-000006",
        "metrics_path": metrics_path,
    }
    first = normalize_companyfacts(**kwargs)
    second = normalize_companyfacts(**kwargs)
    with metrics_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert first == second == len(rows)
    assert len({(row["metric_key"], row["fiscal_year"]) for row in rows}) == len(rows)


def xbrl_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
  xmlns:xbrli="http://www.xbrl.org/2003/instance"
  xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
  xmlns:us-gaap="http://fasb.org/us-gaap/2024"
  xmlns:amzn="http://amazon.com/20231231"
  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <xbrli:context id="aws-business-2023">
    <xbrli:entity><xbrli:identifier scheme="sec">1018724</xbrli:identifier>
      <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">amzn:AmazonWebServicesMember</xbrldi:explicitMember></xbrli:segment>
    </xbrli:entity>
    <xbrli:period><xbrli:startDate>2023-01-01</xbrli:startDate><xbrli:endDate>2023-12-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:context id="aws-product-2023">
    <xbrli:entity><xbrli:identifier scheme="sec">1018724</xbrli:identifier>
      <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:ProductOrServiceAxis">amzn:AmazonWebServicesMember</xbrldi:explicitMember></xbrli:segment>
    </xbrli:entity>
    <xbrli:period><xbrli:startDate>2023-01-01</xbrli:startDate><xbrli:endDate>2023-12-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
  <us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="aws-business-2023" unitRef="usd" scale="2">100</us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax>
  <us-gaap:OperatingIncomeLoss contextRef="aws-business-2023" unitRef="usd">30</us-gaap:OperatingIncomeLoss>
  <us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="aws-product-2023" unitRef="usd">999</us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax>
  <us-gaap:OperatingIncomeLoss contextRef="aws-product-2023" unitRef="usd">999</us-gaap:OperatingIncomeLoss>
</xbrli:xbrl>
"""


def test_aws_segment_uses_business_axis_not_product_axis(tmp_path: Path) -> None:
    instance_path = tmp_path / "amzn-20231231_htm.xml"
    instance_path.write_text(xbrl_xml(), encoding="utf-8")
    records = select_aws_segments(
        read_xbrl_instance(instance_path),
        expected_cik="0001018724",
    )
    assert len(records) == 1
    assert records[0]["revenue"] == "10000"
    assert records[0]["segment_profit"] == "30"
    assert "StatementBusinessSegmentsAxis" in records[0]["note"]
    assert "aws-business-2023" in records[0]["note"]


def test_aws_segment_csv_upserts_are_idempotent(tmp_path: Path) -> None:
    instance_path = tmp_path / "amzn-20231231_htm.xml"
    instance_path.write_text(xbrl_xml(), encoding="utf-8")
    segments_path = tmp_path / "segments.csv"
    kwargs = {
        "company_id": "amazon-com",
        "instance_path": instance_path,
        "source_id": "sec-0001018724-24-000006",
        "segments_path": segments_path,
    }
    assert normalize_aws_segments(**kwargs) == 1
    assert normalize_aws_segments(**kwargs) == 1
    with segments_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["segment_id"] == "aws"


def test_aws_segment_fails_when_only_product_axis_exists(tmp_path: Path) -> None:
    instance_path = tmp_path / "product-only.xml"
    instance_path.write_text(
        xbrl_xml().replace("aws-business-2023", "aws-product-2023"),
        encoding="utf-8",
    )
    with pytest.raises(SecError, match="Required AWS annual segment facts"):
        select_aws_segments(read_xbrl_instance(instance_path))


def write_cached_filing(
    filing_dir: Path,
    *,
    companyfacts_cik: int = 1018724,
    instance_xml: str | None = None,
) -> None:
    filing_dir.mkdir(parents=True)
    (filing_dir / "filing.json").write_text(
        json.dumps(
            {
                "accession_number": ACCESSION,
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
    companyfacts = companyfacts_fixture()
    companyfacts["cik"] = companyfacts_cik
    (filing_dir / "companyfacts.json").write_text(
        json.dumps(companyfacts),
        encoding="utf-8",
    )
    (filing_dir / "index.json").write_text(
        json.dumps(
            {
                "directory": {
                    "item": [{"name": "amzn-20231231_htm.xml"}]
                }
            }
        ),
        encoding="utf-8",
    )
    if instance_xml is not None:
        (filing_dir / "amzn-20231231_htm.xml").write_text(
            instance_xml,
            encoding="utf-8",
        )


def test_normalize_sec_filing_rejects_mismatched_companyfacts_cik(
    tmp_path: Path,
) -> None:
    filing_dir = tmp_path / ACCESSION
    write_cached_filing(
        filing_dir,
        companyfacts_cik=1652044,
        instance_xml=xbrl_xml(),
    )

    with pytest.raises(SecError, match="Company Facts CIK does not match"):
        normalize_sec_filing(
            company_id="amazon-com",
            filing_dir=filing_dir,
            source_id="sec-0001018724-24-000006",
            metrics_path=tmp_path / "metrics.csv",
            segments_path=tmp_path / "segments.csv",
        )
    assert not (tmp_path / "metrics.csv").exists()
    assert not (tmp_path / "segments.csv").exists()


def test_normalize_sec_filing_rejects_mismatched_aws_context_cik_before_writes(
    tmp_path: Path,
) -> None:
    filing_dir = tmp_path / ACCESSION
    write_cached_filing(
        filing_dir,
        instance_xml=xbrl_xml().replace(
            ">1018724</xbrli:identifier>",
            ">1652044</xbrli:identifier>",
        ),
    )
    metrics_path = tmp_path / "metrics.csv"
    segments_path = tmp_path / "segments.csv"
    metrics_path.write_bytes(b"existing metrics\n")
    segments_path.write_bytes(b"existing segments\n")
    before = (metrics_path.read_bytes(), segments_path.read_bytes())

    with pytest.raises(SecError, match="context .* CIK does not match"):
        normalize_sec_filing(
            company_id="amazon-com",
            filing_dir=filing_dir,
            source_id="sec-0001018724-24-000006",
            metrics_path=metrics_path,
            segments_path=segments_path,
        )
    assert (metrics_path.read_bytes(), segments_path.read_bytes()) == before

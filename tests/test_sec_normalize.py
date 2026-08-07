from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from it_recruit_data.sec import SecError
from it_recruit_data.sec_normalize import (
    normalize_aws_segments,
    normalize_companyfacts,
    normalize_reportable_segments,
    normalize_sec_filing,
    read_xbrl_instance,
    select_reportable_segments,
    select_aws_segments,
    select_companyfacts,
)

ACCESSION = "0001018724-24-000006"
ACCENTURE_ACCESSION = "0001467373-25-000217"


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


def companyfacts_fixture(*, accession_number: str = ACCESSION) -> dict:
    revenue = [
        annual_fact(100, "2023-01-01", "2023-12-31", accession=accession_number),
        annual_fact(90, "2022-01-01", "2022-12-31", accession=accession_number),
        annual_fact(80, "2021-01-01", "2021-12-31", accession=accession_number),
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
                        "USD": [
                            annual_fact(
                                100,
                                "2023-01-01",
                                "2023-12-31",
                                accession=accession_number,
                            )
                        ]
                    }
                },
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [
                            annual_fact(
                                12,
                                "2023-01-01",
                                "2023-12-31",
                                accession=accession_number,
                            )
                        ]
                    }
                },
                "AssetsCurrent": {
                    "units": {
                        "USD": [
                            {
                                "end": "2023-12-31",
                                "val": 75,
                                "accn": accession_number,
                                "form": "10-K",
                                "fp": "FY",
                            },
                            {
                                "end": "2022-12-31",
                                "val": 65,
                                "accn": accession_number,
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
                                "accn": accession_number,
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


def reportable_segments_xml(
    *,
    cik: str = "1652044",
    duplicate_revenue: bool = False,
) -> str:
    periods = (
        ("2024", "2024-01-01", "2024-12-31"),
        ("2025", "2025-01-01", "2025-12-31"),
    )
    segments = (
        ("AmericasSegmentMember", "americas", ((100, 30), (110, 33))),
        ("EMEASegmentMember", "emea", ((200, 60), (220, 66))),
        ("AsiaPacificSegmentMember", "asia-pacific", ((300, 90), (330, 99))),
    )
    contexts: list[str] = []
    facts: list[str] = []
    for period_index, (fiscal_year, start, end) in enumerate(periods):
        for member, segment_id, values in segments:
            revenue_context = f"{segment_id}-{fiscal_year}-revenue"
            profit_context = f"{segment_id}-{fiscal_year}-profit"
            contexts.extend(
                [
                    f"""
  <xbrli:context id="{revenue_context}">
    <xbrli:entity><xbrli:identifier scheme="sec">{cik}</xbrli:identifier>
      <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">acme:{member}</xbrldi:explicitMember></xbrli:segment>
    </xbrli:entity>
    <xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period>
  </xbrli:context>""",
                    f"""
  <xbrli:context id="{profit_context}">
    <xbrli:entity><xbrli:identifier scheme="sec">{cik}</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="srt:ConsolidationItemsAxis">us-gaap:OperatingSegmentsMember</xbrldi:explicitMember>
        <xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">acme:{member}</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period>
  </xbrli:context>""",
                ]
            )
            revenue, profit = values[period_index]
            facts.extend(
                [
                    f'<us-gaap:Revenues contextRef="{revenue_context}" unitRef="usd">{revenue}</us-gaap:Revenues>',
                    f'<us-gaap:OperatingIncomeLoss contextRef="{profit_context}" unitRef="usd">{profit}</us-gaap:OperatingIncomeLoss>',
                ]
            )
    contexts.append(
        f"""
  <xbrli:context id="product-axis-2025">
    <xbrli:entity><xbrli:identifier scheme="sec">{cik}</xbrli:identifier>
      <xbrli:segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">acme:AmericasSegmentMember</xbrldi:explicitMember>
        <xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">acme:ConsultingMember</xbrldi:explicitMember>
      </xbrli:segment>
    </xbrli:entity>
    <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2025-01-01</xbrli:endDate></xbrli:period>
  </xbrli:context>"""
    )
    facts.extend(
        [
            '<us-gaap:Revenues contextRef="product-axis-2025" unitRef="usd">999</us-gaap:Revenues>',
            '<us-gaap:OperatingIncomeLoss contextRef="product-axis-2025" unitRef="usd">999</us-gaap:OperatingIncomeLoss>',
        ]
    )
    if duplicate_revenue:
        facts.append(
            '<us-gaap:Revenues contextRef="americas-2024-revenue" unitRef="usd">999</us-gaap:Revenues>'
        )
    contexts_text = "".join(contexts)
    facts_text = "\n".join(facts)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
  xmlns:xbrli="http://www.xbrl.org/2003/instance"
  xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
  xmlns:us-gaap="http://fasb.org/us-gaap/2024"
  xmlns:srt="http://fasb.org/srt/2024"
  xmlns:acme="http://example.com/acme/2024"
  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
{contexts_text}
  <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
{facts_text}
</xbrli:xbrl>
"""


def test_reportable_segments_use_business_axis_and_combine_annual_facts(
    tmp_path: Path,
) -> None:
    instance_path = tmp_path / "reportable.xml"
    instance_path.write_text(reportable_segments_xml(), encoding="utf-8")
    instance = read_xbrl_instance(instance_path)

    records = select_reportable_segments(instance, expected_cik="0001652044")
    by_key = {
        (record["fiscal_year"], record["segment_id"]): record for record in records
    }
    assert len(records) == 6
    assert {
        key: (record["revenue"], record["segment_profit"], record["segment_name"])
        for key, record in by_key.items()
    } == {
        ("2024", "americas"): ("100", "30", "Americas"),
        ("2024", "emea"): ("200", "60", "EMEA"),
        ("2024", "asia-pacific"): ("300", "90", "Asia Pacific"),
        ("2025", "americas"): ("110", "33", "Americas"),
        ("2025", "emea"): ("220", "66", "EMEA"),
        ("2025", "asia-pacific"): ("330", "99", "Asia Pacific"),
    }
    assert all(record["profit_measure"] == "OperatingIncomeLoss" for record in records)
    assert all(record["currency"] == record["unit"] == "USD" for record in records)
    assert all("999" not in record["note"] for record in records)

    segments_path = tmp_path / "segments.csv"
    kwargs = {
        "company_id": "acme",
        "instance_path": instance_path,
        "source_id": "sec-0001652044-25-000001",
        "segments_path": segments_path,
        "expected_cik": "1652044",
    }
    assert normalize_reportable_segments(**kwargs) == 6
    assert normalize_reportable_segments(**kwargs) == 6
    with segments_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 6
    assert {row["source_id"] for row in rows} == {kwargs["source_id"]}


def test_reportable_segments_reject_inconsistent_duplicate_facts(tmp_path: Path) -> None:
    instance_path = tmp_path / "duplicate.xml"
    instance_path.write_text(
        reportable_segments_xml(duplicate_revenue=True),
        encoding="utf-8",
    )
    with pytest.raises(SecError, match="Inconsistent reportable segment revenue facts"):
        select_reportable_segments(read_xbrl_instance(instance_path))


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


def write_cached_non_amazon_filing(filing_dir: Path, instance_xml: str) -> None:
    filing_dir.mkdir(parents=True)
    (filing_dir / "filing.json").write_text(
        json.dumps(
            {
                "accession_number": ACCENTURE_ACCESSION,
                "form": "10-K",
                "filing_date": "2025-10-10",
                "report_date": "2025-08-31",
                "acceptance_timestamp": "2025-10-10T06:53:53.000Z",
                "primary_document": "acn-20250831.htm",
                "filer_name": "Accenture plc",
                "cik": "0001467373",
            }
        ),
        encoding="utf-8",
    )
    companyfacts = companyfacts_fixture(accession_number=ACCENTURE_ACCESSION)
    companyfacts["cik"] = 1467373
    (filing_dir / "companyfacts.json").write_text(
        json.dumps(companyfacts),
        encoding="utf-8",
    )
    (filing_dir / "index.json").write_text(
        json.dumps(
            {"directory": {"item": [{"name": "acn-20250831_htm.xml"}]}}
        ),
        encoding="utf-8",
    )
    (filing_dir / "acn-20250831_htm.xml").write_text(
        instance_xml,
        encoding="utf-8",
    )


def unsegmented_xbrl_xml(*, cik: str = "1467373") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
  xmlns:xbrli="http://www.xbrl.org/2003/instance"
  xmlns:us-gaap="http://fasb.org/us-gaap/2024"
  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <xbrli:context id="annual">
    <xbrli:entity><xbrli:identifier scheme="sec">{cik}</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2024-09-01</xbrli:startDate><xbrli:endDate>2025-08-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
  <us-gaap:Revenues contextRef="annual" unitRef="usd">100</us-gaap:Revenues>
  <us-gaap:OperatingIncomeLoss contextRef="annual" unitRef="usd">10</us-gaap:OperatingIncomeLoss>
</xbrli:xbrl>
"""


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


def test_normalize_sec_filing_uses_generic_segments_for_non_amazon(
    tmp_path: Path,
) -> None:
    filing_dir = tmp_path / ACCENTURE_ACCESSION
    write_cached_non_amazon_filing(
        filing_dir,
        reportable_segments_xml(cik="1467373"),
    )
    metrics_path = tmp_path / "metrics.csv"
    segments_path = tmp_path / "segments.csv"
    kwargs = {
        "company_id": "accenture",
        "filing_dir": filing_dir,
        "source_id": "sec-0001467373-25-000217",
        "metrics_path": metrics_path,
        "segments_path": segments_path,
    }

    first = normalize_sec_filing(**kwargs)
    second = normalize_sec_filing(**kwargs)

    assert first == second
    assert first[1] == 6
    with metrics_path.open(encoding="utf-8", newline="") as file:
        metric_rows = list(csv.DictReader(file))
    with segments_path.open(encoding="utf-8", newline="") as file:
        segment_rows = list(csv.DictReader(file))
    assert len(metric_rows) == first[0]
    assert all(row["accounting_standard"] == "USGAAP" for row in metric_rows)
    assert all(row["scope"] == "consolidated" for row in metric_rows)
    assert len(segment_rows) == 6
    assert all(row["source_id"] == kwargs["source_id"] for row in segment_rows)
    assert all(row["unit"] == row["currency"] == "USD" for row in segment_rows)
    assert all(
        row["profit_measure"] == "OperatingIncomeLoss" for row in segment_rows
    )


def test_normalize_sec_filing_allows_non_amazon_without_reportable_segments(
    tmp_path: Path,
) -> None:
    filing_dir = tmp_path / ACCENTURE_ACCESSION
    write_cached_non_amazon_filing(
        filing_dir,
        unsegmented_xbrl_xml(),
    )

    metric_count, segment_count = normalize_sec_filing(
        company_id="accenture",
        filing_dir=filing_dir,
        source_id="sec-0001467373-25-000217",
        metrics_path=tmp_path / "metrics.csv",
        segments_path=tmp_path / "segments.csv",
    )

    assert metric_count > 0
    assert segment_count == 0

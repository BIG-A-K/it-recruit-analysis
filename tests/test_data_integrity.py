import csv
from decimal import Decimal
from pathlib import Path

DATA_DIR = Path(__file__).parents[1] / "data"
COMPANY_PAGE_DIR = (
    Path(__file__).parents[1]
    / "site"
    / "src"
    / "pages"
    / "companies"
)


def read_rows(filename: str) -> list[dict[str, str]]:
    with (DATA_DIR / filename).open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def assert_unique(
    rows: list[dict[str, str]],
    fields: tuple[str, ...],
) -> None:
    keys = [tuple(row[field] for field in fields) for row in rows]
    assert len(keys) == len(set(keys))


def test_metric_integrity() -> None:
    companies = {row["company_id"] for row in read_rows("companies.csv")}
    sources = {row["source_id"] for row in read_rows("sources.csv")}
    rows = read_rows("metrics.csv")

    assert_unique(
        rows,
        ("company_id", "metric_key", "fiscal_year", "scope"),
    )
    for row in rows:
        assert row["company_id"] in companies
        assert row["availability"] in {
            "reported",
            "not_disclosed",
            "not_applicable",
            "unavailable",
        }
        if row["availability"] == "reported":
            Decimal(row["value"])
            assert row["unit"]
            assert row["source_id"] in sources


def test_segment_integrity() -> None:
    companies = {row["company_id"] for row in read_rows("companies.csv")}
    sources = {row["source_id"] for row in read_rows("sources.csv")}
    rows = read_rows("segments.csv")

    assert_unique(rows, ("company_id", "fiscal_year", "segment_id"))
    for row in rows:
        assert row["company_id"] in companies
        if row["availability"] == "reported":
            assert row["revenue"] or row["segment_profit"]
            if row["revenue"]:
                Decimal(row["revenue"])
            if row["segment_profit"]:
                Decimal(row["segment_profit"])
                assert row["profit_measure"]
            assert row["unit"]
            assert row["source_id"] in sources


def test_company_profile_integrity() -> None:
    companies = {row["company_id"] for row in read_rows("companies.csv")}
    rows = read_rows("company_profiles.csv")

    assert_unique(rows, ("company_id",))
    for row in rows:
        assert row["company_id"] in companies
        assert row["overview"]
        assert row["career_url"].startswith("https://")
        assert row["recruitment_summary"]
        assert row["updated_at"]


def test_company_message_integrity() -> None:
    companies = {row["company_id"] for row in read_rows("companies.csv")}
    rows = read_rows("company_messages.csv")

    assert_unique(rows, ("company_id",))
    for row in rows:
        assert row["company_id"] in companies
        assert row["message"]
        assert row["source_label"]


def test_company_annotation_integrity() -> None:
    companies = {row["company_id"] for row in read_rows("companies.csv")}
    sources = {row["source_id"] for row in read_rows("sources.csv")}
    metric_keys = {row["metric_key"] for row in read_rows("metrics.csv")}
    rows = read_rows("company_annotations.csv")

    assert_unique(rows, ("annotation_id",))
    for row in rows:
        assert row["company_id"] in companies
        assert row["section_key"] == "financials"
        assert row["target_kind"] in {"section", "metric_group", "metric"}
        if row["target_kind"] == "section":
            assert not row["target_key"]
        elif row["target_kind"] == "metric_group":
            assert row["target_key"] in {"cash_flow"}
        else:
            assert row["target_key"] in metric_keys or row["target_key"] == "net_cf"
        if row["fiscal_year"]:
            assert len(row["fiscal_year"]) == 4
            int(row["fiscal_year"])
        assert row["text"]
        if row["source_id"]:
            assert row["source_id"] in sources
        assert row["updated_at"]


def test_segment_description_integrity() -> None:
    companies = {row["company_id"] for row in read_rows("companies.csv")}
    segment_keys = {
        (row["company_id"], row["segment_id"])
        for row in read_rows("segments.csv")
    }
    rows = read_rows("segment_descriptions.csv")

    assert_unique(rows, ("company_id", "segment_id"))
    for row in rows:
        assert row["company_id"] in companies
        assert (row["company_id"], row["segment_id"]) in segment_keys
        assert row["description"]


def test_initial_companies_have_comparison_data() -> None:
    initial_companies = {
        "recruit-holdings",
        "ly-corporation",
        "mercari",
        "cyberagent",
        "dena",
        "ntt-data-group",
        "scsk",
    }
    active_companies = {
        row["company_id"]
        for row in read_rows("companies.csv")
        if row["is_active"] == "true"
        and row["company_id"] in initial_companies
    }
    metric_rows = [
        row
        for row in read_rows("metrics.csv")
        if row["availability"] == "reported"
    ]
    financial_metrics = {
        "revenue",
        "operating_profit",
        "operating_cf",
        "investing_cf",
        "financing_cf",
        "equity_ratio",
    }
    employee_metrics = {
        "average_annual_salary",
        "average_age",
        "average_tenure",
    }

    for company_id in active_companies:
        company_rows = [
            row for row in metric_rows if row["company_id"] == company_id
        ]
        for metric_key in financial_metrics:
            fiscal_years = {
                row["fiscal_year"]
                for row in company_rows
                if row["metric_key"] == metric_key
            }
            assert len(fiscal_years) >= 3, (company_id, metric_key)
        for metric_key in employee_metrics:
            assert any(
                row["metric_key"] == metric_key for row in company_rows
            ), (company_id, metric_key)

        segment_years = {
            row["fiscal_year"]
            for row in read_rows("segments.csv")
            if row["company_id"] == company_id
            and row["availability"] == "reported"
        }
        assert len(segment_years) >= 2, company_id


def test_active_companies_have_mdx_pages() -> None:
    active_company_ids = {
        row["company_id"]
        for row in read_rows("companies.csv")
        if row["is_active"] == "true"
    }
    page_ids = {path.stem for path in COMPANY_PAGE_DIR.glob("*.mdx")}

    assert page_ids == active_company_ids
    for company_id in page_ids:
        page = (COMPANY_PAGE_DIR / f"{company_id}.mdx").read_text(encoding="utf-8")
        assert f"companyId: {company_id}" in page


def test_unlisted_company_pages_omit_unavailable_data_sections() -> None:
    unlisted_company_ids = {
        row["company_id"]
        for row in read_rows("companies.csv")
        if row["is_active"] == "true" and not row["securities_code"]
    }
    unavailable_components = {
        "EmploymentOverview",
        "BusinessSegments",
        "HealthMetrics",
        "FinancialHistory",
        "MetricTrends",
        "FinancialData",
    }

    for company_id in unlisted_company_ids:
        page = (COMPANY_PAGE_DIR / f"{company_id}.mdx").read_text(encoding="utf-8")
        for component in unavailable_components:
            assert component not in page, (company_id, component)

import csv
import re
from datetime import date
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


def test_company_identifiers_and_relations() -> None:
    company_rows = read_rows("companies.csv")
    companies = {row["company_id"] for row in company_rows}
    sources = {row["source_id"] for row in read_rows("sources.csv")}

    assert_unique(company_rows, ("company_id",))
    for row in company_rows:
        if row["sec_cik"]:
            assert re.fullmatch(r"\d{10}", row["sec_cik"])
            assert row["ticker"]
            assert row["exchange"]
        if row["country_code"]:
            assert re.fullmatch(r"[A-Z]{2}", row["country_code"])

    relation_rows = read_rows("company_relations.csv")
    assert_unique(
        relation_rows,
        ("from_company_id", "to_company_id", "relation_type", "valid_from"),
    )
    for row in relation_rows:
        assert row["from_company_id"] in companies
        assert row["to_company_id"] in companies
        assert row["relation_type"] in {
            "parent",
            "subsidiary",
            "affiliate",
            "brand",
            "other",
        }
        assert date.fromisoformat(row["valid_from"])
        if row["valid_to"]:
            assert date.fromisoformat(row["valid_to"])
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


def test_company_articles_have_common_content_sections() -> None:
    active_company_ids = {
        row["company_id"]
        for row in read_rows("companies.csv")
        if row["is_active"] == "true"
    }
    # 住友重機械の /saiyo/ のように、採用サイトのパスが英単語でない企業もある
    recruitment_url = re.compile(
        r"https?://[^)\s]*"
        r"(?:recruit|career|careers|jobs|employ|saiyo|shinsotsu)"
        r"[^)\s]*"
    )
    confirmation_date = re.compile(
        r"20\d{2}年\d{1,2}月\d{1,2}日(?:確認|に確認)"
    )

    for company_id in active_company_ids:
        page = (COMPANY_PAGE_DIR / f"{company_id}.mdx").read_text(
            encoding="utf-8"
        )
        assert f"<CompanyOverview companyId={{frontmatter.companyId}} />" in page
        assert "<CompanyProse>" in page
        assert "<CompanySources " in page
        assert recruitment_url.search(page), company_id
        assert confirmation_date.search(page), company_id


def test_new_game_companies_have_operating_profit() -> None:
    game_company_ids = {
        "nintendo",
        "takara-tomy",
        "bandai-namco",
        "capcom",
        "konami",
        "square-enix",
        "sega-sammy",
        "koei-tecmo",
    }
    rows = read_rows("metrics.csv")

    for company_id in game_company_ids:
        assert any(
            row["company_id"] == company_id
            and row["metric_key"] == "operating_profit"
            and row["availability"] == "reported"
            for row in rows
        ), company_id


def test_heavy_industry_companies_have_profit_and_quick_assets() -> None:
    # 重工各社は営業利益を開示する会社と事業利益で開示する会社が混在するため、
    # 定義の違う値を同じ metric_key へ寄せず、どちらかが揃っていることだけ確認する
    heavy_industry_company_ids = {
        row["company_id"]
        for row in read_rows("company_industries.csv")
        if row["industry_id"] == "heavy-industry"
    }
    assert heavy_industry_company_ids
    rows = read_rows("metrics.csv")

    for company_id in heavy_industry_company_ids:
        reported = {
            row["metric_key"]
            for row in rows
            if row["company_id"] == company_id
            and row["availability"] == "reported"
        }
        assert reported & {"operating_profit", "business_profit"}, company_id
        assert "quick_assets" in reported, company_id
        assert not (
            "operating_profit" in reported and "business_profit" in reported
        ), company_id


def test_unlisted_company_pages_omit_unavailable_data_sections() -> None:
    unlisted_company_ids = {
        row["company_id"]
        for row in read_rows("companies.csv")
        if row["is_active"] == "true" and not row["securities_code"]
    }
    unavailable_components = {
        "EmploymentOverview",
        "HealthMetrics",
        "FinancialHistory",
        "MetricTrends",
        "FinancialData",
    }
    segments_by_company = {
        row["company_id"]
        for row in read_rows("segments.csv")
    }

    for company_id in unlisted_company_ids:
        page = (COMPANY_PAGE_DIR / f"{company_id}.mdx").read_text(encoding="utf-8")
        for component in unavailable_components:
            assert f"<{component} companyId={{frontmatter.companyId}}" not in page, (
                company_id,
                component,
            )
        if company_id not in segments_by_company:
            assert (
                "<BusinessSegments companyId={frontmatter.companyId}" not in page
            ), company_id


def test_aws_page_separates_recruiting_and_disclosure_entities() -> None:
    page = (COMPANY_PAGE_DIR / "aws-japan.mdx").read_text(encoding="utf-8")
    assert ":::warn" in page
    assert '<FinancialHistory companyId="amazon-com" />' in page
    assert '<MetricTrends companyId="amazon-com" />' in page
    assert '<BusinessSegments companyId="amazon-com" showShare={false} />' in page
    assert not any(
        row["company_id"] == "aws-japan" for row in read_rows("metrics.csv")
    )

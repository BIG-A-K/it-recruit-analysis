from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from it_recruit_data.store import (
    METRIC_FIELDS,
    SEGMENT_FIELDS,
    upsert_row,
)

YEAR_CONTEXT = re.compile(
    r"^(CurrentYear|Prior([1-4])Year)(Duration|Instant)"
    r"(?:_.+)?$"
)
CONSOLIDATED_CONTEXT = re.compile(
    r"^(CurrentYear|Prior[1-4]Year)(Duration|Instant)$"
)
NON_CONSOLIDATED_CONTEXT = re.compile(
    r"^(CurrentYear|Prior[1-4]Year)(Duration|Instant)"
    r"_NonConsolidatedMember$"
)


@dataclass(frozen=True)
class MetricRule:
    metric_key: str
    element_id: str
    scope: str
    accounting_standard: str
    output_unit: str
    multiplier: Decimal = Decimal("1")
    company_ids: frozenset[str] | None = None


METRIC_RULES = (
    MetricRule(
        "average_annual_salary",
        "jpcrp_cor:AverageAnnualSalaryInformationAboutReportingCompanyInformationAboutEmployees",
        "non_consolidated",
        "",
        "JPY",
    ),
    MetricRule(
        "average_age",
        "jpcrp_cor:AverageAgeYearsInformationAboutReportingCompanyInformationAboutEmployees",
        "non_consolidated",
        "",
        "years",
    ),
    MetricRule(
        "average_tenure",
        "jpcrp_cor:AverageLengthOfServiceYearsInformationAboutReportingCompanyInformationAboutEmployees",
        "non_consolidated",
        "",
        "years",
    ),
    MetricRule(
        "revenue",
        "jpcrp_cor:RevenueIFRSSummaryOfBusinessResults",
        "consolidated",
        "IFRS",
        "JPY",
    ),
    MetricRule(
        "operating_profit",
        "jpigp_cor:OperatingProfitLossIFRS",
        "consolidated",
        "IFRS",
        "JPY",
    ),
    MetricRule(
        "operating_cf",
        "jpcrp_cor:CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults",
        "consolidated",
        "IFRS",
        "JPY",
    ),
    MetricRule(
        "investing_cf",
        "jpcrp_cor:CashFlowsFromUsedInInvestingActivitiesIFRSSummaryOfBusinessResults",
        "consolidated",
        "IFRS",
        "JPY",
    ),
    MetricRule(
        "financing_cf",
        "jpcrp_cor:CashFlowsFromUsedInFinancingActivitiesIFRSSummaryOfBusinessResults",
        "consolidated",
        "IFRS",
        "JPY",
    ),
    MetricRule(
        "equity_ratio",
        "jpcrp_cor:RatioOfOwnersEquityToGrossAssetsIFRSSummaryOfBusinessResults",
        "consolidated",
        "IFRS",
        "percent",
        Decimal("100"),
    ),
    MetricRule(
        "revenue",
        "jpcrp_cor:NetSalesSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=frozenset({"cyberagent", "tis"}),
    ),
    MetricRule(
        "operating_profit",
        "jppfs_cor:OperatingIncome",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=frozenset({"cyberagent", "tis"}),
    ),
    MetricRule(
        "operating_cf",
        "jpcrp_cor:NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=frozenset({"cyberagent", "tis"}),
    ),
    MetricRule(
        "investing_cf",
        "jpcrp_cor:NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=frozenset({"cyberagent", "tis"}),
    ),
    MetricRule(
        "financing_cf",
        "jpcrp_cor:NetCashProvidedByUsedInFinancingActivitiesSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=frozenset({"cyberagent", "tis"}),
    ),
    MetricRule(
        "equity_ratio",
        "jpcrp_cor:EquityToAssetRatioSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "percent",
        Decimal("100"),
        frozenset({"cyberagent", "tis"}),
    ),
)

METRIC_LOCAL_NAME_ALIASES = {
    "OperatingProfitLossIFRSSummaryOfBusinessResults": (
        "jpigp_cor:OperatingProfitLossIFRS"
    ),
    "NetSalesIFRSKeyFinancialData": (
        "jpcrp_cor:RevenueIFRSSummaryOfBusinessResults"
    ),
    "NetSalesIFRSSummaryOfBusinessResults": (
        "jpcrp_cor:RevenueIFRSSummaryOfBusinessResults"
    ),
}

COMPANY_SEGMENTS = {
    "recruit-holdings": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:SegmentProfitLossIFRS",
        "profit_measure": "EBITDA+S",
        "members": {
            "HRTechnologyReportableSegmentMember": (
                "hr-technology",
                "HRテクノロジー事業",
            ),
            "StaffingReportableSegmentsMember": (
                "staffing",
                "人材派遣事業",
            ),
            "MarketingMatchingTechnologiesReportableSegmentMember": (
                "marketing-matching-technologies",
                "マーケティング・マッチング・テクノロジー事業",
            ),
        },
    },
    "ly-corporation": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "MediaBusinessReportableSegmentMember": (
                "media",
                "メディア事業",
            ),
            "CommerceReportableSegmentMember": (
                "commerce",
                "コマース事業",
            ),
            "StragegyReportableSegmentMember": (
                "strategy",
                "戦略事業",
            ),
        },
    },
    "mercari": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "JapanRegionReportableSegmentMember": (
                "japan",
                "Japan Region",
            ),
            "USReportableSegmentMember": (
                "us",
                "US",
            ),
        },
    },
    "cyberagent": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "MediaAndIPReportableSegmemtsMember": (
                "media-and-ip",
                "メディア&IP事業",
            ),
            "InternetAdvertisementBusinessReportableSegmentsMember": (
                "internet-advertising",
                "インターネット広告事業",
            ),
            "GameBusinessReportableSegmentsMember": (
                "game",
                "ゲーム事業",
            ),
            "InvestmentDevelopmentBusinessReportableSegmentsMember": (
                "investment-development",
                "投資育成事業",
            ),
        },
    },
    "dena": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:SegmentProfitLossIFRS",
        "profit_measure": "セグメント利益",
        "members": {
            "GameBusinessReportableSegmentMember": ("game", "ゲーム事業"),
            "LiveStreamingBusinessReportableSegmentMember": (
                "live-streaming",
                "ライブストリーミング事業",
            ),
            "SportsSmartCityBusinessReportableSegmentMember": (
                "sports-smart-city",
                "スポーツ・スマートシティ事業",
            ),
            "HealthcareAndMedicalBusinessReportableSegmentMember": (
                "healthcare-medical",
                "ヘルスケア・メディカル事業",
            ),
            "NewBusinessesAndOthersReportableSegmentMember": (
                "new-businesses-and-others",
                "新規事業・その他",
            ),
        },
    },
    "ntt-data-group": {
        "revenue_element_id": "jpigp_cor:SalesToExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "JapanReportableSegmentMember": ("japan", "国内事業"),
            "OverseasReportableSegmentMember": ("overseas", "海外事業"),
        },
    },
    "scsk": {
        "revenue_element_id": "jpigp_cor:SalesToExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "IndustrialITReportableSegmentMember": ("industrial-it", "産業IT"),
            "FinancialITReportableSegmentMember": ("financial-it", "金融IT"),
            "ITSolutionReportableSegmentMember": (
                "it-solution",
                "ITソリューション",
            ),
            "ITPlatformReportableSegmentMember": (
                "it-platform",
                "ITプラットフォーム",
            ),
            "ITManagementReportableSegmentMember": (
                "it-management",
                "ITマネジメント",
            ),
        },
    },
    "softbank": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "",
        "profit_measure": "",
        "members": {
            "ConsumerReportableSegmentMember": ("consumer", "コンシューマ"),
            "EnterpriseReportableSegmentMember": ("enterprise", "エンタープライズ"),
            "DistributionReportableSegmentMember": ("distribution", "ディストリビューション"),
            "MediaECReportableSegmentMember": ("media-ec", "メディア・EC"),
            "FinancialReportableSegmentMember": ("financial", "ファイナンス"),
        },
    },
    "kddi": {
        "revenue_element_id": "jpigp_cor:SalesToExternalCustomersIFRS",
        "profit_element_id": "",
        "profit_measure": "",
        "members": {
            "PersonalReportableSegmentMember": ("personal", "パーソナル"),
            "BusinessReportableSegmentMember": ("business", "ビジネス"),
        },
    },
    "fujitsu": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "",
        "profit_measure": "",
        "members": {
            "ServiceSolutionsReportableSegmentMember": ("service-solutions", "サービスソリューション"),
            "HardwareSolutionsReportableSegmentMember": ("hardware-solutions", "ハードウェアソリューション"),
            "UbiquitousSolutionsReportableSegmentMember": ("ubiquitous-solutions", "ユビキタスソリューション"),
        },
    },
    "nec": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "",
        "profit_measure": "",
        "members": {
            "ITServicesReportableSegmentMember": ("it-services", "ITサービス"),
            "SocialInfrastructureReportableSegmentsMember": ("social-infrastructure", "社会インフラ"),
        },
    },
    "hitachi": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "",
        "profit_measure": "",
        "members": {
            "DigitalSystemsAndServicesReportableSegmentMember": ("digital-systems-services", "デジタルシステム&サービス"),
            "EnergyReportableSegmentMember": ("energy", "エナジー"),
            "MobilityReportableSegmentMember": ("mobility", "モビリティ"),
            "ConnectiveIndustriesReportableSegmentMember": ("connective-industries", "コネクティブインダストリーズ"),
        },
    },
    "nri": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "",
        "profit_measure": "",
        "members": {
            "ConsultingReportableSegmentMember": ("consulting", "コンサルティング"),
            "FinancialITSolutionsReportableSegmentMember": ("financial-it-solutions", "金融ITソリューション"),
            "IndustrialITSolutionsReportableSegmentMember": ("industrial-it-solutions", "産業ITソリューション"),
            "ITPlatformServicesReportableSegmentMember": ("it-platform-services", "IT基盤サービス"),
        },
    },
    "tis": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "セグメント利益",
        "members": {
            "OfferingServiceBusinessReportableSegmentsMember": ("offering-services", "オファリングサービス"),
            "BusinessProcessManagementReportableSegmentsMember": ("bpm", "BPM"),
            "FinancialITBusinessReportableSegmentsMember": ("financial-it", "金融IT"),
            "IndustrialITBusinessReportableSegmentsMember": ("industrial-it", "産業IT"),
            "RegionalITSolutionsReportableSegmentsMember": ("regional-it-solutions", "広域ITソリューション"),
        },
    },
    "biprogy": {
        "revenue_element_id": "jpigp_cor:RevenueIFRS",
        "profit_element_id": "",
        "profit_measure": "",
        "members": {
            "SystemServicesReportableSegmentMember": ("system-services", "システムサービス"),
            "SupportServicesReportableSegmentMember": ("support-services", "サポートサービス"),
            "OutsourcingReportableSegmentMember": ("outsourcing", "アウトソーシング"),
            "SoftwareReportableSegmentMember": ("software", "ソフトウェア"),
            "HardwareReportableSegmentMember": ("hardware", "ハードウェア"),
        },
    },
}


def read_edinet_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-16", newline="") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def find_filing_csv(filing_dir: Path) -> Path:
    candidates = sorted((filing_dir / "XBRL_TO_CSV").glob("jpcrp*-asr-*.csv"))
    if len(candidates) != 1:
        raise RuntimeError(
            f"有価証券報告書CSVを一意に特定できません: {filing_dir}"
        )
    return candidates[0]


def fiscal_year_from_context(context_id: str, latest_year: int) -> int | None:
    match = YEAR_CONTEXT.match(context_id)
    if not match:
        return None
    offset = int(match.group(2) or "0")
    return latest_year - offset


def period_end_for_year(latest_period_end: str, fiscal_year: int) -> str:
    latest = date.fromisoformat(latest_period_end)
    return latest.replace(year=fiscal_year).isoformat()


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def is_metric_context(context_id: str, scope: str) -> bool:
    if scope == "consolidated":
        return CONSOLIDATED_CONTEXT.fullmatch(context_id) is not None
    if scope == "non_consolidated":
        return NON_CONSOLIDATED_CONTEXT.fullmatch(context_id) is not None
    return False


def normalize_metrics(
    *,
    company_id: str,
    filing_dir: Path,
    latest_period_end: str,
    source_id: str,
    metrics_path: Path,
) -> int:
    rows = read_edinet_rows(find_filing_csv(filing_dir))
    rules = {rule.element_id: rule for rule in METRIC_RULES}
    latest_year = date.fromisoformat(latest_period_end).year
    records: dict[tuple[str, str, int, str], dict[str, str]] = {}

    for source_row in rows:
        element_id = source_row["要素ID"]
        rule = rules.get(element_id)
        if rule is None:
            local_name = element_id.rsplit(":", 1)[-1]
            canonical_element_id = METRIC_LOCAL_NAME_ALIASES.get(local_name)
            if canonical_element_id is not None:
                rule = rules[canonical_element_id]
        if rule is None:
            continue
        if rule.company_ids is not None and company_id not in rule.company_ids:
            continue

        context_id = source_row["コンテキストID"]
        if not is_metric_context(context_id, rule.scope):
            continue
        fiscal_year = fiscal_year_from_context(context_id, latest_year)
        raw_value = source_row["値"]
        if fiscal_year is None or raw_value in {"", "－", "-"}:
            continue

        value = Decimal(raw_value) * rule.multiplier
        record = {
            "company_id": company_id,
            "metric_key": rule.metric_key,
            "fiscal_year": str(fiscal_year),
            "period_end": period_end_for_year(
                latest_period_end,
                fiscal_year,
            ),
            "value": decimal_text(value),
            "unit": rule.output_unit,
            "scope": rule.scope,
            "accounting_standard": rule.accounting_standard,
            "availability": "reported",
            "source_id": source_id,
            "note": f"element_id={element_id}; context_id={context_id}",
        }
        key = (
            company_id,
            rule.metric_key,
            fiscal_year,
            rule.scope,
        )
        existing = records.get(key)
        if existing is not None:
            if existing["value"] != record["value"]:
                raise RuntimeError(
                    "同一指標・年度・範囲で値が競合しています: "
                    f"{key}: {existing['value']} != {record['value']}"
                )
            continue
        records[key] = record

    for record in records.values():
        upsert_row(
            metrics_path,
            key_fields=("company_id", "metric_key", "fiscal_year", "scope"),
            fieldnames=METRIC_FIELDS,
            row=record,
        )

    return len(records)


def segment_member(
    context_id: str,
    company_id: str = "recruit-holdings",
) -> tuple[str, str] | None:
    config = COMPANY_SEGMENTS.get(company_id)
    if config is None:
        return None
    for member, segment in config["members"].items():
        if context_id.endswith(member):
            return segment
    return None


def normalize_segments(
    *,
    company_id: str,
    filing_dir: Path,
    latest_period_end: str,
    source_id: str,
    segments_path: Path,
) -> int:
    config = COMPANY_SEGMENTS.get(company_id)
    if config is None:
        return 0

    rows = read_edinet_rows(find_filing_csv(filing_dir))
    latest_year = date.fromisoformat(latest_period_end).year
    records: dict[tuple[int, str], dict[str, str]] = {}

    for source_row in rows:
        context_id = source_row["コンテキストID"]
        segment = segment_member(context_id, company_id)
        fiscal_year = fiscal_year_from_context(context_id, latest_year)
        if segment is None or fiscal_year is None:
            continue

        value = source_row["値"]
        if value in {"", "－", "-"}:
            continue

        element_id = source_row["要素ID"]
        segment_id, segment_name = segment
        record = records.setdefault(
            (fiscal_year, segment_id),
            {
                "company_id": company_id,
                "fiscal_year": str(fiscal_year),
                "segment_id": segment_id,
                "segment_name": segment_name,
                "description": "",
                "revenue": "",
                "segment_profit": "",
                "profit_measure": config["profit_measure"],
                "currency": "JPY",
                "unit": "JPY",
                "availability": "reported",
                "source_id": source_id,
                "note": "",
            },
        )

        if element_id == config["revenue_element_id"]:
            record["revenue"] = value
        elif element_id == config["profit_element_id"]:
            record["segment_profit"] = value

    count = 0
    for record in records.values():
        if not record["revenue"] and not record["segment_profit"]:
            continue
        upsert_row(
            segments_path,
            key_fields=("company_id", "fiscal_year", "segment_id"),
            fieldnames=SEGMENT_FIELDS,
            row=record,
        )
        count += 1

    return count


def normalize_recruit_segments(
    *,
    company_id: str,
    filing_dir: Path,
    latest_period_end: str,
    source_id: str,
    segments_path: Path,
) -> int:
    return normalize_segments(
        company_id=company_id,
        filing_dir=filing_dir,
        latest_period_end=latest_period_end,
        source_id=source_id,
        segments_path=segments_path,
    )

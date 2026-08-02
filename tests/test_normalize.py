import csv
from decimal import Decimal

from it_recruit_data.normalize import (
    decimal_text,
    fiscal_year_from_context,
    is_metric_context,
    normalize_metrics,
    segment_member,
)


def test_fiscal_year_from_context() -> None:
    assert fiscal_year_from_context("CurrentYearDuration", 2026) == 2026
    assert fiscal_year_from_context("Prior4YearInstant", 2026) == 2022
    assert (
        fiscal_year_from_context(
            "CurrentYearInstant_NonConsolidatedMember",
            2026,
        )
        == 2026
    )
    assert (
        fiscal_year_from_context(
            "Prior1YearDuration_"
            "jpcrp030000-asr_E07801-000HRTechnologyReportableSegmentMember",
            2026,
        )
        == 2025
    )


def test_decimal_text() -> None:
    assert decimal_text(Decimal("56.800")) == "56.8"
    assert decimal_text(Decimal("-49742000000")) == "-49742000000"
    assert decimal_text(Decimal("3697351000000")) == "3697351000000"


def test_is_metric_context() -> None:
    assert is_metric_context("CurrentYearDuration", "consolidated")
    assert not is_metric_context(
        "CurrentYearDuration_HRTechnologyReportableSegmentMember",
        "consolidated",
    )
    assert is_metric_context(
        "CurrentYearInstant_NonConsolidatedMember",
        "non_consolidated",
    )
    assert not is_metric_context(
        "CurrentYearInstant",
        "non_consolidated",
    )


def test_segment_member() -> None:
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E07801-000HRTechnologyReportableSegmentMember"
    ) == ("hr-technology", "HRテクノロジー事業")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E05000-000MediaBusinessReportableSegmentMember",
        "ly-corporation",
    ) == ("media", "メディア事業")
    assert segment_member("CurrentYearDuration", "unknown") is None
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E05072-000GameBusinessReportableSegmentsMember",
        "cyberagent",
    ) == ("game", "ゲーム事業")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E04830-000ITPlatformReportableSegmentMember",
        "scsk",
    ) == ("it-platform", "ITプラットフォーム")
    assert segment_member(
        "Prior1YearDuration_"
        "jpcrp030000-asr_E07801-000MatchingAndSolutionsReportableSegmentMember",
        "recruit-holdings",
    ) == (
        "marketing-matching-technologies",
        "マーケティング・マッチング・テクノロジー事業",
    )
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E05041-000InternetInfrastructureReportableSegmentMember",
        "gmo-internet",
    ) == ("internet-infrastructure", "インターネットインフラ事業")
    assert segment_member(
        "Prior1YearDuration_"
        "jpcrp030000-asr_E05041-000IncubationReportableSegmentMember",
        "gmo-internet",
    ) == ("incubation", "インキュベーション事業")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E02166-000AutomobileBusinessReportableSegmentMember",
        "honda-motor",
    ) == ("automobile", "四輪事業")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E02142-000SalesFinancingReportableSegmentMember",
        "nissan-motor",
    ) == ("sales-financing", "販売金融事業")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E02152-000AutomobilesReportableSegmentMember",
        "subaru",
    ) == ("automobiles", "自動車事業")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E02143-000AutomobileMember",
        "isuzu-motors",
    ) == ("automobile", "自動車事業")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E02168-000LandmobilityReportableSegmentMember",
        "yamaha-motor",
    ) == ("land-mobility", "ランドモビリティ")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E05350-000TabelogReportableSegmentsMember",
        "kakaku-com",
    ) == ("tabelog", "食べログ事業")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E22012-000InvestmentReportableSegmentsMember",
        "gree",
    ) == ("investment", "投資事業")
    assert segment_member(
        "CurrentYearDuration_ReportableSegmentsMember",
        "gmo-internet",
    ) is None
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E02126-000EnergySystemsReportableSegmentMember",
        "mitsubishi-heavy-industries",
    ) == ("energy", "エナジー")
    assert segment_member(
        "Prior1YearDuration_"
        "jpcrp030000-asr_E02127-000PowersportsAndEngineReportableSegmentMember",
        "kawasaki-heavy-industries",
    ) == ("powersports-and-engine", "パワースポーツ＆エンジン")
    assert segment_member(
        "CurrentYearDuration_"
        "jpcrp030000-asr_E02128-000AeroEngineSpaceAndDefenseMember",
        "ihi",
    ) == ("aero-engine-space-and-defense", "航空・宇宙・防衛")


def test_normalize_business_profit_alias(tmp_path) -> None:
    # 事業利益は提出会社ごとに異なる拡張要素で開示されるため、
    # ローカル名のエイリアスで business_profit へ集約する
    csv_dir = tmp_path / "XBRL_TO_CSV"
    csv_dir.mkdir()
    source_path = csv_dir / "jpcrp030000-asr-test.csv"
    rows = [
        [
            "jpcrp030000-asr_E02126-000:"
            "ProfitFromBusinessActivitiesSummaryOfBusinessResults",
            "Prior1YearDuration",
            "354965000000",
        ],
        [
            "jpcrp030000-asr_E02126-000:ProfitLossFromBusinessActivitiesIFRS",
            "CurrentYearDuration",
            "432218000000",
        ],
        [
            "jpcrp030000-asr_E02126-000:ProfitLossFromBusinessActivitiesIFRS",
            "CurrentYearDuration_ReconcilingItemsMember",
            "-76921000000",
        ],
    ]
    source_path.write_text(
        "要素ID\tコンテキストID\t値\n"
        + "\n".join("\t".join(row) for row in rows)
        + "\n",
        encoding="utf-16",
    )

    metrics_path = tmp_path / "metrics.csv"
    normalize_metrics(
        company_id="mitsubishi-heavy-industries",
        filing_dir=tmp_path,
        latest_period_end="2026-03-31",
        source_id="edinet-test",
        metrics_path=metrics_path,
    )

    with metrics_path.open(encoding="utf-8", newline="") as file:
        normalized = list(csv.DictReader(file))

    assert {row["metric_key"] for row in normalized} == {"business_profit"}
    assert {
        (row["fiscal_year"], row["value"]) for row in normalized
    } == {("2025", "354965000000"), ("2026", "432218000000")}


def test_normalize_quick_assets(tmp_path) -> None:
    csv_dir = tmp_path / "XBRL_TO_CSV"
    csv_dir.mkdir()
    source_path = csv_dir / "jpcrp030000-asr-test.csv"
    rows = [
        [
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "CurrentYearInstant",
            "100",
        ],
        [
            "jpigp_cor:TradeAndOtherReceivablesCAIFRS",
            "CurrentYearInstant",
            "30",
        ],
        [
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
            "CurrentYearInstant",
            "20",
        ],
    ]
    source_path.write_text(
        "要素ID\tコンテキストID\t値\n"
        + "\n".join("\t".join(row) for row in rows)
        + "\n",
        encoding="utf-16",
    )

    metrics_path = tmp_path / "metrics.csv"
    count = normalize_metrics(
        company_id="kakaku-com",
        filing_dir=tmp_path,
        latest_period_end="2026-03-31",
        source_id="edinet-test",
        metrics_path=metrics_path,
    )

    with metrics_path.open(encoding="utf-8", newline="") as file:
        normalized = list(csv.DictReader(file))

    assert count == 1
    assert normalized[0]["metric_key"] == "quick_assets"
    assert normalized[0]["value"] == "150"

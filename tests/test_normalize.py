from decimal import Decimal

from it_recruit_data.normalize import (
    decimal_text,
    fiscal_year_from_context,
    is_metric_context,
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

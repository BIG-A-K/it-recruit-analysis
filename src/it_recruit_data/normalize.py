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


@dataclass(frozen=True)
class QuickAssetRule:
    element_ids: tuple[str, ...]
    accounting_standard: str


JGAAP_COMPANY_IDS = frozenset(
    {
        "cyberagent",
        "tis",
        "mixi",
        "gree",
        "obic",
        "nintendo",
        "takara-tomy",
        "bandai-namco",
        "capcom",
        "square-enix",
        "sega-sammy",
        "koei-tecmo",
        "nissan-motor",
        "mitsubishi-motors",
        "keyence",
        "rohm",
        "tokyo-seimitsu",
        "screen-holdings",
        "taiyo-yuden",
        "tokyo-electron",
        "disco",
        "lasertec",
        "shin-etsu-chemical",
        "sumco",
        "stella-chemifa",
        "fixstars",
        "sumitomo-heavy-industries",
        "mitsui-e-and-s",
        "kanadevia",
        "toto",
    }
)


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
        "employee_count",
        "jpcrp_cor:NumberOfEmployees",
        "consolidated",
        "",
        "persons",
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
    # 事業利益はIFRS任意表示利益で、EDINETの共通タクソノミに要素がなく提出会社の
    # 拡張要素で開示される。要素IDが会社ごとに異なるため、
    # METRIC_LOCAL_NAME_ALIASESでこの内部IDへ寄せて1つの指標へ集約する。
    MetricRule(
        "business_profit",
        "it_recruit:BusinessProfitLossIFRS",
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
        "current_assets",
        "jppfs_cor:CurrentAssets",
        "consolidated",
        "",
        "JPY",
    ),
    MetricRule(
        "current_liabilities",
        "jppfs_cor:CurrentLiabilities",
        "consolidated",
        "",
        "JPY",
    ),
    MetricRule(
        "current_assets",
        "jpigp_cor:CurrentAssetsIFRS",
        "consolidated",
        "IFRS",
        "JPY",
    ),
    MetricRule(
        "current_liabilities",
        "jpigp_cor:TotalCurrentLiabilitiesIFRS",
        "consolidated",
        "IFRS",
        "JPY",
    ),
    MetricRule(
        "revenue",
        "jpcrp_cor:NetSalesSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=JGAAP_COMPANY_IDS,
    ),
    MetricRule(
        "operating_profit",
        "jppfs_cor:OperatingIncome",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=JGAAP_COMPANY_IDS,
    ),
    MetricRule(
        "operating_cf",
        "jpcrp_cor:NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=JGAAP_COMPANY_IDS,
    ),
    MetricRule(
        "investing_cf",
        "jpcrp_cor:NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=JGAAP_COMPANY_IDS,
    ),
    MetricRule(
        "financing_cf",
        "jpcrp_cor:NetCashProvidedByUsedInFinancingActivitiesSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "JPY",
        company_ids=JGAAP_COMPANY_IDS,
    ),
    MetricRule(
        "equity_ratio",
        "jpcrp_cor:EquityToAssetRatioSummaryOfBusinessResults",
        "consolidated",
        "JGAAP",
        "percent",
        Decimal("100"),
        JGAAP_COMPANY_IDS,
    ),
)

METRIC_LOCAL_NAME_ALIASES = {
    "OperatingProfitLossIFRSSummaryOfBusinessResults": (
        "jpigp_cor:OperatingProfitLossIFRS"
    ),
    "OperatingProfitLossIFRSKeyFinancialData": (
        "jpigp_cor:OperatingProfitLossIFRS"
    ),
    "NetSalesIFRSKeyFinancialData": (
        "jpcrp_cor:RevenueIFRSSummaryOfBusinessResults"
    ),
    "NetSalesIFRSSummaryOfBusinessResults": (
        "jpcrp_cor:RevenueIFRSSummaryOfBusinessResults"
    ),
    "SalesAndFinancialServicesRevenueIFRSKeyFinancialData": (
        "jpcrp_cor:RevenueIFRSSummaryOfBusinessResults"
    ),
    "OperatingRevenuesIFRSKeyFinancialData": (
        "jpcrp_cor:RevenueIFRSSummaryOfBusinessResults"
    ),
    "NumberOfEmployeesIFRSSummaryOfBusinessResults": (
        "jpcrp_cor:NumberOfEmployees"
    ),
    "NumberOfEmployeesIFRS": "jpcrp_cor:NumberOfEmployees",
    "BusinessProfitLossIFRS": "it_recruit:BusinessProfitLossIFRS",
    "BusinessProfitIFRSKeyFinancialData": (
        "it_recruit:BusinessProfitLossIFRS"
    ),
    "ProfitLossFromBusinessActivitiesIFRS": (
        "it_recruit:BusinessProfitLossIFRS"
    ),
    "ProfitFromBusinessActivitiesSummaryOfBusinessResults": (
        "it_recruit:BusinessProfitLossIFRS"
    ),
}


QUICK_ASSET_RULES = {
    "honda-motor": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
    ),
    "nissan-motor": QuickAssetRule(
        (
            "jppfs_cor:CashAndDeposits",
            "jppfs_cor:NotesAndAccountsReceivableTradeAndContractAssets",
            "jppfs_cor:ShortTermInvestmentSecurities",
        ),
        "JGAAP",
    ),
    "subaru": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:TradeAndOtherReceivablesCAIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
    ),
    "mitsubishi-motors": QuickAssetRule(
        (
            "jppfs_cor:CashAndDeposits",
            "jppfs_cor:NotesAndAccountsReceivableTradeAndContractAssets",
        ),
        "JGAAP",
    ),
    "isuzu-motors": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:TradeAndOtherReceivablesCAIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
    ),
    "yamaha-motor": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:TradeAndOtherReceivablesCAIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
    ),
    "dena": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:TradeAndOtherReceivables3CAIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
    ),
    "kakaku-com": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:TradeAndOtherReceivablesCAIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
    ),
    "mixi": QuickAssetRule(
        (
            "jppfs_cor:CashAndDeposits",
            "jppfs_cor:NotesAndAccountsReceivableTrade",
            "jppfs_cor:OperationalInvestmentSecuritiesCA",
            "jppfs_cor:ShortTermInvestmentSecurities",
        ),
        "JGAAP",
    ),
    "mitsubishi-heavy-industries": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:TradeAndOtherReceivablesCAIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
    ),
    "kawasaki-heavy-industries": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:TradeAndOtherReceivablesCAIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
    ),
    "ihi": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:TradeAndOtherReceivablesCAIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
    ),
    "sumitomo-heavy-industries": QuickAssetRule(
        (
            "jppfs_cor:CashAndDeposits",
            "jppfs_cor:NotesAndAccountsReceivableTradeAndContractAssets",
        ),
        "JGAAP",
    ),
    "mitsui-e-and-s": QuickAssetRule(
        (
            "jppfs_cor:CashAndDeposits",
            "jppfs_cor:NotesAndAccountsReceivableTradeAndContractAssets",
            "jppfs_cor:ElectronicallyRecordedMonetaryClaimsOperatingCA",
        ),
        "JGAAP",
    ),
    "kanadevia": QuickAssetRule(
        (
            "jppfs_cor:CashAndDeposits",
            "jppfs_cor:NotesAndAccountsReceivableTradeAndContractAssets",
            "jppfs_cor:ShortTermInvestmentSecurities",
        ),
        "JGAAP",
    ),
    "gree": QuickAssetRule(
        (
            "jppfs_cor:CashAndDeposits",
            "jppfs_cor:NotesAndAccountsReceivableTradeAndContractAssets",
            "jppfs_cor:OperationalInvestmentSecuritiesCA",
            "jppfs_cor:MoneyHeldInTrustCA",
            "jppfs_cor:ShortTermInvestmentSecurities",
        ),
        "JGAAP",
    ),
    "toto": QuickAssetRule(
        (
            "jppfs_cor:CashAndDeposits",
            "jppfs_cor:NotesAndAccountsReceivableTradeAndContractAssets",
        ),
        "JGAAP",
    ),
    "kyocera": QuickAssetRule(
        (
            "jpigp_cor:CashAndCashEquivalentsIFRS",
            "jpigp_cor:TradeAndOtherReceivablesCAIFRS",
            "jpigp_cor:OtherFinancialAssetsCAIFRS",
        ),
        "IFRS",
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
            "MatchingAndSolutionsReportableSegmentMember": (
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
    "kakaku-com": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "セグメント利益",
        "members": {
            "KakakuComReportableSegmentsMember": (
                "kakaku-com",
                "価格.com事業",
            ),
            "TabelogReportableSegmentsMember": ("tabelog", "食べログ事業"),
            "KyujinBoxReportableSegmentsMember": (
                "kyujin-box",
                "求人ボックス事業",
            ),
            "IncubationReportableSegmentsMember": (
                "incubation",
                "インキュベーション事業",
            ),
        },
    },
    "gree": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "GameAnimeBusinessReportableSegmentsMember": (
                "game",
                "ゲーム事業",
            ),
            "MetaverseBusinessReportableSegmentsMember": (
                "metaverse",
                "メタバース事業",
            ),
            "IPBusinessReportableSegmentsMember": ("ip", "IP事業"),
            "DXBusinessReportableSegmentsMember": ("dx", "DX事業"),
            "InvestmentReportableSegmentsMember": ("investment", "投資事業"),
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
    "gmo-internet": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpcrp030000-asr_E05041-000:SegmentIncomeLossIFRS",
        "profit_measure": "セグメント損益",
        "members": {
            "InternetInfrastructureReportableSegmentMember": (
                "internet-infrastructure",
                "インターネットインフラ事業",
            ),
            "InternetSecuritiesReportableSegmentMember": (
                "internet-securities",
                "インターネット証券事業",
            ),
            "OnlineAdvertisingAndMediaReportableSegmentMember": (
                "online-advertising-and-media",
                "インターネット広告・メディア事業",
            ),
            "InternetFinanceReportableSegmentMember": (
                "internet-finance",
                "インターネット金融事業",
            ),
            "CryptocurrencyReportableSegmentMember": (
                "cryptocurrency",
                "暗号資産事業",
            ),
            "IncubationReportableSegmentMember": (
                "incubation",
                "インキュベーション事業",
            ),
        },
    },
    "takara-tomy": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "JapanReportableSegmentsMember": ("japan", "日本"),
            "AmericaSReportableSegmentsMember": ("americas", "米州"),
            "EuropeReportableSegmentsMember": ("europe", "欧州"),
            "OceaniaReportableSegmentsMember": ("oceania", "オセアニア"),
            "AsiaReportableSegmentsMember": ("asia", "アジア"),
        },
    },
    "bandai-namco": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "ToysAndHobbyBusinessReportableSegmentsMember": (
                "toys-and-hobby",
                "トイホビー事業",
            ),
            "DigitalBusinessReportableSegmentsMember": (
                "digital",
                "デジタル事業",
            ),
            "VisualAndMusicBusinessReportableSegmentsMember": (
                "visual-and-music",
                "映像音楽事業",
            ),
            "AmusementBusinessReportableSegmentsMember": (
                "amusement",
                "アミューズメント事業",
            ),
        },
    },
    "capcom": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "DegitalContentsReportableSegmentMember": (
                "digital-contents",
                "デジタルコンテンツ事業",
            ),
            "ArcadeOperationsReportableSegmentMember": (
                "arcade-operations",
                "アミューズメント施設事業",
            ),
            "AmusementEquipmentsReportableSegmentMember": (
                "amusement-equipments",
                "アミューズメント機器事業",
            ),
        },
    },
    "konami": {
        "revenue_element_id": (
            "jpcrp030000-asr_E01956-000:"
            "NetSalesAndOperatingRevenueFromExternalCustomersIFRS"
        ),
        "profit_element_id": "jpigp_cor:SegmentProfitLossIFRS",
        "profit_measure": "セグメント利益",
        "members": {
            "DigitalEntertainmentReportableSegmentMember": (
                "digital-entertainment",
                "デジタルエンタテインメント事業",
            ),
            "ArcadeGameReportableSegmentMember": (
                "arcade-game",
                "アミューズメント事業",
            ),
            "GamingAndSystemsReportableSegmentMember": (
                "gaming-and-systems",
                "ゲーミング＆システム事業",
            ),
            "SportsReportableSegmentMember": ("sports", "スポーツ事業"),
        },
    },
    "square-enix": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "DigitalEntertainmentSegmentReportableSegmentsMember": (
                "digital-entertainment",
                "デジタルエンタテインメント事業",
            ),
            "AmusementSegmentReportableSegmentsMember": (
                "amusement",
                "アミューズメント事業",
            ),
            "PublicationSegmentReportableSegmentsMember": (
                "publication",
                "出版事業",
            ),
            "MerchandisingSegmentReportableSegmentsMember": (
                "merchandising",
                "ライツ・プロパティ等事業",
            ),
        },
    },
    "sega-sammy": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OrdinaryIncome",
        "profit_measure": "経常利益",
        "members": {
            "EntertainmentContentsBusinessReportableSegmentsMember": (
                "entertainment-contents",
                "エンタテインメントコンテンツ事業",
            ),
            "PachislotAndPachinkoMachinesReportableSegmentsMember": (
                "pachislot-pachinko-machines",
                "遊技機事業",
            ),
            "GamingBusinessReportableSegmentMember": (
                "gaming",
                "ゲーミング事業",
            ),
        },
    },
    "koei-tecmo": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "EntertainmentReportableSegmentMember": (
                "entertainment",
                "エンタテインメント事業",
            ),
            "AmusementReportableSegmentMember": (
                "amusement",
                "アミューズメント事業",
            ),
            "RealEstateReportableSegmentMember": (
                "real-estate",
                "不動産事業・その他",
            ),
        },
    },
    "sony-group": {
        "revenue_element_id": "jpcrp030000-asr_E01777-000:SalesAndFinancialServicesRevenueToCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "GameAndNetworkServicesReportableSegmentMember": (
                "game-and-network-services",
                "ゲーム&ネットワークサービス",
            ),
            "MusicReportableSegmentMember": (
                "music",
                "ミュージック",
            ),
            "PicturesReportableSegmentMember": (
                "pictures",
                "ピクチャーズ",
            ),
            "EntertainmentTechnologyAndServicesReportableSegmentMember": (
                "entertainment-technology-and-services",
                "エンタテインメント・テクノロジー・サービス",
            ),
            "ImagingAndSensingSolutionsReportableSegmentMember": (
                "imaging-and-sensing-solutions",
                "イメージング&センシング・ソリューションズ",
            ),
            "FinancialServicesReportableSegmentMember": (
                "financial-services",
                "フィナンシャル・サービス",
            ),
        },
    },
    "panasonic-holdings": {
        "revenue_element_id": "jpigp_cor:SalesToExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "AutomotiveReportableSegmentMember": (
                "automotive",
                "オートモーティブ",
            ),
            "ConnectReportableSegmentMember": (
                "connect",
                "コネクト",
            ),
            "EnergyReportableSegmentMember": (
                "energy",
                "エナジー",
            ),
            "IndustryReportableSegmentMember": (
                "industry",
                "インダストリー",
            ),
            "LifestyleReportableSegmentMember": (
                "lifestyle",
                "ライフスタイル",
            ),
        },
    },
    "renesas-electronics": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "AutomotiveReportableSegmentMember": (
                "automotive",
                "オートモーティブ",
            ),
            "IndustrialInfrastructureIoTReportableSegmentMember": (
                "industrial-infrastructure-iot",
                "インダストリアル・インフラ・IoT",
            ),
        },
    },
    "mitsubishi-heavy-industries": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": (
            "jpcrp030000-asr_E02126-000:ProfitLossFromBusinessActivitiesIFRS"
        ),
        "profit_measure": "事業利益",
        "members": {
            "EnergySystemsReportableSegmentMember": (
                "energy",
                "エナジー",
            ),
            "PlantsAndInfrastructureSystemsReportableSegmentMember": (
                "plants-and-infrastructure",
                "プラント・インフラ",
            ),
            "LogisticsThermalAndDriveSystemsReportableSegmentMember": (
                "logistics-thermal-and-drive",
                "物流・冷熱・ドライブシステム",
            ),
            "AircraftDefenseAndSpaceReportableSegmentMember": (
                "aircraft-defense-and-space",
                "航空・防衛・宇宙",
            ),
        },
    },
    "kawasaki-heavy-industries": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": (
            "jpcrp030000-asr_E02127-000:BusinessProfitLossIFRS"
        ),
        "profit_measure": "事業利益",
        "members": {
            "AerospaceSystemsReportableSegmentMember": (
                "aerospace-systems",
                "航空宇宙システム",
            ),
            "RollingStockReportableSegmentMember": (
                "rolling-stock",
                "車両",
            ),
            "EnergySolutionAndMarineReportableSegmentMember": (
                "energy-solution-and-marine",
                "エネルギーソリューション＆マリン",
            ),
            "PrecisionMachineryAndRobotReportableSegmentMember": (
                "precision-machinery-and-robot",
                "精密機械・ロボット",
            ),
            "PowersportsAndEngineReportableSegmentMember": (
                "powersports-and-engine",
                "パワースポーツ＆エンジン",
            ),
        },
    },
    "ihi": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "ResourcesEnergyAndEnvironmentMember": (
                "resources-energy-and-environment",
                "資源・エネルギー・環境",
            ),
            "SocialInfrastructureMember": (
                "social-infrastructure",
                "社会基盤",
            ),
            "IndustrialSystemAndGeneralPurposeMachineryMember": (
                "industrial-system-and-general-purpose-machinery",
                "産業システム・汎用機械",
            ),
            "AeroEngineSpaceAndDefenseMember": (
                "aero-engine-space-and-defense",
                "航空・宇宙・防衛",
            ),
        },
    },
    "sumitomo-heavy-industries": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "MechatronicsReportableSegmentMember": (
                "mechatronics",
                "メカトロニクス",
            ),
            "IndustrialMachineryReportableSegmentMember": (
                "industrial-machinery",
                "インダストリアル マシナリー",
            ),
            "LogisticsAndConstructionReportableSegmentMember": (
                "logistics-and-construction",
                "ロジスティックス＆コンストラクション",
            ),
            "EnergyAndLifelineReportableSegmentMember": (
                "energy-and-lifeline",
                "エネルギー＆ライフライン",
            ),
        },
    },
    "mitsui-e-and-s": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "NewBusinessDevelopmentReportableSegmentsMember": (
                "new-business-development",
                "成長事業推進",
            ),
            "MarinePropulsionSystemsReportableSegmentsMember": (
                "marine-propulsion-systems",
                "舶用推進システム",
            ),
            "LogisticsSystemsReportableSegmentsMember": (
                "logistics-systems",
                "物流システム",
            ),
            "PeripheralBusinessesReportableSegmentsMember": (
                "peripheral-businesses",
                "周辺サービス",
            ),
        },
    },
    "kanadevia": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "EnvironmentalSystemsReportableSegmentsMember": (
                "environment",
                "環境",
            ),
            "MachineryReportableSegmentsMember": (
                "machinery-and-infrastructure",
                "機械・インフラ",
            ),
            # 脱炭素化セグメントの拡張要素名がElementMemberのみで一般名詞と
            # 衝突しやすいため、提出者プレフィックス付きで一致させる
            "E02124-000ElementMember": (
                "decarbonization",
                "脱炭素化",
            ),
        },
    },
    "toyota-motor": {
        "revenue_element_id": "jpcrp030000-asr_E02144-000:OperatingRevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "AutomotiveReportableSegmentMember": (
                "automotive",
                "自動車",
            ),
            "FinancialServicesReportableSegmentMember": (
                "financial-services",
                "金融",
            ),
        },
    },
    "honda-motor": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "MotorcycleBusinessReportableSegmentMember": (
                "motorcycle",
                "二輪事業",
            ),
            "AutomobileBusinessReportableSegmentMember": (
                "automobile",
                "四輪事業",
            ),
            "FinancialServicesBusinessReportableSegmentMember": (
                "financial-services",
                "金融サービス事業",
            ),
            "PowerProductAndOtherBusinessesReportableSegmentMember": (
                "power-products-and-other",
                "パワープロダクツ・その他事業",
            ),
        },
    },
    "nissan-motor": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "AutomobileReportableSegmentMember": (
                "automobile",
                "自動車事業",
            ),
            "SalesFinancingReportableSegmentMember": (
                "sales-financing",
                "販売金融事業",
            ),
        },
    },
    "subaru": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "AutomobilesReportableSegmentMember": (
                "automobiles",
                "自動車事業",
            ),
            "AerospaceReportableSegmentMember": (
                "aerospace",
                "航空宇宙事業",
            ),
        },
    },
    "mitsubishi-motors": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "CarBusinessReportableSegmentsMember": (
                "car",
                "自動車事業",
            ),
            "FinancialBusinessReportableSegmentsMember": (
                "financial",
                "金融事業",
            ),
        },
    },
    "isuzu-motors": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "AutomobileMember": (
                "automobile",
                "自動車事業",
            ),
            "FinancialServicesMember": (
                "financial-services",
                "金融サービス事業",
            ),
        },
    },
    "yamaha-motor": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:SegmentProfitLossIFRS",
        "profit_measure": "セグメント利益",
        "members": {
            "LandmobilityReportableSegmentMember": (
                "land-mobility",
                "ランドモビリティ",
            ),
            "MarineProductsReportableSegmentsMember": (
                "marine-products",
                "マリン",
            ),
            "OutdoorLandVehicleReportableSegmentMember": (
                "outdoor-land-vehicle",
                "アウトドアランドビークル",
            ),
            "RoboticsReportableSegmentMember": (
                "robotics",
                "ロボティクス",
            ),
            "FinancialServicesReportableSegmentMember": (
                "financial-services",
                "金融サービス",
            ),
        },
    },
    "rohm": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "ICsReportableSegmentMember": (
                "ics",
                "IC",
            ),
            "DiscreteSemiconductorDevicesReportableSegmentMember": (
                "discrete-semiconductor-devices",
                "個別半導体デバイス",
            ),
            "ModulesReportableSegmentMember": (
                "modules",
                "モジュール",
            ),
        },
    },
    "tokyo-seimitsu": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "MeasurementEquipmentReportableSegmentsMember": (
                "measurement-equipment",
                "精密測定器",
            ),
            "SemiconductorManufacturingDeviceReportableSegmentsMember": (
                "semiconductor-manufacturing-device",
                "半導体製造装置",
            ),
        },
    },
    "screen-holdings": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "SpeReportableSegmentsMember": (
                "spe",
                "半導体製造装置",
            ),
            "FtReportableSegmentsMember": (
                "ft",
                "微細加工テクノロジー",
            ),
            "GaReportableSegmentsMember": (
                "ga",
                "グラフィックアーツ",
            ),
            "PeReportableSegmentsMember": (
                "pe",
                "生産設備",
            ),
        },
    },
    "advantest": {
        "revenue_element_id": "jpigp_cor:SalesToExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:SegmentProfitLossIFRS",
        "profit_measure": "セグメント利益",
        "members": {
            "MechatronicsSystemBusinessReportableSegmentMember": (
                "mechatronics-system",
                "メカトロニクスシステム事業",
            ),
            "SemiconductorAndComponentTestSystemBusinessReportableSegmentMember": (
                "semiconductor-and-component-test-system",
                "半導体・部品テストシステム事業",
            ),
            "ServicesSupportAndOthersReportableSegmentMember": (
                "services-support-and-others",
                "サービス・サポート・その他",
            ),
        },
    },
    "shin-etsu-chemical": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "ElectronicsMaterialsReportableSegmentsMember": (
                "electronics-materials",
                "電子機能材料",
            ),
            "FunctionalMaterialsReportableSegmentsMember": (
                "functional-materials",
                "機能化学品",
            ),
            "InfrastructureMaterialsReportableSegmentsMember": (
                "infrastructure-materials",
                "基礎素材",
            ),
            "DiversifiedBusinessReportableSegmentsMember": (
                "diversified-business",
                "加工・その他",
            ),
        },
    },
    "stella-chemifa": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "HighPurityChemicalReportableSegmentsMember": (
                "high-purity-chemical",
                "高純度化学",
            ),
            "TransportationReportableSegmentsMember": (
                "transportation",
                "運輸",
            ),
        },
    },
    "resonac-holdings": {
        "revenue_element_id": "jpigp_cor:RevenueFromExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:SegmentProfitLossIFRS",
        "profit_measure": "セグメント利益",
        "members": {
            "SemiconductorAndElectronicMaterialsReportableSegmentMember": (
                "semiconductor-and-electronic-materials",
                "半導体・電子材料",
            ),
            "InnovationEnablingMaterialsReportableSegmentMember": (
                "innovation-enabling-materials",
                "イノベーション・Enabling Materials",
            ),
            "MobilityReportableSegmentMember": (
                "mobility",
                "モビリティ",
            ),
            "ChemicalsReportableSegmentMember": (
                "chemicals",
                "ケミカルズ",
            ),
        },
    },
    "agc": {
        "revenue_element_id": "jpigp_cor:SalesToExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:OperatingProfitLossIFRS",
        "profit_measure": "営業利益",
        "members": {
            "GlassReportableSegmentMember": (
                "glass",
                "ガラス",
            ),
            "AutomotiveReportableSegmentMember": (
                "automotive",
                "自動車",
            ),
            "LifescienceReportableSegmentMember": (
                "lifescience",
                "ライフサイエンス",
            ),
        },
    },
    "toto": {
        "revenue_element_id": "jpcrp_cor:RevenuesFromExternalCustomers",
        "profit_element_id": "jppfs_cor:OperatingIncome",
        "profit_measure": "営業利益",
        "members": {
            "JapanHousingEquipmentBusinessReportableSegmentMember": (
                "japan-housing-equipment",
                "日本住設事業",
            ),
            "AmericasReportableSegmentMember": (
                "americas",
                "米州事業",
            ),
            "AsiaOceaniaReportableSegmentMember": (
                "asia-oceania",
                "アジア・オセアニア事業",
            ),
            "EuropeReportableSegmentMember": (
                "europe",
                "欧州事業",
            ),
            "MainlandChinaBusinessReportableSegmentMember": (
                "mainland-china",
                "中国大陸事業",
            ),
            "AdvancedCeramicsBusinessReportableSegmentMember": (
                "ceramics",
                "セラミック事業",
            ),
        },
    },
    "kyocera": {
        "revenue_element_id": "jpigp_cor:SalesToExternalCustomersIFRS",
        "profit_element_id": "jpigp_cor:SegmentProfitLossIFRS",
        "profit_measure": "事業利益",
        "members": {
            "CoreComponentsBusinessReportableSegmentMember": (
                "core-components",
                "コアコンポーネント",
            ),
            "ElectronicComponentsBusinessReportableSegmentMember": (
                "electronic-components",
                "電子部品",
            ),
            "SolutionsBusinessReportableSegmentMember": (
                "solutions",
                "ソリューション",
            ),
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

    quick_asset_rule = QUICK_ASSET_RULES.get(company_id)
    if quick_asset_rule is not None:
        component_values: dict[str, dict[str, Decimal]] = {
            element_id: {} for element_id in quick_asset_rule.element_ids
        }
        for source_row in rows:
            context_id = source_row["コンテキストID"]
            if not is_metric_context(context_id, "consolidated"):
                continue

            element_id = source_row["要素ID"]
            if element_id not in component_values:
                continue

            raw_value = source_row["値"]
            value = (
                Decimal("0")
                if raw_value in {"", "－", "-"}
                else Decimal(raw_value)
            )
            existing = component_values[element_id].get(context_id)
            if existing is not None and existing != value:
                raise RuntimeError(
                    "当座資産の算定科目で値が競合しています: "
                    f"{element_id}, {context_id}: {existing} != {value}"
                )
            component_values[element_id][context_id] = value

        contexts = set.intersection(
            *(set(values) for values in component_values.values())
        )
        quick_asset_note = "算定科目=" + "+".join(quick_asset_rule.element_ids)
        for context_id in sorted(contexts):
            fiscal_year = fiscal_year_from_context(context_id, latest_year)
            if fiscal_year is None:
                continue
            value = sum(
                (
                    component_values[element_id][context_id]
                    for element_id in quick_asset_rule.element_ids
                ),
                Decimal("0"),
            )
            record = {
                "company_id": company_id,
                "metric_key": "quick_assets",
                "fiscal_year": str(fiscal_year),
                "period_end": period_end_for_year(
                    latest_period_end,
                    fiscal_year,
                ),
                "value": decimal_text(value),
                "unit": "JPY",
                "scope": "consolidated",
                "accounting_standard": quick_asset_rule.accounting_standard,
                "availability": "reported",
                "source_id": source_id,
                "note": quick_asset_note,
            }
            records[
                (company_id, "quick_assets", fiscal_year, "consolidated")
            ] = record

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

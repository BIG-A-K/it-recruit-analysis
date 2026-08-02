from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from it_recruit_data.sec import (
    SecError,
    find_xbrl_instance_name,
    load_cached_filing,
    normalize_cik,
)
from it_recruit_data.store import METRIC_FIELDS, SEGMENT_FIELDS, upsert_rows

XBRLI_NAMESPACE = "http://www.xbrl.org/2003/instance"
XBRLDI_NAMESPACE = "http://xbrl.org/2006/xbrldi"
XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
US_GAAP_NAMESPACE_PREFIX = "http://fasb.org/us-gaap/"
AMAZON_CIK = "0001018724"


@dataclass(frozen=True)
class CompanyFactRule:
    metric_key: str
    taxonomy: str
    concepts: tuple[str, ...]
    units: tuple[str, ...]
    duration: bool
    output_unit: str


COMPANY_FACT_RULES = (
    CompanyFactRule(
        "revenue",
        "us-gaap",
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
        ("USD",),
        True,
        "USD",
    ),
    CompanyFactRule(
        "operating_profit",
        "us-gaap",
        ("OperatingIncomeLoss",),
        ("USD",),
        True,
        "USD",
    ),
    CompanyFactRule(
        "operating_cf",
        "us-gaap",
        ("NetCashProvidedByUsedInOperatingActivities",),
        ("USD",),
        True,
        "USD",
    ),
    CompanyFactRule(
        "investing_cf",
        "us-gaap",
        ("NetCashProvidedByUsedInInvestingActivities",),
        ("USD",),
        True,
        "USD",
    ),
    CompanyFactRule(
        "financing_cf",
        "us-gaap",
        ("NetCashProvidedByUsedInFinancingActivities",),
        ("USD",),
        True,
        "USD",
    ),
    CompanyFactRule(
        "current_assets",
        "us-gaap",
        ("AssetsCurrent",),
        ("USD",),
        False,
        "USD",
    ),
    CompanyFactRule(
        "current_liabilities",
        "us-gaap",
        ("LiabilitiesCurrent",),
        ("USD",),
        False,
        "USD",
    ),
    CompanyFactRule(
        "employee_count",
        "dei",
        ("EntityNumberOfEmployees",),
        ("employees", "pure"),
        False,
        "persons",
    ),
)


@dataclass(frozen=True)
class XbrlDimension:
    axis: str
    member: str


@dataclass(frozen=True)
class XbrlContext:
    context_id: str
    entity_identifier: str
    start_date: str
    end_date: str
    instant: str
    dimensions: tuple[XbrlDimension, ...]


@dataclass(frozen=True)
class XbrlUnit:
    unit_id: str
    measures: tuple[str, ...]


@dataclass(frozen=True)
class XbrlFact:
    concept: str
    context_ref: str
    unit_ref: str
    value: Decimal


@dataclass(frozen=True)
class XbrlInstance:
    contexts: dict[str, XbrlContext]
    units: dict[str, XbrlUnit]
    facts: tuple[XbrlFact, ...]
    namespaces: dict[str, str]


def _local_name(qname: str) -> str:
    if qname.startswith("{"):
        return qname.rsplit("}", 1)[-1]
    return qname.rsplit(":", 1)[-1]


def _namespace(qname: str) -> str:
    if qname.startswith("{"):
        return qname[1:].split("}", 1)[0]
    return ""


def _expand_qname(value: str, namespaces: dict[str, str]) -> str:
    if value.startswith("{"):
        return value
    if ":" in value:
        prefix, local = value.split(":", 1)
        namespace = namespaces.get(prefix)
        if namespace is None:
            raise SecError(f"XBRL QName uses an undeclared prefix: {value}")
        return f"{{{namespace}}}{local}"
    namespace = namespaces.get("")
    return f"{{{namespace}}}{value}" if namespace else value


def format_qname(qname: str, namespaces: dict[str, str]) -> str:
    namespace = _namespace(qname)
    local = _local_name(qname)
    for prefix, uri in namespaces.items():
        if uri == namespace:
            return f"{prefix}:{local}" if prefix else local
    return qname


def read_xbrl_instance(path: Path) -> XbrlInstance:
    raw = path.read_bytes()
    upper_xml = raw.upper()
    if b"<!DOCTYPE" in upper_xml or b"<!ENTITY" in upper_xml:
        raise SecError(f"XBRL instance contains a forbidden DTD or entity: {path}")

    namespaces: dict[str, str] = {}
    for _, namespace in ElementTree.iterparse(
        io.BytesIO(raw), events=("start-ns",)
    ):
        prefix, uri = namespace
        namespaces.setdefault(prefix, uri)
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        raise SecError(f"Invalid XBRL instance XML: {path}") from error

    contexts: dict[str, XbrlContext] = {}
    for element in root.findall(f".//{{{XBRLI_NAMESPACE}}}context"):
        context_id = element.get("id", "")
        if not context_id:
            raise SecError("XBRL context has no id")
        start = element.findtext(f".//{{{XBRLI_NAMESPACE}}}startDate", "")
        end = element.findtext(f".//{{{XBRLI_NAMESPACE}}}endDate", "")
        instant = element.findtext(f".//{{{XBRLI_NAMESPACE}}}instant", "")
        identifier = element.findtext(
            f"./{{{XBRLI_NAMESPACE}}}entity/{{{XBRLI_NAMESPACE}}}identifier",
            "",
        ).strip()
        dimensions: list[XbrlDimension] = []
        for member in element.findall(f".//{{{XBRLDI_NAMESPACE}}}explicitMember"):
            axis = member.get("dimension", "")
            member_value = (member.text or "").strip()
            if not axis or not member_value:
                raise SecError(f"XBRL context {context_id} has an invalid explicit member")
            dimensions.append(
                XbrlDimension(
                    axis=_expand_qname(axis, namespaces),
                    member=_expand_qname(member_value, namespaces),
                )
            )
        contexts[context_id] = XbrlContext(
            context_id=context_id,
            entity_identifier=identifier,
            start_date=start,
            end_date=end,
            instant=instant,
            dimensions=tuple(dimensions),
        )

    units: dict[str, XbrlUnit] = {}
    for element in root.findall(f".//{{{XBRLI_NAMESPACE}}}unit"):
        unit_id = element.get("id", "")
        if not unit_id:
            raise SecError("XBRL unit has no id")
        measures = tuple(
            _expand_qname((measure.text or "").strip(), namespaces)
            for measure in element.findall(f".//{{{XBRLI_NAMESPACE}}}measure")
            if (measure.text or "").strip()
        )
        units[unit_id] = XbrlUnit(unit_id=unit_id, measures=measures)

    facts: list[XbrlFact] = []
    for element in root.iter():
        context_ref = element.get("contextRef")
        if not context_ref:
            continue
        if element.get(f"{{{XSI_NAMESPACE}}}nil", "").lower() in {"true", "1"}:
            continue
        unit_ref = element.get("unitRef", "")
        raw_value = "".join(element.itertext()).strip()
        if not unit_ref or not raw_value:
            continue
        try:
            value = Decimal(raw_value.replace(",", ""))
            scale_text = element.get("scale")
            if scale_text is None:
                scale_text = next(
                    (
                        attribute
                        for name, attribute in element.attrib.items()
                        if _local_name(name) == "scale"
                    ),
                    "0",
                )
            value *= Decimal(10) ** int(scale_text)
            sign = next(
                (
                    attribute
                    for name, attribute in element.attrib.items()
                    if _local_name(name) == "sign"
                ),
                "",
            )
            if sign == "-" and value > 0:
                value = -value
        except (InvalidOperation, ValueError) as error:
            raise SecError(
                f"Invalid numeric XBRL fact {_local_name(element.tag)} in "
                f"context {context_ref}"
            ) from error
        facts.append(
            XbrlFact(
                concept=element.tag,
                context_ref=context_ref,
                unit_ref=unit_ref,
                value=value,
            )
        )
    return XbrlInstance(contexts, units, tuple(facts), namespaces)


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _is_annual_duration(start: str, end: str) -> bool:
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return False
    return 300 <= days <= 380


def select_companyfacts(
    payload: dict[str, Any],
    *,
    accession_number: str,
    form: str,
) -> list[dict[str, str]]:
    if form == "20-F":
        raise SecError(
            "Form 20-F taxonomy is unsupported; IFRS annual facts cannot yet be "
            "normalized safely"
        )
    facts_by_taxonomy = payload.get("facts") or {}
    records: dict[tuple[str, str], dict[str, str]] = {}

    for rule in COMPANY_FACT_RULES:
        taxonomy = facts_by_taxonomy.get(rule.taxonomy) or {}
        for concept in rule.concepts:
            concept_payload = taxonomy.get(concept) or {}
            units = concept_payload.get("units") or {}
            for unit_key in rule.units:
                candidates = units.get(unit_key) or []
                for fact in candidates:
                    if not isinstance(fact, dict):
                        continue
                    if fact.get("accn") != accession_number or fact.get("form") != form:
                        continue
                    if str(fact.get("fp") or "").upper() != "FY":
                        continue
                    start = str(fact.get("start") or "")
                    end = str(fact.get("end") or "")
                    if not end:
                        continue
                    if rule.duration:
                        if not start or not _is_annual_duration(start, end):
                            continue
                    elif start:
                        continue
                    try:
                        period_end = date.fromisoformat(end)
                        value = Decimal(str(fact["val"]))
                    except (InvalidOperation, KeyError, ValueError) as error:
                        raise SecError(
                            f"Invalid Company Facts value for {rule.metric_key} at {end}"
                        ) from error
                    record = {
                        "metric_key": rule.metric_key,
                        "fiscal_year": str(period_end.year),
                        "period_end": end,
                        "value": _decimal_text(value),
                        "unit": rule.output_unit,
                        "scope": "consolidated",
                        "accounting_standard": "USGAAP",
                        "availability": "reported",
                        "note": (
                            f"taxonomy={rule.taxonomy}; concept={concept}; "
                            f"accession={accession_number}; start={start}; end={end}"
                        ),
                    }
                    key = (rule.metric_key, record["fiscal_year"])
                    existing = records.get(key)
                    if existing is not None:
                        comparable = ("period_end", "value", "unit")
                        if any(existing[field] != record[field] for field in comparable):
                            raise SecError(
                                "Inconsistent canonical Company Facts candidates for "
                                f"{rule.metric_key} FY{record['fiscal_year']}: "
                                f"{existing['value']} != {record['value']}"
                            )
                        continue
                    records[key] = record
    if not records:
        raise SecError(
            f"Form {form} taxonomy is unsupported or no supported annual facts "
            f"were found for accession {accession_number}"
        )
    return [records[key] for key in sorted(records)]


def normalize_companyfacts(
    *,
    company_id: str,
    payload: dict[str, Any],
    accession_number: str,
    form: str,
    source_id: str,
    metrics_path: Path,
) -> int:
    records = select_companyfacts(
        payload,
        accession_number=accession_number,
        form=form,
    )
    output_records = [
        {"company_id": company_id, **selected, "source_id": source_id}
        for selected in records
    ]
    upsert_rows(
        metrics_path,
        key_fields=("company_id", "metric_key", "fiscal_year", "scope"),
        fieldnames=METRIC_FIELDS,
        rows=output_records,
    )
    return len(records)


AWS_MEMBER_LOCAL_NAMES = frozenset(
    {"AmazonWebServicesMember", "AmazonWebServicesSegmentMember"}
)
AWS_CONCEPTS = {
    "revenue": frozenset(
        {"RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"}
    ),
    "segment_profit": frozenset({"OperatingIncomeLoss"}),
}


def _aws_dimension(context: XbrlContext) -> XbrlDimension | None:
    if any(
        _local_name(dimension.axis) == "ProductOrServiceAxis"
        for dimension in context.dimensions
    ):
        return None
    for dimension in context.dimensions:
        if (
            _namespace(dimension.axis).startswith(US_GAAP_NAMESPACE_PREFIX)
            and _local_name(dimension.axis) == "StatementBusinessSegmentsAxis"
            and _local_name(dimension.member) in AWS_MEMBER_LOCAL_NAMES
        ):
            return dimension
    return None


def _is_usd_unit(unit: XbrlUnit | None) -> bool:
    return bool(
        unit
        and len(unit.measures) == 1
        and _local_name(unit.measures[0]).upper() == "USD"
    )


def select_aws_segments(
    instance: XbrlInstance,
    *,
    expected_cik: str | None = None,
) -> list[dict[str, str]]:
    normalized_cik = normalize_cik(expected_cik) if expected_cik is not None else None
    records: dict[str, dict[str, Any]] = {}
    for fact in instance.facts:
        if not _namespace(fact.concept).startswith(US_GAAP_NAMESPACE_PREFIX):
            continue
        field = next(
            (
                name
                for name, concepts in AWS_CONCEPTS.items()
                if _local_name(fact.concept) in concepts
            ),
            None,
        )
        if field is None or not _is_usd_unit(instance.units.get(fact.unit_ref)):
            continue
        context = instance.contexts.get(fact.context_ref)
        if context is None or not _is_annual_duration(context.start_date, context.end_date):
            continue
        dimension = _aws_dimension(context)
        if dimension is None:
            continue
        if normalized_cik is not None:
            try:
                context_cik = normalize_cik(context.entity_identifier)
            except ValueError as error:
                raise SecError(
                    f"AWS XBRL context {context.context_id} has an invalid or missing "
                    "entity identifier"
                ) from error
            if context_cik != normalized_cik:
                raise SecError(
                    f"AWS XBRL context {context.context_id} CIK does not match "
                    f"filing CIK {normalized_cik}"
                )

        record = records.setdefault(
            context.end_date,
            {
                "fiscal_year": str(date.fromisoformat(context.end_date).year),
                "segment_id": "aws",
                "segment_name": "AWS",
                "description": "",
                "revenue": "",
                "segment_profit": "",
                "profit_measure": "OperatingIncomeLoss",
                "currency": "USD",
                "unit": "USD",
                "availability": "reported",
                "details": {},
            },
        )
        value = _decimal_text(fact.value)
        existing = record[field]
        if existing and existing != value:
            raise SecError(
                f"Inconsistent AWS {field} facts for period {context.end_date}: "
                f"{existing} != {value}"
            )
        record[field] = value
        record["details"][field] = (
            f"context={context.context_id},"
            f"concept={format_qname(fact.concept, instance.namespaces)},"
            f"axis={format_qname(dimension.axis, instance.namespaces)},"
            f"member={format_qname(dimension.member, instance.namespaces)}"
        )

    if not records:
        raise SecError(
            "Required AWS annual segment facts were not found on "
            "us-gaap:StatementBusinessSegmentsAxis"
        )
    normalized: list[dict[str, str]] = []
    for period_end in sorted(records):
        record = records[period_end]
        missing = [field for field in AWS_CONCEPTS if not record[field]]
        if missing:
            raise SecError(
                f"Required AWS segment facts are missing for {period_end}: "
                + ", ".join(missing)
            )
        details = record.pop("details")
        record["note"] = (
            f"period_end={period_end}; {details['revenue']}; "
            f"{details['segment_profit']}"
        )
        normalized.append(record)
    return normalized


def normalize_aws_segments(
    *,
    company_id: str,
    instance_path: Path,
    source_id: str,
    segments_path: Path,
    expected_cik: str | None = None,
) -> int:
    records = select_aws_segments(
        read_xbrl_instance(instance_path),
        expected_cik=expected_cik,
    )
    output_records = [
        {"company_id": company_id, **selected, "source_id": source_id}
        for selected in records
    ]
    upsert_rows(
        segments_path,
        key_fields=("company_id", "fiscal_year", "segment_id"),
        fieldnames=SEGMENT_FIELDS,
        rows=output_records,
    )
    return len(records)


def normalize_sec_filing(
    *,
    company_id: str,
    filing_dir: Path,
    source_id: str,
    metrics_path: Path,
    segments_path: Path,
) -> tuple[int, int]:
    filing = load_cached_filing(filing_dir)
    companyfacts_path = filing_dir / "companyfacts.json"
    if not companyfacts_path.exists():
        raise SecError(f"Cached SEC Company Facts are missing: {companyfacts_path}")
    try:
        companyfacts = json.loads(companyfacts_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise SecError(f"Cached SEC Company Facts are invalid: {companyfacts_path}") from error
    if not isinstance(companyfacts, dict):
        raise SecError(f"Cached SEC Company Facts are invalid: {companyfacts_path}")
    filing_cik = normalize_cik(filing.cik)
    try:
        companyfacts_cik = normalize_cik(companyfacts.get("cik", ""))
    except ValueError as error:
        raise SecError("Cached SEC Company Facts CIK is missing or invalid") from error
    if companyfacts_cik != filing_cik:
        raise SecError("Cached SEC Company Facts CIK does not match the filing CIK")

    metric_records = select_companyfacts(
        payload=companyfacts,
        accession_number=filing.accession_number,
        form=filing.form,
    )

    segment_records: list[dict[str, str]] = []
    if filing_cik == AMAZON_CIK:
        index_path = filing_dir / "index.json"
        if not index_path.exists():
            raise SecError(f"Cached SEC filing index is missing: {index_path}")
        try:
            index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            raise SecError(f"Cached SEC filing index is invalid: {index_path}") from error
        instance_name = find_xbrl_instance_name(
            index_payload,
            filing.primary_document,
        )
        instance_path = filing_dir / instance_name if instance_name else None
        if instance_path is None or not instance_path.exists():
            raise SecError(
                f"Required extracted XBRL instance is missing for {filing.accession_number}"
            )
        segment_records = select_aws_segments(
            read_xbrl_instance(instance_path),
            expected_cik=filing_cik,
        )

    output_metrics = [
        {"company_id": company_id, **record, "source_id": source_id}
        for record in metric_records
    ]
    output_segments = [
        {"company_id": company_id, **record, "source_id": source_id}
        for record in segment_records
    ]
    upsert_rows(
        metrics_path,
        key_fields=("company_id", "metric_key", "fiscal_year", "scope"),
        fieldnames=METRIC_FIELDS,
        rows=output_metrics,
    )
    upsert_rows(
        segments_path,
        key_fields=("company_id", "fiscal_year", "segment_id"),
        fieldnames=SEGMENT_FIELDS,
        rows=output_segments,
    )
    return len(metric_records), len(segment_records)

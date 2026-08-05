from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

COMPANY_FIELDS = (
    "company_id",
    "display_name",
    "name_kana",
    "legal_name",
    "securities_code",
    "corporate_number",
    "website_url",
    "edinet_code",
    "sec_cik",
    "ticker",
    "exchange",
    "country_code",
    "is_active",
)

SOURCE_FIELDS = (
    "source_id",
    "source_type",
    "title",
    "url",
    "document_id",
    "published_at",
    "retrieved_at",
    "issuer",
)

METRIC_FIELDS = (
    "company_id",
    "metric_key",
    "fiscal_year",
    "period_end",
    "value",
    "unit",
    "scope",
    "accounting_standard",
    "availability",
    "source_id",
    "note",
)

SEGMENT_FIELDS = (
    "company_id",
    "fiscal_year",
    "segment_id",
    "segment_name",
    "description",
    "revenue",
    "segment_profit",
    "profit_measure",
    "currency",
    "unit",
    "availability",
    "source_id",
    "note",
)

INDUSTRY_FIELDS = (
    "industry_id",
    "name",
    "description",
    "classification_basis",
    "is_active",
)

COMPANY_INDUSTRY_FIELDS = (
    "company_id",
    "industry_id",
)

COMPANY_RELATION_FIELDS = (
    "from_company_id",
    "to_company_id",
    "relation_type",
    "valid_from",
    "valid_to",
    "source_id",
    "note",
)

COMPANY_ANNOTATION_FIELDS = (
    "annotation_id",
    "company_id",
    "section_key",
    "target_kind",
    "target_key",
    "fiscal_year",
    "text",
    "source_id",
    "updated_at",
)


@dataclass(frozen=True)
class Table:
    """data/ 配下のCSV1ファイルの定義。主キーは docs/data/schema.md と一致させる。"""

    filename: str
    fieldnames: tuple[str, ...]
    key_fields: tuple[str, ...]


# company_profiles.csv はレガシー（読み取り専用）のため登録しない
TABLES: dict[str, Table] = {
    "companies": Table("companies.csv", COMPANY_FIELDS, ("company_id",)),
    "industries": Table("industries.csv", INDUSTRY_FIELDS, ("industry_id",)),
    "company_industries": Table(
        "company_industries.csv",
        COMPANY_INDUSTRY_FIELDS,
        ("company_id", "industry_id"),
    ),
    "company_relations": Table(
        "company_relations.csv",
        COMPANY_RELATION_FIELDS,
        ("from_company_id", "to_company_id", "relation_type", "valid_from"),
    ),
    "metrics": Table(
        "metrics.csv",
        METRIC_FIELDS,
        ("company_id", "metric_key", "fiscal_year", "scope"),
    ),
    "segments": Table(
        "segments.csv",
        SEGMENT_FIELDS,
        ("company_id", "fiscal_year", "segment_id"),
    ),
    "sources": Table("sources.csv", SOURCE_FIELDS, ("source_id",)),
    "company_annotations": Table(
        "company_annotations.csv",
        COMPANY_ANNOTATION_FIELDS,
        ("annotation_id",),
    ),
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def find_company(data_dir: Path, company_id: str) -> dict[str, str]:
    companies_path = data_dir / "companies.csv"
    for row in read_rows(companies_path):
        if row["company_id"] == company_id:
            return row
    raise KeyError(f"企業IDがcompanies.csvにありません: {company_id}")


@dataclass(frozen=True)
class UpsertResult:
    added: int
    updated: int
    unchanged: int


def upsert_row(
    path: Path,
    *,
    key_fields: tuple[str, ...],
    row: dict[str, str],
    fieldnames: tuple[str, ...],
) -> UpsertResult:
    return upsert_rows(
        path,
        key_fields=key_fields,
        rows=[row],
        fieldnames=fieldnames,
    )


def upsert_rows(
    path: Path,
    *,
    key_fields: tuple[str, ...],
    rows: list[dict[str, str]],
    fieldnames: tuple[str, ...],
) -> UpsertResult:
    if not rows:
        return UpsertResult(added=0, updated=0, unchanged=0)

    existing_rows = read_rows(path) if path.exists() else []
    indexes = {
        tuple(existing[field] for field in key_fields): index
        for index, existing in enumerate(existing_rows)
    }
    added = updated = unchanged = 0
    for row in rows:
        target_key = tuple(row[field] for field in key_fields)
        index = indexes.get(target_key)
        if index is None:
            indexes[target_key] = len(existing_rows)
            existing_rows.append(row)
            added += 1
        else:
            merged = {**existing_rows[index], **row}
            if merged == existing_rows[index]:
                unchanged += 1
            else:
                existing_rows[index] = merged
                updated += 1

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as file:
            # csv の既定の終端は CRLF だが、他経路の追記は LF になり混在するとパーサが誤判定するため LF に固定する
            writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(existing_rows)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return UpsertResult(added=added, updated=updated, unchanged=unchanged)

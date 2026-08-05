from __future__ import annotations

import csv
import os
import tempfile
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


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def find_company(data_dir: Path, company_id: str) -> dict[str, str]:
    companies_path = data_dir / "companies.csv"
    for row in read_rows(companies_path):
        if row["company_id"] == company_id:
            return row
    raise KeyError(f"企業IDがcompanies.csvにありません: {company_id}")


def upsert_row(
    path: Path,
    *,
    key_fields: tuple[str, ...],
    row: dict[str, str],
    fieldnames: tuple[str, ...],
) -> None:
    upsert_rows(
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
) -> None:
    if not rows:
        return

    existing_rows = read_rows(path) if path.exists() else []
    indexes = {
        tuple(existing[field] for field in key_fields): index
        for index, existing in enumerate(existing_rows)
    }
    for row in rows:
        target_key = tuple(row[field] for field in key_fields)
        index = indexes.get(target_key)
        if index is None:
            indexes[target_key] = len(existing_rows)
            existing_rows.append(row)
        else:
            existing_rows[index] = {**existing_rows[index], **row}

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing_rows)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise

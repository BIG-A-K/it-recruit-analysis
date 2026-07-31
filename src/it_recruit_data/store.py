from __future__ import annotations

import csv
from pathlib import Path

COMPANY_FIELDS = (
    "company_id",
    "display_name",
    "legal_name",
    "securities_code",
    "corporate_number",
    "website_url",
    "edinet_code",
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
    rows = read_rows(path) if path.exists() else []
    target_key = tuple(row[field] for field in key_fields)
    updated = False

    for index, existing in enumerate(rows):
        existing_key = tuple(existing[field] for field in key_fields)
        if existing_key == target_key:
            rows[index] = {**existing, **row}
            updated = True
            break

    if not updated:
        rows.append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

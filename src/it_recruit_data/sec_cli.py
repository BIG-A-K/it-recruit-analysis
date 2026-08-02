from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from it_recruit_data.sec import (
    ANNUAL_FORMS,
    SecClient,
    SecError,
    cache_filing_package,
    normalize_cik,
    source_id_for_accession,
)
from it_recruit_data.sec_normalize import normalize_sec_filing
from it_recruit_data.store import SOURCE_FIELDS, find_company, upsert_row


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from error


def nonnegative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("interval must be a number") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("interval cannot be negative")
    return parsed


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch and normalize an annual filing from SEC EDGAR"
    )
    parser.add_argument("company_id")
    parser.add_argument("--start", required=True, type=parse_date)
    parser.add_argument("--end", required=True, type=parse_date)
    parser.add_argument("--form", required=True, choices=sorted(ANNUAL_FORMS))
    parser.add_argument(
        "--all",
        action="store_true",
        help="process every exact-form filing in the date range",
    )
    parser.add_argument("--interval", type=nonnegative_float, default=0.1)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    return parser


def _company_cik(company: dict[str, str]) -> str:
    sec_cik = company.get("sec_cik", "")
    if not sec_cik:
        raise SecError(
            "The company has no sec_cik in companies.csv; do not reuse "
            "securities_code or edinet_code"
        )
    return normalize_cik(sec_cik)


def run(args: argparse.Namespace) -> int:
    if args.start > args.end:
        raise SecError("--start must not be after --end")
    user_agent = os.environ.get("SEC_USER_AGENT", "")
    if not user_agent:
        raise SecError(
            "SEC_USER_AGENT is required and must contain an organization and "
            "a monitored contact"
        )

    company = find_company(args.data_dir, args.company_id)
    cik = _company_cik(company)
    client = SecClient(user_agent, request_interval=args.interval)
    filings, submissions, historical = client.discover_filings(
        cik,
        start=args.start,
        end=args.end,
        form=args.form,
    )
    if not filings:
        raise SecError(
            f"No exact Form {args.form} filing was found for "
            f"{company.get('legal_name') or args.company_id} in the requested range"
        )

    selected = filings if args.all else [filings[-1]]
    destinations = {
        filing.accession_number: (
            args.data_dir
            / "raw"
            / "sec"
            / cik
            / filing.accession_number
        )
        for filing in selected
    }
    needs_download = any(not destination.exists() for destination in destinations.values())
    companyfacts = client.companyfacts(cik) if needs_download else {}

    for filing in selected:
        destination = destinations[filing.accession_number]
        downloaded = cache_filing_package(
            client,
            filing,
            destination,
            submissions_payload=submissions,
            historical_submissions=historical,
            companyfacts_payload=companyfacts,
        )
        action = "download" if downloaded else "skip"
        print(f"{action} {filing.accession_number}: {filing.filing_date}")

        source_id = source_id_for_accession(filing.accession_number)
        metric_count, segment_count = normalize_sec_filing(
            company_id=args.company_id,
            filing_dir=destination,
            source_id=source_id,
            metrics_path=args.data_dir / "metrics.csv",
            segments_path=args.data_dir / "segments.csv",
        )
        upsert_row(
            args.data_dir / "sources.csv",
            key_fields=("source_id",),
            fieldnames=SOURCE_FIELDS,
            row={
                "source_id": source_id,
                "source_type": "statutory_filing",
                "title": f"Form {filing.form} annual report",
                "url": filing.detail_url,
                "document_id": filing.accession_number,
                "published_at": filing.filing_date,
                "retrieved_at": date.today().isoformat(),
                "issuer": filing.filer_name,
            },
        )
        print(
            f"normalize {filing.accession_number}: "
            f"{metric_count} metrics, {segment_count} segments"
        )
    return len(selected)


def main() -> None:
    args = create_parser().parse_args()
    try:
        run(args)
    except (KeyError, OSError, SecError, ValueError) as error:
        raise SystemExit(str(error)) from error

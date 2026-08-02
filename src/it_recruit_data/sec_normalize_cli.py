from __future__ import annotations

import argparse
from pathlib import Path

from it_recruit_data.sec import (
    SecError,
    load_cached_filing,
    normalize_accession,
    normalize_cik,
    source_id_for_accession,
)
from it_recruit_data.sec_normalize import normalize_sec_filing
from it_recruit_data.store import find_company, read_rows


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay normalization for a cached SEC EDGAR filing"
    )
    parser.add_argument("company_id")
    parser.add_argument("accession_number")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    return parser


def run(args: argparse.Namespace) -> tuple[int, int]:
    accession = normalize_accession(args.accession_number)
    company = find_company(args.data_dir, args.company_id)
    sec_cik = company.get("sec_cik", "")
    if not sec_cik:
        raise SecError(f"{args.company_id} has no sec_cik in companies.csv")
    cik = normalize_cik(sec_cik)
    filing_dir = args.data_dir / "raw" / "sec" / cik / accession
    if not filing_dir.exists():
        raise SecError(f"Cached SEC filing does not exist: {filing_dir}")

    filing = load_cached_filing(filing_dir)
    if filing.accession_number != accession or filing.cik != cik:
        raise SecError("Cached SEC filing metadata does not match the requested company/filing")
    source_id = source_id_for_accession(accession)
    sources_path = args.data_dir / "sources.csv"
    if not sources_path.exists():
        raise SecError(f"SEC source row is missing: {source_id}")
    source = next(
        (
            row
            for row in read_rows(sources_path)
            if row.get("source_id") == source_id
            and row.get("document_id") == accession
            and row.get("source_type") == "statutory_filing"
        ),
        None,
    )
    if source is None:
        raise SecError(f"SEC source row is missing or mismatched: {source_id}")

    result = normalize_sec_filing(
        company_id=args.company_id,
        filing_dir=filing_dir,
        source_id=source_id,
        metrics_path=args.data_dir / "metrics.csv",
        segments_path=args.data_dir / "segments.csv",
    )
    print(
        f"normalized {accession}: {result[0]} metrics, {result[1]} segments"
    )
    return result


def main() -> None:
    args = create_parser().parse_args()
    try:
        run(args)
    except (KeyError, OSError, SecError, ValueError) as error:
        raise SystemExit(str(error)) from error

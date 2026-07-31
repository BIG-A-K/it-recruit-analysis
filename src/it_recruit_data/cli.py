from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from it_recruit_data.edinet import EdinetClient, extract_zip_safely
from it_recruit_data.normalize import (
    normalize_metrics,
    normalize_segments,
)
from it_recruit_data.store import SOURCE_FIELDS, find_company, upsert_row


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "日付はYYYY-MM-DD形式で指定してください"
        ) from error


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="対象企業のEDINET有価証券報告書CSVを取得する"
    )
    parser.add_argument("company_id")
    parser.add_argument("--start", required=True, type=parse_date)
    parser.add_argument("--end", type=parse_date, default=date.today())
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--all",
        action="store_true",
        help="最新書類だけでなく、期間内の全書類を取得する",
    )
    parser.add_argument("--interval", type=float, default=1.0)
    return parser


def main() -> None:
    args = create_parser().parse_args()
    api_key = os.environ.get("EDINET_API", "")
    if not api_key:
        raise SystemExit(
            "EDINET_APIが未設定です。APIキーを環境変数へ設定してください。"
        )

    company = find_company(args.data_dir, args.company_id)
    client = EdinetClient(api_key, request_interval=args.interval)
    filings = client.find_annual_reports(
        company["edinet_code"],
        args.start,
        args.end,
    )
    if not filings:
        raise SystemExit(
            f"{company['legal_name']}のCSV付き有価証券報告書が見つかりませんでした"
        )

    selected = filings if args.all else [filings[-1]]
    for filing in selected:
        destination = args.data_dir / "raw" / "edinet" / filing.doc_id
        if destination.exists():
            print(f"skip {filing.doc_id}: 取得済み")
        else:
            content = client.download_csv_zip(filing.doc_id)
            extracted = extract_zip_safely(content, destination)
            print(
                f"download {filing.doc_id}: "
                f"{filing.period_end} ({len(extracted)} files)"
            )

        source_id = f"edinet-{filing.doc_id.lower()}"
        upsert_row(
            args.data_dir / "sources.csv",
            key_fields=("source_id",),
            fieldnames=SOURCE_FIELDS,
            row={
                "source_id": source_id,
                "source_type": "statutory_filing",
                "title": filing.description,
                "url": (
                    "https://api.edinet-fsa.go.jp/api/v2/documents/"
                    f"{filing.doc_id}"
                ),
                "document_id": filing.doc_id,
                "published_at": filing.submitted_at[:10],
                "retrieved_at": date.today().isoformat(),
                "issuer": filing.filer_name,
            },
        )

        metric_count = normalize_metrics(
            company_id=args.company_id,
            filing_dir=destination,
            latest_period_end=filing.period_end,
            source_id=source_id,
            metrics_path=args.data_dir / "metrics.csv",
        )
        segment_count = normalize_segments(
            company_id=args.company_id,
            filing_dir=destination,
            latest_period_end=filing.period_end,
            source_id=source_id,
            segments_path=args.data_dir / "segments.csv",
        )
        print(
            f"normalize {filing.doc_id}: "
            f"{metric_count} metrics, {segment_count} segments"
        )

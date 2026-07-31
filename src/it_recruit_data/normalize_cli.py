from __future__ import annotations

import argparse
from pathlib import Path

from it_recruit_data.normalize import (
    normalize_metrics,
    normalize_segments,
)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="取得済みEDINET CSVをサイト用CSVへ変換する"
    )
    parser.add_argument("company_id")
    parser.add_argument("doc_id")
    parser.add_argument("--period-end", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    return parser


def main() -> None:
    args = create_parser().parse_args()
    filing_dir = args.data_dir / "raw" / "edinet" / args.doc_id
    if not filing_dir.exists():
        raise SystemExit(f"取得済み書類がありません: {filing_dir}")

    source_id = f"edinet-{args.doc_id.lower()}"
    metric_count = normalize_metrics(
        company_id=args.company_id,
        filing_dir=filing_dir,
        latest_period_end=args.period_end,
        source_id=source_id,
        metrics_path=args.data_dir / "metrics.csv",
    )
    segment_count = normalize_segments(
        company_id=args.company_id,
        filing_dir=filing_dir,
        latest_period_end=args.period_end,
        source_id=source_id,
        segments_path=args.data_dir / "segments.csv",
    )

    print(
        f"normalized {args.doc_id}: "
        f"{metric_count} metrics, {segment_count} segments"
    )

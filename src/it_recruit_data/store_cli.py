"""data/ 配下のCSVへ行を安全にupsertするCLI。

AIエージェント・人間の双方が data/*.csv をテキストとして直接編集すると、
改行コード混在・列ズレ・クォート漏れの事故が起きるため、書き込みはこのCLIへ集約する。

使い方:
    uv run csv-upsert <table> [--data-dir data] < rows.jsonl

行は標準入力からJSON Lines(1行1オブジェクト)またはJSON配列で渡す。
主キーが一致する既存行は渡したフィールドだけ更新され、それ以外は追加される。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from it_recruit_data.store import TABLES, Table, read_rows, upsert_rows


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csv-upsert",
        description="標準入力のJSONL/JSON配列を検証してdata/のCSVへupsertする",
    )
    parser.add_argument("table", choices=sorted(TABLES), help="対象テーブル名")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    return parser


def parse_input(text: str) -> list[dict[str, object]]:
    text = text.strip()
    if not text:
        raise SystemExit("標準入力が空です。JSON LinesまたはJSON配列で行を渡してください")
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise SystemExit("JSON配列を渡してください")
        rows = parsed
    else:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit(f"行はJSONオブジェクトである必要があります: {row!r}")
    return rows


def coerce_value(value: object) -> str:
    """JSONの値をCSVセル表現へ変換する。既存データの表記(true/false・空欄)に合わせる。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def validate_rows(
    table_name: str,
    table: Table,
    rows: list[dict[str, object]],
    data_dir: Path,
) -> list[dict[str, str]]:
    errors: list[str] = []
    coerced_rows: list[dict[str, str]] = []
    seen_keys: dict[tuple[str, ...], int] = {}

    known_companies: set[str] | None = None
    known_sources: set[str] | None = None
    companies_path = data_dir / "companies.csv"
    sources_path = data_dir / "sources.csv"
    if table_name != "companies" and companies_path.exists():
        known_companies = {row["company_id"] for row in read_rows(companies_path)}
    if table_name != "sources" and sources_path.exists():
        known_sources = {row["source_id"] for row in read_rows(sources_path)}

    company_reference_fields = tuple(
        field
        for field in table.fieldnames
        if field in ("company_id", "from_company_id", "to_company_id")
        and table_name != "companies"
    )

    for line_number, raw_row in enumerate(rows, start=1):
        unknown = sorted(set(raw_row) - set(table.fieldnames))
        if unknown:
            errors.append(
                f"{line_number}行目: 未知のフィールド {unknown}"
                f"（{table.filename} の列: {', '.join(table.fieldnames)}）"
            )
            continue

        row = {field: coerce_value(value) for field, value in raw_row.items()}

        missing_keys = [field for field in table.key_fields if not row.get(field)]
        if missing_keys:
            errors.append(f"{line_number}行目: 主キーが空です {missing_keys}")
            continue

        key = tuple(row[field] for field in table.key_fields)
        if key in seen_keys:
            errors.append(
                f"{line_number}行目: 入力内で主キーが重複しています"
                f"（{seen_keys[key]}行目と同一: {key}）"
            )
            continue
        seen_keys[key] = line_number

        if known_companies is not None:
            for field in company_reference_fields:
                value = row.get(field, "")
                if value and value not in known_companies:
                    errors.append(
                        f"{line_number}行目: {field}={value} が companies.csv にありません"
                    )
        if known_sources is not None and row.get("source_id"):
            if row["source_id"] not in known_sources:
                errors.append(
                    f"{line_number}行目: source_id={row['source_id']} が"
                    " sources.csv にありません。先に sources へ登録してください"
                )

        coerced_rows.append(row)

    if errors:
        for error in errors:
            print(f"エラー: {error}", file=sys.stderr)
        raise SystemExit(1)
    return coerced_rows


def main() -> None:
    args = create_parser().parse_args()
    table = TABLES[args.table]
    rows = validate_rows(
        args.table,
        table,
        parse_input(sys.stdin.read()),
        args.data_dir,
    )
    result = upsert_rows(
        args.data_dir / table.filename,
        key_fields=table.key_fields,
        rows=rows,
        fieldnames=table.fieldnames,
    )
    print(
        f"{table.filename}: {result.added} added, "
        f"{result.updated} updated, {result.unchanged} unchanged"
    )

import io
import json
from pathlib import Path

import pytest

from it_recruit_data.store import (
    COMPANY_FIELDS,
    SOURCE_FIELDS,
    TABLES,
    upsert_row,
)
from it_recruit_data.store_cli import create_parser, main, parse_input


def run_cli(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    stdin_text: str,
) -> None:
    monkeypatch.setattr("sys.argv", ["csv-upsert", *argv])
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    main()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """companies.csv と sources.csv に参照先の最小データを用意する。"""
    upsert_row(
        tmp_path / "companies.csv",
        key_fields=("company_id",),
        fieldnames=COMPANY_FIELDS,
        row={"company_id": "example", "display_name": "Example", "is_active": "true"},
    )
    upsert_row(
        tmp_path / "sources.csv",
        key_fields=("source_id",),
        fieldnames=SOURCE_FIELDS,
        row={"source_id": "edinet-s100test", "source_type": "edinet"},
    )
    return tmp_path


def read_metric_rows(data_dir: Path) -> list[dict[str, str]]:
    import csv

    with (data_dir / "metrics.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def metric_row(**overrides: str) -> str:
    row = {
        "company_id": "example",
        "metric_key": "revenue",
        "fiscal_year": "2026",
        "period_end": "2026-03-31",
        "value": "1000",
        "unit": "JPY",
        "scope": "consolidated",
        "accounting_standard": "IFRS",
        "availability": "reported",
        "source_id": "edinet-s100test",
    }
    row.update(overrides)
    return json.dumps(row, ensure_ascii=False)


def test_upsert_adds_and_updates(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_cli(monkeypatch, ["metrics", "--data-dir", str(data_dir)], metric_row())
    assert "1 added, 0 updated" in capsys.readouterr().out

    # 主キーが同じ行は追加ではなく更新される
    run_cli(
        monkeypatch,
        ["metrics", "--data-dir", str(data_dir)],
        metric_row(value="2000"),
    )
    assert "0 added, 1 updated" in capsys.readouterr().out

    rows = read_metric_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["value"] == "2000"

    # 同一内容の再実行は unchanged と報告される（冪等）
    run_cli(
        monkeypatch,
        ["metrics", "--data-dir", str(data_dir)],
        metric_row(value="2000"),
    )
    assert "0 added, 0 updated, 1 unchanged" in capsys.readouterr().out


def test_partial_update_keeps_other_fields(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
) -> None:
    run_cli(monkeypatch, ["metrics", "--data-dir", str(data_dir)], metric_row())
    partial = json.dumps(
        {
            "company_id": "example",
            "metric_key": "revenue",
            "fiscal_year": "2026",
            "scope": "consolidated",
            "note": "追記",
        },
        ensure_ascii=False,
    )
    run_cli(monkeypatch, ["metrics", "--data-dir", str(data_dir)], partial)
    rows = read_metric_rows(data_dir)
    assert rows[0]["value"] == "1000"
    assert rows[0]["note"] == "追記"


def test_json_array_input(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    body = f"[{metric_row()}, {metric_row(metric_key='operating_profit')}]"
    run_cli(monkeypatch, ["metrics", "--data-dir", str(data_dir)], body)
    assert "2 added" in capsys.readouterr().out


def test_unknown_field_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        run_cli(
            monkeypatch,
            ["metrics", "--data-dir", str(data_dir)],
            metric_row(typo_field="x"),
        )
    assert "未知のフィールド" in capsys.readouterr().err
    assert not (data_dir / "metrics.csv").exists()


def test_missing_key_field_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        run_cli(
            monkeypatch,
            ["metrics", "--data-dir", str(data_dir)],
            metric_row(scope=""),
        )
    assert "主キーが空です" in capsys.readouterr().err


def test_unknown_company_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        run_cli(
            monkeypatch,
            ["metrics", "--data-dir", str(data_dir)],
            metric_row(company_id="ghost"),
        )
    assert "companies.csv にありません" in capsys.readouterr().err


def test_unknown_source_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        run_cli(
            monkeypatch,
            ["metrics", "--data-dir", str(data_dir)],
            metric_row(source_id="edinet-unknown"),
        )
    assert "sources.csv にありません" in capsys.readouterr().err


def test_duplicate_key_in_input_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    body = "\n".join([metric_row(value="1"), metric_row(value="2")])
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, ["metrics", "--data-dir", str(data_dir)], body)
    assert "主キーが重複" in capsys.readouterr().err


def test_value_coercion(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    # JSONの数値・真偽値・nullは既存CSVの表記へ変換される
    row = json.dumps(
        {
            "company_id": "example2",
            "display_name": "Example2",
            "is_active": True,
            "securities_code": 1234,
            "corporate_number": None,
        }
    )
    run_cli(monkeypatch, ["companies", "--data-dir", str(data_dir)], row)
    import csv

    with (data_dir / "companies.csv").open(encoding="utf-8", newline="") as file:
        rows = {r["company_id"]: r for r in csv.DictReader(file)}
    added = rows["example2"]
    assert added["is_active"] == "true"
    assert added["securities_code"] == "1234"
    assert added["corporate_number"] == ""


def test_empty_stdin_is_rejected(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, ["metrics", "--data-dir", str(data_dir)], "")


def test_output_is_lf_only(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    run_cli(monkeypatch, ["metrics", "--data-dir", str(data_dir)], metric_row())
    raw = (data_dir / "metrics.csv").read_bytes()
    assert b"\r" not in raw


def test_table_registry_matches_real_headers() -> None:
    # レジストリの列定義が実CSVのヘッダーと一致していることを保証する
    import csv

    real_data_dir = Path(__file__).parents[1] / "data"
    for table in TABLES.values():
        with (real_data_dir / table.filename).open(
            encoding="utf-8", newline=""
        ) as file:
            header = tuple(next(csv.reader(file)))
        assert header == table.fieldnames, table.filename


def test_parser_rejects_unknown_table() -> None:
    with pytest.raises(SystemExit):
        create_parser().parse_args(["company_profiles"])


def test_parse_input_rejects_non_object() -> None:
    with pytest.raises(SystemExit):
        parse_input('["not-an-object"]')

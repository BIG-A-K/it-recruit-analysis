from pathlib import Path

from it_recruit_data.store import read_rows, upsert_row


def test_upsert_row_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "sources.csv"
    fieldnames = ("source_id", "title")

    upsert_row(
        path,
        key_fields=("source_id",),
        fieldnames=fieldnames,
        row={"source_id": "source-1", "title": "old"},
    )
    upsert_row(
        path,
        key_fields=("source_id",),
        fieldnames=fieldnames,
        row={"source_id": "source-1", "title": "new"},
    )

    assert read_rows(path) == [{"source_id": "source-1", "title": "new"}]


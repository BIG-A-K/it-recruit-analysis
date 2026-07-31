from __future__ import annotations

import io
import json
import time
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"
ANNUAL_REPORT_CODES = frozenset({"120", "130"})


class EdinetError(RuntimeError):
    """EDINET APIの取得または応答内容が不正な場合のエラー。"""


@dataclass(frozen=True)
class Filing:
    doc_id: str
    edinet_code: str
    filer_name: str
    doc_type_code: str
    period_start: str
    period_end: str
    submitted_at: str
    description: str
    parent_doc_id: str

    @classmethod
    def from_api(cls, row: dict[str, Any]) -> Filing:
        return cls(
            doc_id=str(row.get("docID") or ""),
            edinet_code=str(row.get("edinetCode") or ""),
            filer_name=str(row.get("filerName") or ""),
            doc_type_code=str(row.get("docTypeCode") or ""),
            period_start=str(row.get("periodStart") or ""),
            period_end=str(row.get("periodEnd") or ""),
            submitted_at=str(row.get("submitDateTime") or ""),
            description=str(row.get("docDescription") or ""),
            parent_doc_id=str(row.get("parentDocID") or ""),
        )


def iter_dates(start: date, end: date) -> Iterator[date]:
    if start > end:
        raise ValueError("startはend以前である必要があります")

    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


class EdinetClient:
    def __init__(
        self,
        api_key: str,
        *,
        request_interval: float = 1.0,
        timeout: float = 60.0,
        max_attempts: int = 5,
    ) -> None:
        if not api_key:
            raise ValueError("EDINET APIキーが空です")

        self.api_key = api_key
        self.request_interval = request_interval
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.session = requests.Session()
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.request_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get(self, path: str, params: dict[str, Any]) -> requests.Response:
        url = f"{BASE_URL}{path}"
        request_params = {**params, "Subscription-Key": self.api_key}

        for attempt in range(self.max_attempts):
            self._throttle()
            response = self.session.get(
                url,
                params=request_params,
                timeout=self.timeout,
            )
            self._last_request_at = time.monotonic()

            if response.status_code != 429:
                response.raise_for_status()
                return response

            time.sleep(2**attempt)

        raise EdinetError("EDINET APIが429を返し続けたため取得を中止しました")

    def list_documents(self, target_date: date) -> list[dict[str, Any]]:
        response = self._get(
            "/documents.json",
            {"date": target_date.isoformat(), "type": 2},
        )
        payload = response.json()
        metadata = payload.get("metadata") or {}
        status = str(metadata.get("status") or "200")
        if status != "200":
            raise EdinetError(
                f"書類一覧APIエラー: status={status}, "
                f"message={metadata.get('message', '')}"
            )
        return list(payload.get("results") or [])

    def find_annual_reports(
        self,
        edinet_code: str,
        start: date,
        end: date,
    ) -> list[Filing]:
        filings: dict[str, Filing] = {}

        for target_date in iter_dates(start, end):
            for row in self.list_documents(target_date):
                if row.get("edinetCode") != edinet_code:
                    continue
                if row.get("docTypeCode") not in ANNUAL_REPORT_CODES:
                    continue
                if row.get("csvFlag") != "1":
                    continue

                filing = Filing.from_api(row)
                if filing.doc_id:
                    filings[filing.doc_id] = filing

        return sorted(
            filings.values(),
            key=lambda filing: (filing.period_end, filing.submitted_at),
        )

    def download_csv_zip(self, doc_id: str) -> bytes:
        response = self._get(f"/documents/{doc_id}", {"type": 5})
        content_type = response.headers.get("Content-Type", "").lower()

        if "application/octet-stream" not in content_type:
            try:
                detail = json.dumps(response.json(), ensure_ascii=False)
            except (ValueError, json.JSONDecodeError):
                detail = response.text[:500]
            raise EdinetError(
                f"{doc_id}: CSV ZIPを取得できませんでした "
                f"(Content-Type={content_type!r}, response={detail})"
            )

        return response.content


def extract_zip_safely(content: bytes, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    extracted: list[Path] = []

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for member in archive.infolist():
            output_path = (destination / member.filename).resolve()
            if not output_path.is_relative_to(destination_root):
                raise EdinetError(
                    f"ZIP内に不正なパスがあります: {member.filename}"
                )
            archive.extract(member, destination)
            if not member.is_dir():
                extracted.append(output_path)

    return extracted


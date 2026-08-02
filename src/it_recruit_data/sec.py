from __future__ import annotations

import json
import re
import shutil
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests

SEC_DATA_URL = "https://data.sec.gov"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives"
ANNUAL_FORMS = frozenset({"10-K", "20-F"})
ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[\w.+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?![\w.-])"
)
PLACEHOLDER_CONTACTS = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "invalid",
    }
)
TRANSIENT_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})

_THROTTLE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


class SecError(RuntimeError):
    """SEC data is unavailable, invalid, or unsuitable for normalization."""


@dataclass(frozen=True)
class SecFiling:
    accession_number: str
    form: str
    filing_date: str
    report_date: str
    acceptance_timestamp: str
    primary_document: str
    filer_name: str
    cik: str

    @property
    def accession_compact(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def detail_url(self) -> str:
        return (
            f"{SEC_ARCHIVES_URL}/edgar/data/{int(self.cik)}/"
            f"{self.accession_compact}/{self.accession_number}-index.html"
        )

    @property
    def archive_base_url(self) -> str:
        return (
            f"{SEC_ARCHIVES_URL}/edgar/data/{int(self.cik)}/"
            f"{self.accession_compact}"
        )


def normalize_cik(value: str | int) -> str:
    text = str(value).strip()
    if not text or not text.isascii() or not text.isdigit():
        raise ValueError("SEC CIK must contain only decimal digits")
    if len(text) > 10 or int(text) <= 0:
        raise ValueError("SEC CIK must be a positive number of at most 10 digits")
    return text.zfill(10)


def normalize_accession(value: str) -> str:
    accession = value.strip()
    if not ACCESSION_PATTERN.fullmatch(accession):
        raise ValueError(
            "SEC accession number must use the 0000000000-00-000000 format"
        )
    return accession


def source_id_for_accession(accession_number: str) -> str:
    accession = normalize_accession(accession_number).lower()
    return "sec-" + re.sub(r"[^a-z0-9-]", "", accession)


def validate_user_agent(value: str) -> str:
    user_agent = value.strip()
    match = EMAIL_PATTERN.search(user_agent)
    if not match:
        raise ValueError(
            "SEC_USER_AGENT must identify the requester and include a monitored "
            "email address"
        )
    local_part, domain = match.group(0).lower().rsplit("@", 1)
    if (
        domain in PLACEHOLDER_CONTACTS
        or domain.endswith(".invalid")
        or domain.split(".", 1)[0] in {"example", "test"}
        or local_part in {"example", "test", "noreply", "no-reply"}
        or any(token in local_part for token in ("placeholder", "your.email"))
    ):
        raise ValueError("SEC_USER_AGENT contains a placeholder contact address")
    identity = (user_agent[: match.start()] + user_agent[match.end() :]).strip()
    if len(identity.strip("()[]<> ,;/")) < 2:
        raise ValueError("SEC_USER_AGENT must include an organization or application name")
    return user_agent


def _retry_after_seconds(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return max(0.0, (retry_at - current).total_seconds())


class SecClient:
    def __init__(
        self,
        user_agent: str,
        *,
        request_interval: float = 0.1,
        timeout: float = 60.0,
        max_attempts: int = 5,
        session: requests.Session | None = None,
    ) -> None:
        if request_interval < 0:
            raise ValueError("SEC request interval cannot be negative")
        if max_attempts < 1:
            raise ValueError("SEC max_attempts must be at least one")
        self.user_agent = validate_user_agent(user_agent)
        self.request_interval = request_interval
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json, text/html, application/xhtml+xml, "
                "application/xml;q=0.9, */*;q=0.8",
            }
        )

    def _send(self, url: str) -> requests.Response:
        global _LAST_REQUEST_AT

        last_request_error: requests.RequestException | None = None
        response: requests.Response | None = None
        for attempt in range(self.max_attempts):
            with _THROTTLE_LOCK:
                remaining = self.request_interval - (time.monotonic() - _LAST_REQUEST_AT)
                if remaining > 0:
                    time.sleep(remaining)
                try:
                    response = self.session.get(url, timeout=self.timeout)
                except requests.RequestException as error:
                    last_request_error = error
                    response = None
                finally:
                    _LAST_REQUEST_AT = time.monotonic()

            if response is None:
                if attempt + 1 < self.max_attempts:
                    time.sleep(float(2**attempt))
                    continue
                break

            if response.status_code not in TRANSIENT_HTTP_STATUSES:
                try:
                    response.raise_for_status()
                except requests.HTTPError as error:
                    raise SecError(
                        f"SEC returned non-retryable HTTP {response.status_code} "
                        f"for {url}"
                    ) from error
                return response

            if attempt + 1 == self.max_attempts:
                break
            retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
            delay = max(float(2**attempt), retry_after or 0.0)
            time.sleep(delay)

        if response is None:
            raise SecError(
                f"SEC request failed for {url} after {self.max_attempts} attempts"
            ) from last_request_error
        raise SecError(
            f"SEC returned {response.status_code} for {url} after "
            f"{self.max_attempts} attempts"
        )

    def get_json(self, url: str) -> dict[str, Any]:
        response = self._send(url)
        try:
            payload = response.json()
        except ValueError as error:
            raise SecError(f"SEC returned invalid JSON for {url}") from error
        if not isinstance(payload, dict):
            raise SecError(f"SEC returned a non-object JSON payload for {url}")
        return payload

    def get_bytes(self, url: str) -> bytes:
        return self._send(url).content

    def submissions(self, cik: str) -> dict[str, Any]:
        normalized = normalize_cik(cik)
        payload = self.get_json(f"{SEC_DATA_URL}/submissions/CIK{normalized}.json")
        response_cik = payload.get("cik")
        if response_cik is not None and normalize_cik(response_cik) != normalized:
            raise SecError("SEC submissions response CIK does not match the request")
        return payload

    def companyfacts(self, cik: str) -> dict[str, Any]:
        normalized = normalize_cik(cik)
        payload = self.get_json(
            f"{SEC_DATA_URL}/api/xbrl/companyfacts/CIK{normalized}.json"
        )
        response_cik = payload.get("cik")
        if response_cik is not None and normalize_cik(response_cik) != normalized:
            raise SecError("SEC Company Facts response CIK does not match the request")
        return payload

    def discover_filings(
        self,
        cik: str,
        *,
        start: date,
        end: date,
        form: str,
        include_amendments: bool = False,
    ) -> tuple[list[SecFiling], dict[str, Any], dict[str, dict[str, Any]]]:
        if start > end:
            raise ValueError("SEC filing start date must not be after end date")
        if form not in ANNUAL_FORMS:
            raise ValueError("SEC annual form must be 10-K or 20-F")

        root = self.submissions(cik)
        payloads: list[dict[str, Any]] = [root]
        historical: dict[str, dict[str, Any]] = {}
        for descriptor in (root.get("filings") or {}).get("files") or []:
            if not isinstance(descriptor, dict):
                continue
            name = str(descriptor.get("name") or "")
            if not name or Path(name).name != name or not name.endswith(".json"):
                raise SecError(f"Unsafe SEC submissions history filename: {name!r}")
            payload = self.get_json(f"{SEC_DATA_URL}/submissions/{name}")
            historical[name] = payload
            payloads.append(payload)

        filings = select_filings(
            payloads,
            cik=normalize_cik(cik),
            filer_name=str(root.get("name") or ""),
            start=start,
            end=end,
            form=form,
            include_amendments=include_amendments,
        )
        return filings, root, historical


def filings_from_submissions(
    payload: dict[str, Any],
    *,
    cik: str,
    filer_name: str,
) -> list[SecFiling]:
    expected_cik = normalize_cik(cik)
    normalized_cik = normalize_cik(payload.get("cik") or expected_cik)
    if normalized_cik != expected_cik:
        raise SecError("SEC submissions payload CIK does not match the requested company")
    name = str(payload.get("name") or filer_name)
    filing_data = payload.get("filings") or payload
    arrays = filing_data.get("recent") or filing_data
    if not isinstance(arrays, dict):
        raise SecError("SEC submissions filing arrays are missing")

    accessions = arrays.get("accessionNumber") or []
    if not isinstance(accessions, list):
        raise SecError("SEC submissions accessionNumber must be an array")

    def item(field: str, index: int) -> str:
        values = arrays.get(field) or []
        if not isinstance(values, list) or index >= len(values):
            return ""
        return str(values[index] or "")

    filings: list[SecFiling] = []
    for index, raw_accession in enumerate(accessions):
        accession = str(raw_accession or "")
        try:
            accession = normalize_accession(accession)
        except ValueError as error:
            raise SecError(f"Invalid accession in SEC submissions: {accession!r}") from error
        filings.append(
            SecFiling(
                accession_number=accession,
                form=item("form", index),
                filing_date=item("filingDate", index),
                report_date=item("reportDate", index),
                acceptance_timestamp=item("acceptanceDateTime", index),
                primary_document=item("primaryDocument", index),
                filer_name=name,
                cik=normalized_cik,
            )
        )
    return filings


def select_filings(
    payloads: list[dict[str, Any]],
    *,
    cik: str,
    filer_name: str,
    start: date,
    end: date,
    form: str,
    include_amendments: bool = False,
) -> list[SecFiling]:
    allowed_forms = {form, f"{form}/A"} if include_amendments else {form}
    selected: dict[str, SecFiling] = {}
    for payload in payloads:
        for filing in filings_from_submissions(
            payload,
            cik=cik,
            filer_name=filer_name,
        ):
            if filing.form not in allowed_forms:
                continue
            try:
                filing_date = date.fromisoformat(filing.filing_date)
            except ValueError as error:
                raise SecError(
                    f"Invalid filing date for {filing.accession_number}: "
                    f"{filing.filing_date!r}"
                ) from error
            if start <= filing_date <= end:
                selected[filing.accession_number] = filing
    return sorted(
        selected.values(),
        key=lambda filing: (
            filing.filing_date,
            filing.acceptance_timestamp,
            filing.accession_number,
        ),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _safe_archive_name(name: str) -> str:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise SecError(f"Unsafe SEC archive filename: {name!r}")
    return name


def find_xbrl_instance_name(index_payload: dict[str, Any], primary_document: str) -> str | None:
    directory = index_payload.get("directory") or {}
    items = directory.get("item") or []
    if not isinstance(items, list):
        raise SecError("SEC filing index directory items are invalid")
    primary_stem = Path(primary_document).stem.lower()
    candidates: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        lower = name.lower()
        if not lower.endswith(".xml"):
            continue
        if lower in {"filingsummary.xml", "metalinks.json"}:
            continue
        if any(marker in lower for marker in ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")):
            continue
        candidates.append(_safe_archive_name(name))
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda name: (
            not name.lower().endswith("_htm.xml"),
            not name.lower().startswith(primary_stem),
            name,
        ),
    )[0]


def cache_filing_package(
    client: SecClient,
    filing: SecFiling,
    destination: Path,
    *,
    submissions_payload: dict[str, Any],
    historical_submissions: dict[str, dict[str, Any]],
    companyfacts_payload: dict[str, Any],
) -> bool:
    """Cache one filing. Return False without network access when it already exists."""
    if destination.exists():
        return False

    primary_document = _safe_archive_name(filing.primary_document)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    try:
        _write_json(temporary / "submissions.json", submissions_payload)
        for name, payload in historical_submissions.items():
            _write_json(temporary / _safe_archive_name(name), payload)
        _write_json(temporary / "companyfacts.json", companyfacts_payload)
        _write_json(temporary / "filing.json", asdict(filing))

        index_payload = client.get_json(f"{filing.archive_base_url}/index.json")
        _write_json(temporary / "index.json", index_payload)
        (temporary / primary_document).write_bytes(
            client.get_bytes(f"{filing.archive_base_url}/{primary_document}")
        )

        instance_name = find_xbrl_instance_name(index_payload, primary_document)
        if instance_name and instance_name != primary_document:
            (temporary / instance_name).write_bytes(
                client.get_bytes(f"{filing.archive_base_url}/{instance_name}")
            )
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return True


def load_cached_filing(path: Path) -> SecFiling:
    metadata_path = path / "filing.json"
    if not metadata_path.exists():
        raise SecError(f"Cached SEC filing metadata is missing: {metadata_path}")
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise SecError(f"Cached SEC filing metadata is invalid: {metadata_path}") from error
    try:
        filing = SecFiling(**payload)
    except (TypeError, KeyError) as error:
        raise SecError(f"Cached SEC filing metadata is invalid: {metadata_path}") from error
    normalize_accession(filing.accession_number)
    normalize_cik(filing.cik)
    return filing

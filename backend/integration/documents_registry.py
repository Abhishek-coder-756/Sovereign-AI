import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

from .storage import company_paths


def _registry_path(company: str) -> Path:
    return company_paths(company)["root"] / "documents.json"


def _load(company: str):
    path = _registry_path(company)

    if not path.exists():
        return []

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return []


def _save(company: str, records):
    path = _registry_path(company)

    path.write_text(
        json.dumps(records, indent=2),
        encoding="utf-8"
    )


def register_upload(
    company,
    filename,
    category,
    size
):
    records = _load(company)

    # Prevent unsafe filenames in the registry
    filename = Path(filename).name

    record = {
        "id": uuid.uuid4().hex[:12],
        "filename": filename,
        "category": category,
        "size": size,
        "indexed": False,
        "pages": 0,
        "chunks": 0,
        "uploaded_at": datetime.now(
            timezone.utc
        ).isoformat()
    }

    records.append(record)

    _save(company, records)

    return record


def list_documents(company):
    return _load(company)


def mark_indexed(
    company,
    filename,
    pages,
    chunks
):
    records = _load(company)

    for record in records:
        if record["filename"] == filename:
            record["indexed"] = True
            record["pages"] = pages
            record["chunks"] = chunks

    _save(company, records)


def delete_document(
    company,
    document_id
):
    records = _load(company)

    target = None
    remaining = []

    for record in records:

        if record["id"] == document_id:
            target = record
        else:
            remaining.append(record)

    if target is None:
        return None

    _save(company, remaining)

    return target

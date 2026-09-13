from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STORAGE_ROOT = PROJECT_ROOT / "storage"


def _safe_company_name(company: str) -> str:
    company = str(company or "default").strip()

    safe = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        company
    )

    return safe or "default"


def company_paths(company: str):
    company_dir = STORAGE_ROOT / _safe_company_name(company)

    documents = company_dir / "documents"
    images = company_dir / "images"
    uploads = company_dir / "uploads"
    index = company_dir / "index"

    for path in [documents, images, uploads, index]:
        path.mkdir(parents=True, exist_ok=True)

    return {
        "root": company_dir,
        "documents": documents,
        "images": images,
        "uploads": uploads,
        "index": index,
        "faiss": index / "faiss.index",
        "documents_pickle": index / "documents.pkl",
    }

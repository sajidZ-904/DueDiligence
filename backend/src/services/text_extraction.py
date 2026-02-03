from __future__ import annotations

from pathlib import Path


def extract_text_from_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    return _extract_text_file(path)


def _extract_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return f"PDF extraction unavailable for {path.name}. Install pypdf to enable text extraction."

    reader = PdfReader(str(path))
    parts = []
    max_pages = 30
    for page in reader.pages[:max_pages]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join([p for p in parts if p]).strip()


from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from src.models.enums import ProjectStatus, RequestStatus, ScopeType
from src.services.text_extraction import extract_text_from_path
from src.storage.memory_store import ChunkRecord, STORE
from src.utils.ids import new_id
from src.utils.paths import resolve_data_file
from src.utils.time import now_utc


def _chunk_text(content: str, *, max_len: int = 800) -> List[str]:
    normalized = content.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    parts = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    chunks: List[str] = []
    for part in parts:
        if len(part) <= max_len:
            chunks.append(part)
            continue
        start = 0
        while start < len(part):
            end = min(start + max_len, len(part))
            chunks.append(part[start:end].strip())
            start = end
    return [c for c in chunks if c]


async def index_document_job(*, request_id: UUID, document_id: UUID, content: Optional[str], file_path: Optional[str]) -> None:
    STORE.update_request(request_id, status=RequestStatus.RUNNING, progress=0.05)
    doc = STORE.get_document(document_id)
    if doc is None:
        STORE.update_request(
            request_id,
            status=RequestStatus.FAILED,
            progress=1.0,
            error_message="document_not_found",
        )
        return

    text = content or ""
    if not text and file_path:
        try:
            path = resolve_data_file(file_path)
        except Exception:
            path = None
        if path is not None:
            text = extract_text_from_path(path) or ""
    chunks_text = _chunk_text(text) if text else []
    if not chunks_text:
        chunks_text = [f"Document {doc.filename} indexed with no extractable text at {now_utc().isoformat()}"]

    chunks: List[ChunkRecord] = []
    for i, chunk in enumerate(chunks_text):
        chunks.append(
            ChunkRecord(
                chunk_id=new_id(),
                document_id=document_id,
                page_number=1,
                bbox=None,
                text=chunk,
            )
        )
        if i and i % 10 == 0:
            STORE.update_request(request_id, progress=min(0.9, 0.1 + (i / max(1, len(chunks_text))) * 0.8))

    STORE.set_document_indexed(document_id, chunks=chunks)
    STORE.update_request(
        request_id,
        status=RequestStatus.SUCCEEDED,
        progress=1.0,
        result={"document_id": str(document_id), "chunks": len(chunks)},
    )

    latest_sig = STORE.corpus_signature_all_docs()
    for project in STORE.list_projects():
        if project.scope_type != ScopeType.ALL_DOCS:
            continue
        if project.project_status in (ProjectStatus.ERROR, ProjectStatus.CREATING):
            continue
        if project.index_snapshot and project.index_snapshot != latest_sig:
            STORE.update_project(
                project.project_id,
                project_status=ProjectStatus.OUTDATED,
                outdated_reason=f"Corpus changed after indexing document {document_id}",
            )


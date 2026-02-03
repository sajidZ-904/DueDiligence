from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from src.models.enums import AnswerStatus, RequestStatus, ScopeType
from src.storage.memory_store import AnswerVersionRecord, STORE
from src.utils.ids import new_id
from src.utils.time import now_utc


def _keywords(question: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]{2,}", question.lower())
    stop = {"the", "and", "for", "with", "are", "was", "were", "this", "that", "you", "your", "has", "have", "had"}
    out = []
    for t in tokens:
        if t in stop:
            continue
        if t.isdigit() and len(t) < 4:
            continue
        out.append(t)
    return out[:12]


def _score(text: str, keys: List[str]) -> int:
    low = text.lower()
    score = 0
    for k in keys:
        if k in low:
            score += 1
    return score


def _select_chunks(project_id: UUID, question_id: UUID) -> List[Dict]:
    project = STORE.get_project(project_id)
    if project is None:
        raise KeyError("project_not_found")
    question = project.questions.get(question_id)
    if question is None:
        raise KeyError("question_not_found")

    keys = _keywords(question.prompt)
    if project.scope_type == ScopeType.ALL_DOCS:
        docs = STORE.iter_indexed_docs_for_all_docs()
    else:
        docs = STORE.iter_indexed_docs_for_subset(project.scope_document_ids)

    scored: List[Tuple[int, Dict]] = []
    for doc in docs:
        for chunk in doc.chunks:
            s = _score(chunk.text, keys) if keys else 0
            if s <= 0 and keys:
                continue
            scored.append(
                (
                    s,
                    {
                        "document_id": doc.document_id,
                        "chunk_id": chunk.chunk_id,
                        "page_number": chunk.page_number,
                        "bbox": chunk.bbox,
                        "excerpt": chunk.text[:240],
                    },
                )
            )

    scored.sort(key=lambda x: (x[0], str(x[1]["chunk_id"])), reverse=True)
    top = [c for _, c in scored[:5]]
    return top


def generate_answer_payload(project_id: UUID, question_id: UUID) -> AnswerVersionRecord:
    citations = _select_chunks(project_id, question_id)
    answerable = len(citations) > 0
    if answerable:
        confidence = min(0.95, 0.4 + 0.12 * len(citations))
        evidence = " ".join([c["excerpt"] for c in citations[:2]])
        answer_text = f"Answerable based on the provided documents. Evidence: {evidence}"
    else:
        confidence = 0.1
        answer_text = "Not answerable from the currently indexed documents for this project scope."

    return AnswerVersionRecord(
        answer_version_id=new_id(),
        created_at=now_utc(),
        answerable=answerable,
        answer_text=answer_text,
        confidence=confidence,
        citations=[
            {
                "document_id": str(c["document_id"]),
                "chunk_id": str(c["chunk_id"]),
                "page_number": c["page_number"],
                "bbox": c["bbox"],
                "excerpt": c["excerpt"],
            }
            for c in citations
        ],
    )


async def generate_all_answers_job(*, request_id: UUID, project_id: UUID) -> None:
    STORE.update_request(request_id, status=RequestStatus.RUNNING, progress=0.02)
    project = STORE.get_project(project_id)
    if project is None:
        STORE.update_request(
            request_id,
            status=RequestStatus.FAILED,
            progress=1.0,
            error_message="project_not_found",
        )
        return

    question_ids = list(project.questions.keys())
    total = max(1, len(question_ids))
    for idx, qid in enumerate(question_ids, start=1):
        answer = STORE.get_answer(project_id=project_id, question_id=qid)
        if answer is None:
            STORE.get_or_create_answer(new_id(), project_id=project_id, question_id=qid)
        version = generate_answer_payload(project_id, qid)
        STORE.put_ai_answer_version(project_id=project_id, question_id=qid, answer_version=version)
        if version.answerable:
            STORE.set_answer_status(project_id=project_id, question_id=qid, status=AnswerStatus.DRAFT)
        else:
            STORE.set_answer_status(project_id=project_id, question_id=qid, status=AnswerStatus.MISSING_DATA)
        STORE.update_request(request_id, progress=min(0.98, idx / total))

    STORE.update_request(
        request_id,
        status=RequestStatus.SUCCEEDED,
        progress=1.0,
        result={"project_id": str(project_id), "answers_generated": len(question_ids)},
    )


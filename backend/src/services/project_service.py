from __future__ import annotations

from typing import Dict, List, Optional
from uuid import UUID

from src.models.enums import ProjectStatus, RequestStatus, ScopeType
from src.services.text_extraction import extract_text_from_path
from src.storage.memory_store import QuestionRecord, SectionRecord, STORE
from src.utils.ids import new_id
from src.utils.paths import resolve_data_file


def _extract_questions(questionnaire_text: str) -> List[str]:
    text = questionnaire_text.replace("\r\n", "\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    candidates = []
    for line in lines:
        if len(line) < 8:
            continue
        if "?" in line:
            candidates.append(line)
            continue
        prefix = line.split(" ", 1)[0]
        if prefix.rstrip(".)").isdigit():
            candidates.append(line)
    if not candidates:
        return lines[:50]
    return candidates[:500]


def _normalize_scope(scope_type: ScopeType, scope_document_ids: Optional[List[UUID]]) -> List[UUID]:
    if scope_type == ScopeType.SUBSET:
        return list(scope_document_ids or [])
    return []


async def create_project_job(
    *,
    request_id: UUID,
    project_id: UUID,
    project_name: str,
    scope_type: ScopeType,
    scope_document_ids: Optional[List[UUID]],
    questionnaire_text: Optional[str],
    questionnaire_file_path: Optional[str],
    questions: Optional[List[str]],
) -> None:
    STORE.update_request(request_id, status=RequestStatus.RUNNING, progress=0.05)
    project = STORE.get_project(project_id)
    if project is None:
        STORE.update_request(
            request_id,
            status=RequestStatus.FAILED,
            progress=1.0,
            error_message="project_not_found",
        )
        return

    normalized_scope_ids = _normalize_scope(scope_type, scope_document_ids)
    if questions:
        prompts = [q.strip() for q in questions if q and q.strip()]
    elif questionnaire_text:
        prompts = _extract_questions(questionnaire_text)
    elif questionnaire_file_path:
        try:
            path = resolve_data_file(questionnaire_file_path)
            prompts = _extract_questions(extract_text_from_path(path))
        except Exception:
            prompts = ["Provide questionnaire_text or questions to create a project."]
    else:
        prompts = ["Provide questionnaire_text or questions to create a project."]

    section_id = new_id()
    question_records: Dict[UUID, QuestionRecord] = {}
    question_ids: List[UUID] = []
    for idx, prompt in enumerate(prompts, start=1):
        qid = new_id()
        question_ids.append(qid)
        question_records[qid] = QuestionRecord(
            question_id=qid,
            project_id=project_id,
            section_id=section_id,
            prompt=prompt,
            order=idx,
        )
        STORE.get_or_create_answer(new_id(), project_id=project_id, question_id=qid)
        if idx % 25 == 0:
            STORE.update_request(request_id, progress=min(0.6, 0.05 + (idx / max(1, len(prompts))) * 0.55))

    sections = [
        SectionRecord(
            section_id=section_id,
            project_id=project_id,
            title="Questionnaire",
            order=1,
            question_ids=question_ids,
        )
    ]

    if scope_type == ScopeType.ALL_DOCS:
        snapshot = STORE.corpus_signature_all_docs()
        scope_ids_for_project: List[UUID] = []
    else:
        snapshot = STORE.corpus_signature_subset(normalized_scope_ids)
        scope_ids_for_project = normalized_scope_ids

    STORE.update_project(
        project_id,
        project_status=ProjectStatus.READY,
        scope_type=scope_type,
        scope_document_ids=scope_ids_for_project,
        index_snapshot=snapshot,
        outdated_reason=None,
        last_request_id=request_id,
        sections=sections,
        questions=question_records,
    )
    STORE.update_request(
        request_id,
        status=RequestStatus.SUCCEEDED,
        progress=1.0,
        result={"project_id": str(project_id), "questions": len(question_ids)},
    )

    if scope_type == ScopeType.ALL_DOCS:
        latest_sig = STORE.corpus_signature_all_docs()
        updated = STORE.get_project(project_id)
        if updated and updated.index_snapshot and updated.index_snapshot != latest_sig:
            STORE.update_project(
                project_id,
                project_status=ProjectStatus.OUTDATED,
                outdated_reason="Corpus changed during project creation",
            )


async def update_project_job(
    *,
    project_id: UUID,
    scope_type: Optional[ScopeType],
    scope_document_ids: Optional[List[UUID]],
) -> None:
    project = STORE.get_project(project_id)
    if project is None:
        raise KeyError("project_not_found")

    new_scope_type = scope_type or project.scope_type
    if new_scope_type == ScopeType.SUBSET:
        new_scope_ids = list(scope_document_ids or project.scope_document_ids)
        snapshot = STORE.corpus_signature_subset(new_scope_ids)
    else:
        new_scope_ids = []
        snapshot = STORE.corpus_signature_all_docs()

    STORE.update_project(
        project_id,
        project_status=ProjectStatus.READY,
        scope_type=new_scope_type,
        scope_document_ids=new_scope_ids,
        index_snapshot=snapshot,
        outdated_reason=None,
        last_request_id=None,
    )


from __future__ import annotations

from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.models.api import (
    AnswerPayload,
    CreateProjectAsyncRequest,
    CreateProjectAsyncResponse,
    GenerateAllAnswersRequest,
    GenerateAllAnswersResponse,
    GenerateSingleAnswerRequest,
    GenerateSingleAnswerResponse,
    IndexDocumentAsyncRequest,
    IndexDocumentAsyncResponse,
    ProjectInfoResponse,
    ProjectStatusResponse,
    RequestStatusResponse,
    SectionInfo,
    QuestionInfo,
    UpdateAnswerRequest,
    UpdateAnswerResponse,
    UpdateProjectAsyncRequest,
    UpdateProjectAsyncResponse,
)
from src.models.enums import AnswerStatus, ProjectStatus, RequestStatus, RequestType, ScopeType
from src.services.answer_service import generate_all_answers_job, generate_answer_payload
from src.services.ingestion_service import index_document_job
from src.services.project_service import create_project_job, update_project_job
from src.services.text_extraction import extract_text_from_path
from src.storage.memory_store import ManualAnswerVersionRecord, STORE
from src.utils.ids import new_id
from src.utils.paths import resolve_data_file
from src.utils.time import now_utc
from src.workers.runner import schedule


router = APIRouter()


def _answer_payload_for(*, project_id: UUID, question_id: UUID) -> AnswerPayload:
    answer = STORE.get_answer(project_id=project_id, question_id=question_id)
    if answer is None:
        answer = STORE.get_or_create_answer(new_id(), project_id=project_id, question_id=question_id)

    latest_manual = answer.latest_manual()
    latest_ai = answer.latest_ai()
    if latest_manual is None and latest_ai is None:
        version = generate_answer_payload(project_id, question_id)
        STORE.put_ai_answer_version(project_id=project_id, question_id=question_id, answer_version=version)
        latest_ai = version

    if latest_manual is not None:
        base_text = latest_manual.answer_text
        citations = latest_manual.citations
        manual_id = latest_manual.manual_version_id
    else:
        base_text = latest_ai.answer_text if latest_ai else ""
        citations = latest_ai.citations if latest_ai else []
        manual_id = None

    ai_version_id = latest_ai.answer_version_id if latest_ai else new_id()
    generated_at = latest_ai.created_at if latest_ai else now_utc()
    answerable = latest_ai.answerable if latest_ai else False
    confidence = latest_ai.confidence if latest_ai else 0.0

    return AnswerPayload(
        question_id=question_id,
        answer_status=answer.answer_status,
        answerable=answerable,
        answer_text=base_text,
        citations=citations,
        confidence=confidence,
        generated_at=generated_at,
        ai_version_id=ai_version_id,
        manual_version_id=manual_id,
    )


@router.post("/index-document-async", response_model=IndexDocumentAsyncResponse)
async def index_document_async(req: IndexDocumentAsyncRequest) -> IndexDocumentAsyncResponse:
    request_id = new_id()
    document_id = new_id()
    STORE.create_request(request_id, RequestType.INDEX_DOCUMENT)
    extracted_content = req.content
    if req.file_path:
        try:
            path = resolve_data_file(req.file_path)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="file_not_found")
        except ValueError:
            raise HTTPException(status_code=400, detail="file_path_must_be_within_data_dir")
        extracted_content = extract_text_from_path(path)
    STORE.create_document(
        document_id,
        filename=req.filename,
        content=extracted_content,
        mime_type=req.mime_type,
        eligible_for_all_docs=req.eligible_for_all_docs,
    )
    schedule(index_document_job(request_id=request_id, document_id=document_id, content=extracted_content))
    return IndexDocumentAsyncResponse(request_id=request_id, document_id=document_id)


@router.post("/create-project-async", response_model=CreateProjectAsyncResponse)
async def create_project_async(req: CreateProjectAsyncRequest) -> CreateProjectAsyncResponse:
    if req.scope_type == ScopeType.SUBSET and not req.scope_document_ids:
        raise HTTPException(status_code=400, detail="scope_document_ids required for SUBSET scope")
    request_id = new_id()
    project_id = new_id()
    STORE.create_request(request_id, RequestType.CREATE_PROJECT)
    scope_ids = list(req.scope_document_ids or [])
    questionnaire_text = req.questionnaire_text
    if req.questionnaire_file_path:
        try:
            path = resolve_data_file(req.questionnaire_file_path)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="file_not_found")
        except ValueError:
            raise HTTPException(status_code=400, detail="file_path_must_be_within_data_dir")
        questionnaire_text = extract_text_from_path(path)
    STORE.create_project(
        project_id,
        project_name=req.project_name,
        scope_type=req.scope_type,
        scope_document_ids=scope_ids if req.scope_type == ScopeType.SUBSET else [],
        request_id=request_id,
    )
    schedule(
        create_project_job(
            request_id=request_id,
            project_id=project_id,
            project_name=req.project_name,
            scope_type=req.scope_type,
            scope_document_ids=req.scope_document_ids,
            questionnaire_text=questionnaire_text,
            questions=req.questions,
        )
    )
    return CreateProjectAsyncResponse(request_id=request_id, project_id=project_id)


@router.post("/update-project-async", response_model=UpdateProjectAsyncResponse)
async def update_project_async(req: UpdateProjectAsyncRequest) -> UpdateProjectAsyncResponse:
    request_id = new_id()
    STORE.create_request(request_id, RequestType.UPDATE_PROJECT)
    project = STORE.get_project(req.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    STORE.update_project(req.project_id, project_status=ProjectStatus.CREATING, last_request_id=request_id)

    async def run() -> None:
        STORE.update_request(request_id, status=RequestStatus.RUNNING, progress=0.05)
        try:
            await update_project_job(
                project_id=req.project_id,
                scope_type=req.scope_type,
                scope_document_ids=req.scope_document_ids,
            )
        except KeyError:
            STORE.update_request(
                request_id,
                status=RequestStatus.FAILED,
                progress=1.0,
                error_message="project_not_found",
            )
            STORE.update_project(req.project_id, project_status=ProjectStatus.ERROR, outdated_reason="project_not_found")
            return

        if req.regenerate_answers:
            generation_request_id = new_id()
            STORE.create_request(generation_request_id, RequestType.GENERATE_ALL_ANSWERS)
            STORE.update_project(req.project_id, last_request_id=generation_request_id)
            STORE.update_request(
                request_id,
                status=RequestStatus.SUCCEEDED,
                progress=1.0,
                result={
                    "project_id": str(req.project_id),
                    "generation_request_id": str(generation_request_id),
                },
            )
            schedule(generate_all_answers_job(request_id=generation_request_id, project_id=req.project_id))
            return

        STORE.update_project(req.project_id, last_request_id=request_id)
        STORE.update_request(request_id, status=RequestStatus.SUCCEEDED, progress=1.0, result={"project_id": str(req.project_id)})

    schedule(run())
    return UpdateProjectAsyncResponse(request_id=request_id, project_id=req.project_id)


@router.get("/get-project-status", response_model=ProjectStatusResponse)
async def get_project_status(project_id: UUID) -> ProjectStatusResponse:
    project = STORE.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return ProjectStatusResponse(
        project_id=project.project_id,
        project_status=project.project_status,
        outdated_reason=project.outdated_reason,
        last_request_id=project.last_request_id,
    )


@router.get("/get-project-info", response_model=ProjectInfoResponse)
async def get_project_info(project_id: UUID) -> ProjectInfoResponse:
    project = STORE.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")

    sections: List[SectionInfo] = []
    for s in sorted(project.sections, key=lambda x: x.order):
        questions = []
        for qid in s.question_ids:
            q = project.questions.get(qid)
            if q is None:
                continue
            questions.append(QuestionInfo(question_id=q.question_id, prompt=q.prompt, order=q.order))
        sections.append(SectionInfo(section_id=s.section_id, title=s.title, order=s.order, questions=questions))

    answers: Dict[UUID, AnswerPayload] = {}
    for qid in project.questions.keys():
        answers[qid] = _answer_payload_for(project_id=project_id, question_id=qid)

    return ProjectInfoResponse(
        project_id=project.project_id,
        project_name=project.project_name,
        scope_type=project.scope_type,
        scope_document_ids=list(project.scope_document_ids),
        project_status=project.project_status,
        sections=sections,
        answers=answers,
    )


@router.post("/generate-single-answer", response_model=GenerateSingleAnswerResponse)
async def generate_single_answer(req: GenerateSingleAnswerRequest) -> GenerateSingleAnswerResponse:
    project = STORE.get_project(req.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    if req.question_id not in project.questions:
        raise HTTPException(status_code=404, detail="question_not_found")
    answer = STORE.get_answer(project_id=req.project_id, question_id=req.question_id)
    if answer is None:
        STORE.get_or_create_answer(new_id(), project_id=req.project_id, question_id=req.question_id)

    version = generate_answer_payload(req.project_id, req.question_id)
    STORE.put_ai_answer_version(project_id=req.project_id, question_id=req.question_id, answer_version=version)
    if version.answerable:
        STORE.set_answer_status(project_id=req.project_id, question_id=req.question_id, status=AnswerStatus.DRAFT)
    else:
        STORE.set_answer_status(project_id=req.project_id, question_id=req.question_id, status=AnswerStatus.MISSING_DATA)
    return GenerateSingleAnswerResponse(answer=_answer_payload_for(project_id=req.project_id, question_id=req.question_id))


@router.post("/generate-all-answers", response_model=GenerateAllAnswersResponse)
async def generate_all_answers(req: GenerateAllAnswersRequest) -> GenerateAllAnswersResponse:
    project = STORE.get_project(req.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    request_id = new_id()
    STORE.create_request(request_id, RequestType.GENERATE_ALL_ANSWERS)
    schedule(generate_all_answers_job(request_id=request_id, project_id=req.project_id))
    STORE.update_project(req.project_id, last_request_id=request_id)
    return GenerateAllAnswersResponse(request_id=request_id)


@router.post("/update-answer", response_model=UpdateAnswerResponse)
async def update_answer(req: UpdateAnswerRequest) -> UpdateAnswerResponse:
    project = STORE.get_project(req.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    if req.question_id not in project.questions:
        raise HTTPException(status_code=404, detail="question_not_found")

    answer = STORE.get_answer(project_id=req.project_id, question_id=req.question_id)
    if answer is None:
        answer = STORE.get_or_create_answer(new_id(), project_id=req.project_id, question_id=req.question_id)

    if req.manual_answer_text is not None:
        manual = ManualAnswerVersionRecord(
            manual_version_id=new_id(),
            created_at=now_utc(),
            answer_text=req.manual_answer_text,
            citations=[],
            reviewer=req.reviewer,
        )
        STORE.put_manual_answer_version(project_id=req.project_id, question_id=req.question_id, manual_version=manual)

    if req.new_status is not None:
        STORE.set_answer_status(project_id=req.project_id, question_id=req.question_id, status=req.new_status)

    return UpdateAnswerResponse(answer=_answer_payload_for(project_id=req.project_id, question_id=req.question_id))


@router.get("/get-request-status", response_model=RequestStatusResponse)
async def get_request_status(request_id: UUID) -> RequestStatusResponse:
    record = STORE.get_request(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="request_not_found")
    return RequestStatusResponse(
        request_id=record.request_id,
        status=record.status,
        request_type=record.request_type.value,
        progress=record.progress,
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
        result=record.result,
    )


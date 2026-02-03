from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.enums import AnswerStatus, ProjectStatus, RequestStatus, ScopeType


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class Citation(BaseModel):
    document_id: UUID
    chunk_id: UUID
    page_number: int = Field(ge=1)
    bbox: Optional[BoundingBox] = None
    excerpt: str


class IndexDocumentAsyncRequest(BaseModel):
    filename: str = Field(min_length=1)
    content: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    eligible_for_all_docs: bool = True


class IndexDocumentAsyncResponse(BaseModel):
    request_id: UUID
    document_id: UUID


class CreateProjectAsyncRequest(BaseModel):
    project_name: str = Field(min_length=1)
    scope_type: ScopeType
    scope_document_ids: Optional[List[UUID]] = None
    questionnaire_text: Optional[str] = None
    questionnaire_file_path: Optional[str] = None
    questions: Optional[List[str]] = None


class CreateProjectAsyncResponse(BaseModel):
    request_id: UUID
    project_id: UUID


class UpdateProjectAsyncRequest(BaseModel):
    project_id: UUID
    scope_type: Optional[ScopeType] = None
    scope_document_ids: Optional[List[UUID]] = None
    regenerate_answers: bool = False


class UpdateProjectAsyncResponse(BaseModel):
    request_id: UUID
    project_id: UUID


class GenerateSingleAnswerRequest(BaseModel):
    project_id: UUID
    question_id: UUID


class GenerateAllAnswersRequest(BaseModel):
    project_id: UUID


class GenerateAllAnswersResponse(BaseModel):
    request_id: UUID


class UpdateAnswerRequest(BaseModel):
    project_id: UUID
    question_id: UUID
    new_status: Optional[AnswerStatus] = None
    manual_answer_text: Optional[str] = None
    reviewer: Optional[str] = None


class AnswerPayload(BaseModel):
    question_id: UUID
    answer_status: AnswerStatus
    answerable: bool
    answer_text: str
    citations: List[Citation]
    confidence: float = Field(ge=0, le=1)
    generated_at: datetime
    ai_version_id: UUID
    manual_version_id: Optional[UUID] = None


class GenerateSingleAnswerResponse(BaseModel):
    answer: AnswerPayload


class UpdateAnswerResponse(BaseModel):
    answer: AnswerPayload


class QuestionInfo(BaseModel):
    question_id: UUID
    prompt: str
    order: int


class SectionInfo(BaseModel):
    section_id: UUID
    title: str
    order: int
    questions: List[QuestionInfo]


class ProjectInfoResponse(BaseModel):
    project_id: UUID
    project_name: str
    scope_type: ScopeType
    scope_document_ids: List[UUID]
    project_status: ProjectStatus
    sections: List[SectionInfo]
    answers: Dict[UUID, AnswerPayload]


class ProjectStatusResponse(BaseModel):
    project_id: UUID
    project_status: ProjectStatus
    outdated_reason: Optional[str] = None
    last_request_id: Optional[UUID] = None


class RequestStatusResponse(BaseModel):
    request_id: UUID
    status: RequestStatus
    request_type: str
    progress: Optional[float] = Field(default=None, ge=0, le=1)
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    result: Optional[Dict[str, Any]] = None


from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

from src.models.enums import AnswerStatus, ProjectStatus, RequestStatus, RequestType, ScopeType
from src.utils.hashing import sha256_json, sha256_text
from src.utils.time import now_utc


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: UUID
    document_id: UUID
    page_number: int
    bbox: Optional[Dict[str, float]]
    text: str


@dataclass
class DocumentRecord:
    document_id: UUID
    filename: str
    mime_type: Optional[str]
    eligible_for_all_docs: bool
    content_hash: str
    created_at: datetime
    indexed_at: Optional[datetime] = None
    ingestion_status: str = "UPLOADED"
    chunks: List[ChunkRecord] = field(default_factory=list)


@dataclass(frozen=True)
class QuestionRecord:
    question_id: UUID
    project_id: UUID
    section_id: UUID
    prompt: str
    order: int


@dataclass(frozen=True)
class SectionRecord:
    section_id: UUID
    project_id: UUID
    title: str
    order: int
    question_ids: List[UUID]


@dataclass(frozen=True)
class AnswerVersionRecord:
    answer_version_id: UUID
    created_at: datetime
    answerable: bool
    answer_text: str
    confidence: float
    citations: List[Dict[str, Any]]


@dataclass(frozen=True)
class ManualAnswerVersionRecord:
    manual_version_id: UUID
    created_at: datetime
    answer_text: str
    citations: List[Dict[str, Any]]
    reviewer: Optional[str]


@dataclass
class AnswerRecord:
    answer_id: UUID
    project_id: UUID
    question_id: UUID
    answer_status: AnswerStatus
    ai_versions: List[AnswerVersionRecord] = field(default_factory=list)
    manual_versions: List[ManualAnswerVersionRecord] = field(default_factory=list)

    def latest_ai(self) -> Optional[AnswerVersionRecord]:
        return self.ai_versions[-1] if self.ai_versions else None

    def latest_manual(self) -> Optional[ManualAnswerVersionRecord]:
        return self.manual_versions[-1] if self.manual_versions else None


@dataclass
class ProjectRecord:
    project_id: UUID
    project_name: str
    scope_type: ScopeType
    scope_document_ids: List[UUID]
    created_at: datetime
    project_status: ProjectStatus = ProjectStatus.CREATING
    outdated_reason: Optional[str] = None
    index_snapshot: Optional[str] = None
    last_request_id: Optional[UUID] = None
    sections: List[SectionRecord] = field(default_factory=list)
    questions: Dict[UUID, QuestionRecord] = field(default_factory=dict)


@dataclass
class RequestRecord:
    request_id: UUID
    request_type: RequestType
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
    progress: Optional[float] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class MemoryStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._documents: Dict[UUID, DocumentRecord] = {}
        self._projects: Dict[UUID, ProjectRecord] = {}
        self._answers: Dict[Tuple[UUID, UUID], AnswerRecord] = {}
        self._requests: Dict[UUID, RequestRecord] = {}

    def create_request(self, request_id: UUID, request_type: RequestType) -> RequestRecord:
        with self._lock:
            now = now_utc()
            record = RequestRecord(
                request_id=request_id,
                request_type=request_type,
                status=RequestStatus.PENDING,
                created_at=now,
                updated_at=now,
                progress=0.0,
            )
            self._requests[request_id] = record
            return record

    def get_request(self, request_id: UUID) -> Optional[RequestRecord]:
        with self._lock:
            return self._requests.get(request_id)

    def update_request(
        self,
        request_id: UUID,
        *,
        status: Optional[RequestStatus] = None,
        progress: Optional[float] = None,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[RequestRecord]:
        with self._lock:
            record = self._requests.get(request_id)
            if record is None:
                return None
            if status is not None:
                record.status = status
            if progress is not None:
                record.progress = progress
            if error_message is not None:
                record.error_message = error_message
            if result is not None:
                record.result = result
            record.updated_at = now_utc()
            return record

    def create_document(
        self,
        document_id: UUID,
        *,
        filename: str,
        content: Optional[str],
        mime_type: Optional[str],
        eligible_for_all_docs: bool,
    ) -> DocumentRecord:
        with self._lock:
            content_hash = sha256_text(content or filename)
            record = DocumentRecord(
                document_id=document_id,
                filename=filename,
                mime_type=mime_type,
                eligible_for_all_docs=eligible_for_all_docs,
                content_hash=content_hash,
                created_at=now_utc(),
            )
            self._documents[document_id] = record
            return record

    def get_document(self, document_id: UUID) -> Optional[DocumentRecord]:
        with self._lock:
            return self._documents.get(document_id)

    def set_document_indexed(
        self,
        document_id: UUID,
        *,
        chunks: List[ChunkRecord],
    ) -> Optional[DocumentRecord]:
        with self._lock:
            record = self._documents.get(document_id)
            if record is None:
                return None
            record.chunks = chunks
            record.indexed_at = now_utc()
            record.ingestion_status = "INDEXED"
            return record

    def iter_indexed_docs_for_all_docs(self) -> List[DocumentRecord]:
        with self._lock:
            docs = [
                d
                for d in self._documents.values()
                if d.ingestion_status == "INDEXED" and d.eligible_for_all_docs
            ]
            docs.sort(key=lambda d: str(d.document_id))
            return docs

    def iter_indexed_docs_for_subset(self, document_ids: Iterable[UUID]) -> List[DocumentRecord]:
        with self._lock:
            selected = []
            for doc_id in document_ids:
                d = self._documents.get(doc_id)
                if d is None:
                    continue
                if d.ingestion_status != "INDEXED":
                    continue
                selected.append(d)
            selected.sort(key=lambda d: str(d.document_id))
            return selected

    def corpus_signature_all_docs(self) -> str:
        docs = self.iter_indexed_docs_for_all_docs()
        payload = [{"document_id": str(d.document_id), "content_hash": d.content_hash} for d in docs]
        return sha256_json(payload)

    def corpus_signature_subset(self, document_ids: List[UUID]) -> str:
        docs = self.iter_indexed_docs_for_subset(document_ids)
        payload = [{"document_id": str(d.document_id), "content_hash": d.content_hash} for d in docs]
        return sha256_json(payload)

    def create_project(
        self,
        project_id: UUID,
        *,
        project_name: str,
        scope_type: ScopeType,
        scope_document_ids: List[UUID],
        request_id: UUID,
    ) -> ProjectRecord:
        with self._lock:
            record = ProjectRecord(
                project_id=project_id,
                project_name=project_name,
                scope_type=scope_type,
                scope_document_ids=scope_document_ids,
                created_at=now_utc(),
                project_status=ProjectStatus.CREATING,
                last_request_id=request_id,
            )
            self._projects[project_id] = record
            return record

    def get_project(self, project_id: UUID) -> Optional[ProjectRecord]:
        with self._lock:
            return self._projects.get(project_id)

    def update_project(
        self,
        project_id: UUID,
        *,
        project_status: Optional[ProjectStatus] = None,
        outdated_reason: Optional[str] = None,
        index_snapshot: Optional[str] = None,
        scope_type: Optional[ScopeType] = None,
        scope_document_ids: Optional[List[UUID]] = None,
        last_request_id: Optional[UUID] = None,
        sections: Optional[List[SectionRecord]] = None,
        questions: Optional[Dict[UUID, QuestionRecord]] = None,
    ) -> Optional[ProjectRecord]:
        with self._lock:
            record = self._projects.get(project_id)
            if record is None:
                return None
            if project_status is not None:
                record.project_status = project_status
            if outdated_reason is not None:
                record.outdated_reason = outdated_reason
            if index_snapshot is not None:
                record.index_snapshot = index_snapshot
            if scope_type is not None:
                record.scope_type = scope_type
            if scope_document_ids is not None:
                record.scope_document_ids = scope_document_ids
            if last_request_id is not None:
                record.last_request_id = last_request_id
            if sections is not None:
                record.sections = sections
            if questions is not None:
                record.questions = questions
            return record

    def list_projects(self) -> List[ProjectRecord]:
        with self._lock:
            items = list(self._projects.values())
            items.sort(key=lambda p: str(p.project_id))
            return items

    def get_or_create_answer(self, answer_id: UUID, *, project_id: UUID, question_id: UUID) -> AnswerRecord:
        key = (project_id, question_id)
        with self._lock:
            existing = self._answers.get(key)
            if existing is not None:
                return existing
            record = AnswerRecord(
                answer_id=answer_id,
                project_id=project_id,
                question_id=question_id,
                answer_status=AnswerStatus.DRAFT,
            )
            self._answers[key] = record
            return record

    def get_answer(self, *, project_id: UUID, question_id: UUID) -> Optional[AnswerRecord]:
        with self._lock:
            return self._answers.get((project_id, question_id))

    def put_ai_answer_version(
        self,
        *,
        project_id: UUID,
        question_id: UUID,
        answer_version: AnswerVersionRecord,
    ) -> AnswerRecord:
        key = (project_id, question_id)
        with self._lock:
            record = self._answers.get(key)
            if record is None:
                raise KeyError("answer_missing")
            record.ai_versions.append(answer_version)
            record.answer_status = AnswerStatus.DRAFT
            return record

    def put_manual_answer_version(
        self,
        *,
        project_id: UUID,
        question_id: UUID,
        manual_version: ManualAnswerVersionRecord,
    ) -> AnswerRecord:
        key = (project_id, question_id)
        with self._lock:
            record = self._answers.get(key)
            if record is None:
                raise KeyError("answer_missing")
            record.manual_versions.append(manual_version)
            record.answer_status = AnswerStatus.MANUAL_UPDATED
            return record

    def set_answer_status(self, *, project_id: UUID, question_id: UUID, status: AnswerStatus) -> Optional[AnswerRecord]:
        key = (project_id, question_id)
        with self._lock:
            record = self._answers.get(key)
            if record is None:
                return None
            record.answer_status = status
            return record

    def all_answers_for_project(self, project_id: UUID) -> List[AnswerRecord]:
        with self._lock:
            items = [a for a in self._answers.values() if a.project_id == project_id]
            items.sort(key=lambda a: str(a.question_id))
            return items


STORE = MemoryStore()


from __future__ import annotations

from enum import Enum


class ScopeType(str, Enum):
    ALL_DOCS = "ALL_DOCS"
    SUBSET = "SUBSET"


class ProjectStatus(str, Enum):
    CREATING = "CREATING"
    READY = "READY"
    OUTDATED = "OUTDATED"
    ERROR = "ERROR"


class AnswerStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    MANUAL_UPDATED = "MANUAL_UPDATED"
    MISSING_DATA = "MISSING_DATA"


class RequestStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class RequestType(str, Enum):
    INDEX_DOCUMENT = "INDEX_DOCUMENT"
    CREATE_PROJECT = "CREATE_PROJECT"
    UPDATE_PROJECT = "UPDATE_PROJECT"
    GENERATE_ALL_ANSWERS = "GENERATE_ALL_ANSWERS"


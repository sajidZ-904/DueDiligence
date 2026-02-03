Backend (FastAPI)

Purpose
This folder holds the backend service implementation for the Questionnaire
Agent. It uses a minimal FastAPI setup and serves as the starting point for
implementation.

Quick Start
1) Install dependencies

Windows:
```powershell
cd c:\DueDiligence\backend
py -m pip install -r requirements.txt
```

Ubuntu (and most Linux distros):
```bash
cd backend
python3 -m pip install -r requirements.txt
```

macOS:
```bash
cd backend
python3 -m pip install -r requirements.txt
```

2) Run the API

```powershell
py -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Ubuntu/macOS equivalent:
```bash
python3 -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

3) Open Swagger UI
- Swagger UI: http://127.0.0.1:8000/docs
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json
- Health check: http://127.0.0.1:8000/health

Notes
- The current implementation uses in-memory storage; restarting the server clears documents, projects, answers, and request IDs.
- All async endpoints return a `request_id`. Use `GET /get-request-status` to poll until `SUCCEEDED` or `FAILED`.

Module Layout
- src/api/        HTTP route handlers for the listed endpoints
- src/models/     Data models mirroring the spec data structures
- src/services/   Core business logic (project, answers, ingestion, evaluation)
- src/indexing/   Multi-layer indexing pipeline and chunking
- src/storage/    Persistence layer (DB, vector store, object storage)
- src/workers/    Async/background processing and request status tracking
- src/utils/      Shared helpers, validation, and constants

API Endpoints
- POST /create-project-async
- POST /generate-single-answer
- POST /generate-all-answers
- POST /update-project-async
- POST /update-answer
- GET /get-project-info
- GET /get-project-status
- POST /index-document-async
- GET /get-request-status

Swagger Test Flow (End-to-End)
1) POST /index-document-async
Example body:
```json
{
  "filename": "ref1.txt",
  "content": "Revenue was $10M in 2025. Net income was $2M.",
  "eligible_for_all_docs": true
}
```
Copy the returned `request_id`.

2) GET /get-request-status
- Paste `request_id` from step 1 and execute until `status` becomes `SUCCEEDED`.

3) POST /create-project-async
Example body:
```json
{
  "project_name": "Demo Project",
  "scope_type": "ALL_DOCS",
  "questions": ["What was revenue?", "What was net income?"]
}
```
Copy the returned `project_id` and `request_id`, then poll request status until `SUCCEEDED`.

4) GET /get-project-info
- Use `project_id` and copy any `question_id` from the response.

5) POST /generate-single-answer
```json
{
  "project_id": "PASTE_PROJECT_ID",
  "question_id": "PASTE_QUESTION_ID"
}
```

6) POST /generate-all-answers (optional)
- Returns a `request_id`. Poll `GET /get-request-status` until `SUCCEEDED`.

Smoke Test Script (Optional)
This repo includes a small script that exercises indexing, project creation, and single-answer generation via the FastAPI TestClient.

1) Install dev dependency:
```powershell
py -m pip install -r requirements-dev.txt
```

2) Run:
```powershell
py smoke_test.py
```

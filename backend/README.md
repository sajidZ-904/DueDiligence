Backend (FastAPI)

Purpose
This folder holds the backend service implementation for the Questionnaire
Agent. It uses a minimal FastAPI setup and serves as the starting point for
implementation.

Quick Start
1) Install dependencies

Windows:
```powershell
cd backend
py -m venv env
.\env\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Ubuntu (and most Linux distros):
```bash
cd backend
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```


2) Run the API

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
- For local development, you can ingest files from the repo `data/` folder by passing `file_path` / `questionnaire_file_path`. Paths are restricted to the `data/` directory.
- Environment variables can be set in `backend/.env` and are loaded automatically when the API starts.

AI (Transformers + LangChain, Optional)
By default, answer generation uses a lightweight heuristic method. You can enable an AI RAG mode (retrieval + generation) powered by Hugging Face Transformers and LangChain.

1) Install AI dependencies
```bash
pip install -r requirements.txt
```

2) Enable RAG mode
Windows PowerShell:
```bash
$env:QA_AI_MODE="rag"
py -m uvicorn app:app --reload
```

Ubuntu/macOS:
```bash
export QA_AI_MODE=rag
uvicorn app:app --reload
```

Notes
- The first run will download the Hugging Face models (may take a while).
- You can override models with `QA_EMBED_MODEL` and `QA_GEN_MODEL`.
- `QA_GEN_MODEL` must be a Hugging Face model id (for Transformers), not an OpenAI-style name like `gpt-*`.
- Debugging: `GET /ai-status` returns whether AI mode is enabled and whether required libraries can load.
- Windows note: if `torch` fails to import with a DLL error (e.g. WinError 1114), install Microsoft Visual C++ Redistributable (x64) and restart.

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

Using a file from the repo `data/` folder (recommended for testing the provided PDFs):
```json
{
  "filename": "20260110_MiniMax_Global_Offering_Prospectus.pdf",
  "file_path": "20260110_MiniMax_Global_Offering_Prospectus.pdf",
  "eligible_for_all_docs": true
}
```

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

Create a project using the provided questionnaire PDF in `data/`:
```json
{
  "project_name": "ILPA Project",
  "scope_type": "ALL_DOCS",
  "questionnaire_file_path": "ILPA_Due_Diligence_Questionnaire_v1.2.pdf"
}
```

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
This repo includes small scripts that exercise indexing, project creation, and answer generation via the FastAPI TestClient.


1) Run the lightweight smoke test (fast, uses inline text):
```powershell
python3 smoke_test.py
```

2) Run the data-folder smoke test (indexes files in `../data/`):
```powershell
python3 smoke_test_file.py
```

Environment variables (optional)
- `QA_SMOKE_MAX_FILES`: limit how many files to index (0 = no limit)
- `QA_SMOKE_INDEX_TIMEOUT_S`: per-file indexing timeout (seconds)
- `QA_SMOKE_PROJECT_TIMEOUT_S`: project creation timeout (seconds)

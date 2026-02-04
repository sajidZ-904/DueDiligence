Frontend Skeleton (Minimal Framework)

Purpose
This folder holds the frontend implementation for the Questionnaire Agent.
It uses a minimal Vite + React setup and serves as the starting point for
implementation.

Quick Start
1) Install dependencies

Windows:
```powershell
cd frontend
npm install
```

Ubuntu (and most Linux distros):
```bash
cd frontend
npm install
```

2) Configure backend URL (optional)
If your backend is not running at `http://127.0.0.1:8000`, create `frontend/.env`:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_API_TIMEOUT_MS=120000
```
You can copy from `.env.example`.

3) Run the dev server
```bash
npm run dev
```

4) Open the app
Vite prints the local URL (typically http://localhost:5173).
The home page shows `Backend health: ok` when the backend is running.

Backend prerequisite
- Start the backend first (default: http://127.0.0.1:8000).

Testing with the data folder
1) Start the backend and ensure the repo `data/` folder contains PDFs.
2) Start the frontend and open the app.
3) In the "Data Folder Test" section:
   - Click "Refresh data files" to fetch a list of files in `../data/`
   - Click "Index all data files" to index every file via `file_path`
   - Click "Create ILPA project" to create a project using the ILPA questionnaire PDF (if present)
   - Click "Generate first answer" to generate one sample answer

Planned Screens
- Project List: view all projects and their status
- Project Detail: sections, questions, and answers with review actions
- Question Review: approve/reject/manual edit with citations and confidence
- Document Management: upload, scope, and indexing status
- Evaluation Report: compare AI vs human answers with similarity scores
- Request Status: async task tracking and error details

Planned UI Modules
- src/pages/       Page-level containers
- src/components/  Reusable UI components
- src/services/    API clients and request helpers
- src/state/       Client state management

Build
```bash
npm run build
```

Preview production build
```bash
npm run preview
```

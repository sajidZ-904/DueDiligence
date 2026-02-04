import os
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional, Tuple

from fastapi.testclient import TestClient

from app import app


def wait_for_request(client: TestClient, request_id: str, timeout_s: float) -> str:
    elapsed = 0.0
    while elapsed < timeout_s:
        res = client.get("/get-request-status", params={"request_id": request_id})
        res.raise_for_status()
        status = res.json()["status"]
        if status in ("SUCCEEDED", "FAILED"):
            return status
        sleep(0.05)
        elapsed += 0.05
    return "TIMEOUT"


def data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def list_data_files() -> List[Path]:
    base = data_dir()
    if not base.exists():
        return []
    allowed = {".pdf", ".docx", ".txt", ".md"}
    files = [p for p in base.iterdir() if p.is_file() and p.suffix.lower() in allowed]
    files.sort(key=lambda p: p.name.lower())
    return files


def index_data_files(client: TestClient, *, timeout_s: float, max_files: int) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    files = list_data_files()
    if max_files > 0:
        files = files[:max_files]
    for idx, f in enumerate(files, start=1):
        print(f"Indexing [{idx}/{len(files)}]: {f.name}", flush=True)
        res = client.post(
            "/index-document-async",
            json={
                "filename": f.name,
                "file_path": f.name,
                "eligible_for_all_docs": True,
            },
        )
        res.raise_for_status()
        request_id = res.json()["request_id"]
        status = wait_for_request(client, request_id, timeout_s=timeout_s)
        print(f"Indexed: {f.name} -> {status}", flush=True)
        results.append({"filename": f.name, "request_id": request_id, "status": status})
    return results


def create_project_from_questionnaire(client: TestClient, *, timeout_s: float) -> Tuple[str, str]:
    files = list_data_files()
    questionnaire = next((f for f in files if "ilpa_due_diligence_questionnaire" in f.name.lower()), None)
    payload: Dict[str, object] = {"project_name": "ILPA Data Folder Project", "scope_type": "ALL_DOCS"}
    if questionnaire:
        payload["questionnaire_file_path"] = questionnaire.name
    else:
        payload["questions"] = ["What are the key financial highlights?", "What are the main risks?"]

    res = client.post("/create-project-async", json=payload)
    res.raise_for_status()
    project_id = res.json()["project_id"]
    request_id = res.json()["request_id"]
    status = wait_for_request(client, request_id, timeout_s=timeout_s)
    return project_id, status


def main() -> None:
    client = TestClient(app)

    health = client.get("/health")
    health.raise_for_status()

    max_files = int(os.getenv("QA_SMOKE_MAX_FILES", "0"))
    index_timeout_s = float(os.getenv("QA_SMOKE_INDEX_TIMEOUT_S", "240"))
    project_timeout_s = float(os.getenv("QA_SMOKE_PROJECT_TIMEOUT_S", "240"))

    index_results = index_data_files(client, timeout_s=index_timeout_s, max_files=max_files)
    failures = [r for r in index_results if r["status"] != "SUCCEEDED"]

    project_id, project_status = create_project_from_questionnaire(client, timeout_s=project_timeout_s)

    info = client.get("/get-project-info", params={"project_id": project_id})
    info.raise_for_status()
    sections = info.json()["sections"]
    first_qid: Optional[str] = None
    if sections and sections[0]["questions"]:
        first_qid = sections[0]["questions"][0]["question_id"]

    answer_summary = None
    if first_qid:
        ans = client.post("/generate-single-answer", json={"project_id": project_id, "question_id": first_qid})
        ans.raise_for_status()
        answer_summary = {
            "answer_status": ans.json()["answer"]["answer_status"],
            "confidence": ans.json()["answer"]["confidence"],
            "citation_count": len(ans.json()["answer"]["citations"]),
        }

    print(
        {
            "health": health.json(),
            "data_dir": str(data_dir()),
            "indexed_files": len(index_results),
            "index_failures": failures,
            "create_project_status": project_status,
            "project_id": project_id,
            "question_count": sum(len(s["questions"]) for s in sections),
            "first_answer": answer_summary,
        }
    )


if __name__ == "__main__":
    main()


from time import sleep

from fastapi.testclient import TestClient

from app import app


def wait_for_request(client: TestClient, request_id: str, timeout_s: float = 2.0) -> str:
    elapsed = 0.0
    while elapsed < timeout_s:
        res = client.get("/get-request-status", params={"request_id": request_id})
        res.raise_for_status()
        status = res.json()["status"]
        if status in ("SUCCEEDED", "FAILED"):
            return status
        sleep(0.02)
        elapsed += 0.02
    return "TIMEOUT"


def main() -> None:
    client = TestClient(app)

    res = client.get("/health")
    res.raise_for_status()

    index = client.post(
        "/index-document-async",
        json={
            "filename": "ref1.txt",
            "content": "Revenue was $10M in 2025. Net income was $2M.",
            "eligible_for_all_docs": True,
        },
    )
    index.raise_for_status()
    index_status = wait_for_request(client, index.json()["request_id"])

    project = client.post(
        "/create-project-async",
        json={
            "project_name": "Demo",
            "scope_type": "ALL_DOCS",
            "questions": ["What was revenue?", "What was net income?"],
        },
    )
    project.raise_for_status()
    project_status = wait_for_request(client, project.json()["request_id"])

    info = client.get("/get-project-info", params={"project_id": project.json()["project_id"]})
    info.raise_for_status()
    sections = info.json()["sections"]
    qid = sections[0]["questions"][0]["question_id"]

    ans = client.post(
        "/generate-single-answer",
        json={"project_id": project.json()["project_id"], "question_id": qid},
    )
    ans.raise_for_status()

    print(
        {
            "health": res.json(),
            "index_request_status": index_status,
            "create_project_request_status": project_status,
            "single_answer_status": ans.json()["answer"]["answer_status"],
            "single_answer_confidence": ans.json()["answer"]["confidence"],
        }
    )


if __name__ == "__main__":
    main()

import { useEffect, useState } from "react";

import {
  API_BASE_URL,
  createProjectAsync,
  generateSingleAnswerAsync,
  getHealth,
  getProjectFirstQuestion,
  getRequestStatus,
  indexDocumentAsync,
  listDataFiles,
  sleepMs,
} from "./services/api";

export default function App() {
  const [health, setHealth] = useState<string>("loading");
  const [error, setError] = useState<string | null>(null);
  const [dataFiles, setDataFiles] = useState<string[]>([]);
  const [indexResults, setIndexResults] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectStatus, setProjectStatus] = useState<string | null>(null);
  const [answerText, setAnswerText] = useState<string | null>(null);
  const [genStatus, setGenStatus] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((r) => {
        if (cancelled) return;
        setHealth(r.status);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
        setHealth("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function refreshDataFiles() {
    setError(null);
    const res = await listDataFiles();
    setDataFiles(res.files);
  }

  async function waitForRequest(requestId: string, timeoutMs: number) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const s = await getRequestStatus(requestId);
      if (s.status === "SUCCEEDED" || s.status === "FAILED") return s;
      await sleepMs(200);
    }
    throw new Error(`Request timed out: ${requestId}`);
  }

  async function indexAllDataFiles() {
    setBusy(true);
    setError(null);
    setIndexResults({});
    setAnswerText(null);
    try {
      const files = dataFiles.length ? dataFiles : (await listDataFiles()).files;
      setDataFiles(files);
      for (const filename of files) {
        setIndexResults((prev) => ({ ...prev, [filename]: "INDEXING" }));
        const start = await indexDocumentAsync({
          filename,
          file_path: filename,
          eligible_for_all_docs: true,
        });
        const done = await waitForRequest(start.request_id, 5 * 60 * 1000);
        setIndexResults((prev) => ({ ...prev, [filename]: done.status }));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function createIlpaProject() {
    setBusy(true);
    setError(null);
    setProjectId(null);
    setProjectStatus(null);
    setAnswerText(null);
    try {
      const files = dataFiles.length ? dataFiles : (await listDataFiles()).files;
      setDataFiles(files);
      const ilpa = files.find((f) => f.toLowerCase().includes("ilpa_due_diligence_questionnaire"));
      const req = await createProjectAsync(
        ilpa
          ? { project_name: "ILPA Project", scope_type: "ALL_DOCS", questionnaire_file_path: ilpa }
          : { project_name: "Demo Project", scope_type: "ALL_DOCS", questions: ["What are the key risks?"] },
      );
      setProjectId(req.project_id);
      const done = await waitForRequest(req.request_id, 5 * 60 * 1000);
      setProjectStatus(done.status);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function generateFirstAnswer() {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    setAnswerText(null);
    setGenStatus("STARTING");
    try {
      setGenStatus("LOADING_PROJECT_INFO");
      const firstQ = await getProjectFirstQuestion(projectId);
      setGenStatus("REQUESTING_GENERATION");
      const started = await generateSingleAnswerAsync({ project_id: projectId, question_id: firstQ.question_id });
      setGenStatus(`REQUESTED (${started.request_id})`);
      setGenStatus(`POLLING (${started.request_id})`);
      const done = await waitForRequest(started.request_id, 15 * 60 * 1000);
      setGenStatus(done.status);
      const answer = (done.result as any)?.answer as any;
      if (answer?.answer_text) {
        setAnswerText(String(answer.answer_text));
      } else {
        setAnswerText("Answer generation completed, but no answer payload was returned.");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setGenStatus("ERROR");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Questionnaire Agent</h1>
      <p>Project skeleton ready for implementation.</p>
      <p>API base URL: {API_BASE_URL}</p>
      <p>Backend health: {health}</p>
      <hr />
      <h2>Data Folder Test</h2>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button onClick={refreshDataFiles} disabled={busy}>
          Refresh data files
        </button>
        <button onClick={indexAllDataFiles} disabled={busy}>
          Index all data files
        </button>
        <button onClick={createIlpaProject} disabled={busy}>
          Create ILPA project
        </button>
        <button onClick={generateFirstAnswer} disabled={busy || !projectId}>
          Generate first answer
        </button>
      </div>

      <p>Found {dataFiles.length} files in /data</p>
      {dataFiles.length ? (
        <ul>
          {dataFiles.map((f) => (
            <li key={f}>
              {f} {indexResults[f] ? `— ${indexResults[f]}` : ""}
            </li>
          ))}
        </ul>
      ) : null}

      {projectId ? (
        <p>
          Project: {projectId} {projectStatus ? `— ${projectStatus}` : ""}
        </p>
      ) : null}

      {genStatus ? <p>Generate status: {genStatus}</p> : null}

      {answerText ? (
        <div>
          <h3>First Answer</h3>
          <pre style={{ whiteSpace: "pre-wrap" }}>{answerText}</pre>
        </div>
      ) : null}
      {error ? <pre>{error}</pre> : null}
    </main>
  );
}

const envBaseUrl = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined;
const envTimeoutMs = (import.meta as any).env?.VITE_API_TIMEOUT_MS as string | undefined;

export const API_BASE_URL = (envBaseUrl || "http://127.0.0.1:8000").replace(/\/+$/, "");
export const API_TIMEOUT_MS = Number(envTimeoutMs || "30000");

export type HealthResponse = {
  status: string;
};

export type DataFilesResponse = {
  files: string[];
};

export type IndexDocumentAsyncRequest = {
  filename: string;
  content?: string;
  file_path?: string;
  eligible_for_all_docs?: boolean;
  mime_type?: string;
};

export type IndexDocumentAsyncResponse = {
  request_id: string;
  document_id: string;
};

export type RequestStatusResponse = {
  request_id: string;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";
  request_type: string;
  progress?: number | null;
  error_message?: string | null;
  result?: Record<string, unknown> | null;
};

export type CreateProjectAsyncRequest = {
  project_name: string;
  scope_type: "ALL_DOCS" | "SUBSET";
  scope_document_ids?: string[];
  questionnaire_text?: string;
  questionnaire_file_path?: string;
  questions?: string[];
};

export type CreateProjectAsyncResponse = {
  request_id: string;
  project_id: string;
};

export type ProjectInfoResponse = {
  project_id: string;
  project_name: string;
  scope_type: string;
  project_status: string;
  sections: Array<{
    section_id: string;
    title: string;
    order: number;
    questions: Array<{ question_id: string; prompt: string; order: number }>;
  }>;
};

export type FirstQuestionResponse = {
  question_id: string;
  prompt: string;
};

export type GenerateSingleAnswerRequest = {
  project_id: string;
  question_id: string;
};

export type GenerateSingleAnswerResponse = {
  answer: {
    question_id: string;
    answer_status: string;
    answerable: boolean;
    answer_text: string;
    confidence: number;
    citations: Array<unknown>;
  };
};

export type GenerateSingleAnswerAsyncResponse = {
  request_id: string;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = Number.isFinite(API_TIMEOUT_MS) && API_TIMEOUT_MS > 0 ? API_TIMEOUT_MS : 30000;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { ...init, signal: controller.signal });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(
        `${init?.method || "GET"} ${path} failed: ${res.status} ${res.statusText}${text ? `\n${text}` : ""}`,
      );
    }
    return (await res.json()) as T;
  } catch (e: unknown) {
    const err = e as any;
    if (controller.signal.aborted) {
      throw new Error(
        `${init?.method || "GET"} ${path} timed out after ${timeoutMs}ms. ` +
          `Check the backend is running and VITE_API_BASE_URL is correct (${API_BASE_URL}).`,
      );
    }
    throw e;
  } finally {
    clearTimeout(timeout);
  }
}

export async function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health", { method: "GET" });
}

export async function listDataFiles(): Promise<DataFilesResponse> {
  return requestJson<DataFilesResponse>("/list-data-files", { method: "GET" });
}

export async function indexDocumentAsync(body: IndexDocumentAsyncRequest): Promise<IndexDocumentAsyncResponse> {
  return requestJson<IndexDocumentAsyncResponse>("/index-document-async", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getRequestStatus(requestId: string): Promise<RequestStatusResponse> {
  const q = new URLSearchParams({ request_id: requestId });
  return requestJson<RequestStatusResponse>(`/get-request-status?${q.toString()}`, { method: "GET" });
}

export async function createProjectAsync(body: CreateProjectAsyncRequest): Promise<CreateProjectAsyncResponse> {
  return requestJson<CreateProjectAsyncResponse>("/create-project-async", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getProjectInfo(projectId: string): Promise<ProjectInfoResponse> {
  const q = new URLSearchParams({ project_id: projectId, include_answers: "false" });
  return requestJson<ProjectInfoResponse>(`/get-project-info?${q.toString()}`, { method: "GET" });
}

export async function getProjectFirstQuestion(projectId: string): Promise<FirstQuestionResponse> {
  const q = new URLSearchParams({ project_id: projectId });
  return requestJson<FirstQuestionResponse>(`/get-project-first-question?${q.toString()}`, { method: "GET" });
}

export async function generateSingleAnswer(body: GenerateSingleAnswerRequest): Promise<GenerateSingleAnswerResponse> {
  return requestJson<GenerateSingleAnswerResponse>("/generate-single-answer", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function generateSingleAnswerAsync(body: GenerateSingleAnswerRequest): Promise<GenerateSingleAnswerAsyncResponse> {
  return requestJson<GenerateSingleAnswerAsyncResponse>("/generate-single-answer-async", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

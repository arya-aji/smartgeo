import type {
  LoginRequest,
  LoginResponse,
  User,
  PresignRequest,
  PresignResponse,
  CompleteUploadRequest,
  CompleteUploadResponse,
  MapDocumentSummary,
  MapDocumentDetail,
  PaginationEnvelope,
  DashboardResponse,
  Job,
  CreateOperatorRequest,
  UpdateOperatorRequest,
  OperatorResponse,
  WssTarget,
  ImportTargetsRequest,
  ImportTargetsResponse,
  ReviewAcceptRequest,
  ReviewManualRequest,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("wss_token");
  }
  return null;
}

async function fetchJson<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  return fetchJson<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function me(): Promise<User> {
  return fetchJson<User>("/api/auth/me");
}

export async function presignUpload(payload: PresignRequest): Promise<PresignResponse> {
  return fetchJson<PresignResponse>("/api/uploads/presign", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function completeUpload(payload: CompleteUploadRequest): Promise<CompleteUploadResponse> {
  return fetchJson<CompleteUploadResponse>("/api/uploads/complete", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getDashboard(): Promise<DashboardResponse> {
  return fetchJson<DashboardResponse>("/api/dashboard");
}

export async function getMaps(params: {
  status?: string;
  q?: string;
  page?: number;
  page_size?: number;
  mine?: boolean;
}): Promise<PaginationEnvelope<MapDocumentSummary>> {
  const sp = new URLSearchParams();
  if (params.status) sp.set("status", params.status);
  if (params.q) sp.set("q", params.q);
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  if (params.mine) sp.set("mine", "true");
  return fetchJson<PaginationEnvelope<MapDocumentSummary>>(`/api/maps?${sp.toString()}`);
}

export async function getMap(id: string): Promise<MapDocumentDetail> {
  return fetchJson<MapDocumentDetail>(`/api/maps/${id}`);
}

export async function retryJob(id: string): Promise<Job> {
  return fetchJson<Job>(`/api/jobs/${id}/retry`, { method: "POST" });
}

export async function getReviewQueue(params: {
  page?: number;
  page_size?: number;
}): Promise<PaginationEnvelope<MapDocumentSummary>> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  return fetchJson<PaginationEnvelope<MapDocumentSummary>>(`/api/review?${sp.toString()}`);
}

export async function acceptReview(id: string, payload?: ReviewAcceptRequest): Promise<MapDocumentDetail> {
  return fetchJson<MapDocumentDetail>(`/api/review/${id}/accept`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export async function manualReview(id: string, payload: ReviewManualRequest): Promise<MapDocumentDetail> {
  return fetchJson<MapDocumentDetail>(`/api/review/${id}/manual-id`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getOperators(): Promise<OperatorResponse[]> {
  return fetchJson<OperatorResponse[]>("/api/operators");
}

export async function createOperator(payload: CreateOperatorRequest): Promise<OperatorResponse> {
  return fetchJson<OperatorResponse>("/api/operators", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateOperator(id: string, payload: UpdateOperatorRequest): Promise<OperatorResponse> {
  return fetchJson<OperatorResponse>(`/api/operators/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function getTargets(params: {
  status?: string;
  q?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginationEnvelope<WssTarget>> {
  const sp = new URLSearchParams();
  if (params.status) sp.set("status", params.status);
  if (params.q) sp.set("q", params.q);
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  return fetchJson<PaginationEnvelope<WssTarget>>(`/api/targets?${sp.toString()}`);
}

export async function importTargets(payload: ImportTargetsRequest): Promise<ImportTargetsResponse> {
  return fetchJson<ImportTargetsResponse>("/api/targets/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteTarget(id: string): Promise<{ deleted: boolean }> {
  return fetchJson<{ deleted: boolean }>(`/api/targets/${id}`, { method: "DELETE" });
}

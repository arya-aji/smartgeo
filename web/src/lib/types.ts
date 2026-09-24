export type Role = "OPERATOR" | "ADMIN";

export interface User {
  id: string;
  name: string;
  username: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export type ProcessingStatus =
  | "UPLOADING"
  | "UPLOADED"
  | "QUEUED"
  | "DETECTING_PAPER"
  | "CORRECTING_PERSPECTIVE"
  | "DETECTING_ORIENTATION"
  | "ENHANCING"
  | "UPSCALING"
  | "DETECTING_TEXT"
  | "RECOGNIZING_ID"
  | "VALIDATING_ID"
  | "FINALIZING"
  | "COMPLETED"
  | "NEEDS_REVIEW"
  | "FAILED";

export interface MapDocumentSummary {
  id: string;
  idsubsls: string;
  processing_status: ProcessingStatus;
  quality_score: number | null;
  ocr_confidence: number | null;
  paper_confidence: number | null;
  orientation: number | null;
  upscaled: boolean;
  upscale_factor: number | null;
  created_at: string;
  processed_at: string | null;
  uploaded_by: string;
  uploaded_by_name: string;
  preview_url: string | null;
  review_reason: string | null;
}

export interface OcrCandidate {
  idsubsls: string;
  confidence: number;
}

export interface MapDocumentDetail extends MapDocumentSummary {
  ocr_raw: string | null;
  ocr_candidates: OcrCandidate[] | null;
  corners: Record<string, unknown> | null;
  source_width: number | null;
  source_height: number | null;
  final_width: number | null;
  final_height: number | null;
  processing_attempts: number;
  error_message: string | null;
  original_filename: string;
  content_type: string;
  file_size: number;
  original_url: string | null;
  final_url: string | null;
  review_url: string | null;
}

export interface PaginationEnvelope<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface PresignRequest {
  filename: string;
  content_type: string;
  size: number;
  target_id: string | null;
}

export interface PresignResponse {
  map_document_id: string;
  object_key: string;
  upload_url: string;
  method: string;
  headers: Record<string, string>;
  expires_in: number;
}

export interface CompleteUploadRequest {
  map_document_id: string;
  width: number;
  height: number;
  file_size: number;
}

export interface CompleteUploadResponse {
  map_document: MapDocumentDetail;
  job: Job;
}

export interface Job {
  id: string;
  map_document_id: string;
  job_type: string;
  status: string;
  attempt: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface DashboardGlobal {
  total: number;
  completed: number;
  processing: number;
  queued: number;
  review: number;
  failed: number;
}

export interface DashboardQueue {
  cv_pending: number;
  cv_processing: number;
  geo_pending: number;
}

export interface DashboardOperator {
  id: string;
  name: string;
  username: string;
  completed: number;
  assigned: number;
  review: number;
  failed: number;
}

export interface DashboardResponse {
  global: DashboardGlobal;
  progress_percent: number;
  queue: DashboardQueue;
  operators: DashboardOperator[];
}

export interface CreateOperatorRequest {
  name: string;
  username: string;
  password: string;
  role: Role;
}

export interface UpdateOperatorRequest {
  name?: string;
  password?: string;
  is_active?: boolean;
  role?: Role;
}

export interface OperatorResponse extends User {
  completed: number;
  assigned: number;
}

export interface WssTarget {
  id: string;
  idsubsls: string;
  status: string;
  map_document_id: string | null;
  assigned_to: string | null;
  assigned_at: string | null;
  preview_url: string | null;
  final_url: string | null;
  download_url: string | null;
}

export interface ImportTargetsRequest {
  idsubsls: string[];
}

export interface ImportTargetsResponse {
  created: number;
  skipped: number;
  invalid: number;
}

export interface BatchClaimResponse {
  targets: WssTarget[];
  remaining: number;
}

export interface ReviewAcceptRequest {
  idsubsls?: string;
}

export interface ReviewManualRequest {
  idsubsls: string;
}

export interface ApiError {
  detail: string;
}

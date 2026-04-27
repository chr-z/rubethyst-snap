export type ProgressStatus =
  | "queued"
  | "extracting"
  | "downloading"
  | "merging"
  | "postprocessing"
  | "uploading"
  | "finished"
  | "error"
  | "retrying";

export interface FormatEntry {
  format_id: string;
  ext: string | null;
  height: number | null;
  width: number | null;
  fps: number | null;
  vcodec: string | null;
  acodec: string | null;
  tbr: number | null;
  vbr: number | null;
  abr: number | null;
  filesize: number | null;
  note: string | null;
}

export interface PreviewResponse {
  title: string;
  extractor: string;
  duration_seconds: number | null;
  thumbnail: string | null;
  uploader: string | null;
  is_live: boolean;
  was_live: boolean;
  formats: FormatEntry[];
}

export interface PlanInfo {
  name: "free" | "pro";
  max_duration_seconds: number;
  max_filesize_mb: number;
  max_height: number;
  concurrency: number;
  rate_per_hour: number;
  retention_hours: number;
  allowed_presets: string[];
}

export interface JobProgress {
  status: ProgressStatus;
  percent: number | null;
  downloaded_bytes: number | null;
  total_bytes: number | null;
  speed_bps: number | null;
  eta_seconds: number | null;
  message: string | null;
}

export interface JobResult {
  download_url: string;
  expires_at: string;
  filename: string;
  size_bytes: number;
  container: string;
}

export interface Job {
  id: string;
  url: string;
  preset: string;
  plan: "free" | "pro";
  identity: string;
  created_at: string;
  updated_at: string;
  retention_until: string | null;
  progress: JobProgress;
  title: string | null;
  duration_seconds: number | null;
  extractor: string | null;
  artifact_path: string | null;
  result: JobResult | null;
  error: string | null;
}

export interface SseProgressEvent {
  status: ProgressStatus;
  percent: number | null;
  downloaded_bytes: number | null;
  total_bytes: number | null;
  speed_bps: number | null;
  eta_seconds: number | null;
  message: string | null;
}

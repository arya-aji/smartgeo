import type { ProcessingStatus } from "@/lib/types";

const STATUS_STYLES: Record<ProcessingStatus, string> = {
  UPLOADING: "bg-sky-50 text-sky-700 ring-sky-600/20",
  UPLOADED: "bg-sky-50 text-sky-700 ring-sky-600/20",
  QUEUED: "bg-amber-50 text-amber-700 ring-amber-600/20",
  DETECTING_PAPER: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  CORRECTING_PERSPECTIVE: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  DETECTING_ORIENTATION: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  ENHANCING: "bg-violet-50 text-violet-700 ring-violet-600/20",
  UPSCALING: "bg-violet-50 text-violet-700 ring-violet-600/20",
  DETECTING_TEXT: "bg-violet-50 text-violet-700 ring-violet-600/20",
  RECOGNIZING_ID: "bg-violet-50 text-violet-700 ring-violet-600/20",
  VALIDATING_ID: "bg-violet-50 text-violet-700 ring-violet-600/20",
  FINALIZING: "bg-violet-50 text-violet-700 ring-violet-600/20",
  COMPLETED: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  NEEDS_REVIEW: "bg-rose-50 text-rose-700 ring-rose-600/20",
  FAILED: "bg-red-50 text-red-700 ring-red-600/20",
};

interface StatusPillProps {
  status: ProcessingStatus;
}

export default function StatusPill({ status }: StatusPillProps) {
  const style = STATUS_STYLES[status] || "bg-surface-100 text-surface-700 ring-surface-600/20";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}
    >
      {status}
    </span>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getMap, retryJob } from "@/lib/api";
import type { MapDocumentDetail } from "@/lib/types";
import StatusPill from "@/components/StatusPill";
import { formatDate, formatBytes, formatPercent } from "@/lib/format";
import { showToast } from "@/components/Toast";

export default function MapDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [doc, setDoc] = useState<MapDocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);

  const fetchDoc = async () => {
    setLoading(true);
    try {
      const res = await getMap(id);
      setDoc(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load map";
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDoc();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleRetry = async () => {
    if (!doc) return;
    setRetrying(true);
    try {
      await retryJob(doc.id);
      showToast("Retry initiated", "success");
      fetchDoc();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Retry failed";
      showToast(msg, "error");
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-1/3 animate-pulse rounded bg-surface-200" />
        <div className="h-64 animate-pulse rounded-lg bg-surface-200" />
        <div className="h-32 animate-pulse rounded-lg bg-surface-200" />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="rounded-lg border border-surface-200 bg-white p-8 text-center text-surface-500">
        Map not found
      </div>
    );
  }

  const imageUrl = doc.final_url || doc.review_url || doc.original_url || doc.preview_url;
  const ocrCandidates = doc.ocr_candidates ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push("/logs")}
            className="text-sm text-surface-500 hover:text-surface-900"
          >
            ← Back to Logs
          </button>
          <h1 className="mt-1 text-xl font-semibold text-surface-900">{doc.idsubsls}</h1>
        </div>
        <StatusPill status={doc.processing_status} />
      </div>

      {imageUrl && (
        <div className="rounded-lg border border-surface-200 bg-white p-4 shadow-sm">
          <img
            src={imageUrl}
            alt={`Map ${doc.idsubsls}`}
            className="max-h-[60vh] w-auto rounded object-contain"
          />
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-surface-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-surface-500">
            Metadata
          </h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-surface-500">Orientation</dt>
              <dd className="font-medium text-surface-900">{doc.orientation ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-surface-500">Dimensions</dt>
              <dd className="font-medium text-surface-900">
                {doc.source_width ?? "—"} × {doc.source_height ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-surface-500">Final dimensions</dt>
              <dd className="font-medium text-surface-900">
                {doc.final_width ?? "—"} × {doc.final_height ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-surface-500">Upscaled</dt>
              <dd className="font-medium text-surface-900">{doc.upscaled ? "Yes" : "No"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-surface-500">Upscale factor</dt>
              <dd className="font-medium text-surface-900">{doc.upscale_factor ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-surface-500">Attempts</dt>
              <dd className="font-medium text-surface-900">{doc.processing_attempts}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-surface-500">File size</dt>
              <dd className="font-medium text-surface-900">{formatBytes(doc.file_size)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-surface-500">Created</dt>
              <dd className="font-medium text-surface-900">{formatDate(doc.created_at)}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-lg border border-surface-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-surface-500">
            Confidences
          </h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-surface-500">Quality</dt>
              <dd className="font-medium text-surface-900">{formatPercent(doc.quality_score)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-surface-500">OCR</dt>
              <dd className="font-medium text-surface-900">{formatPercent(doc.ocr_confidence)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-surface-500">Paper</dt>
              <dd className="font-medium text-surface-900">{formatPercent(doc.paper_confidence)}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-lg border border-surface-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-surface-500">
            OCR
          </h2>
          <div className="mt-3 space-y-2 text-sm">
            <div>
              <span className="text-surface-500">Raw:</span>{" "}
              <span className="font-mono font-medium text-surface-900">{doc.ocr_raw ?? "—"}</span>
            </div>
            {ocrCandidates.length > 0 && (
              <div>
                <span className="text-surface-500">Candidates:</span>
                <ul className="mt-1 space-y-1">
                  {ocrCandidates.map((c, i) => (
                    <li key={i} className="font-mono text-surface-700">
                      {c.idsubsls} ({formatPercent(c.confidence)})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>

      {doc.error_message && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <strong>Error:</strong> {doc.error_message}
        </div>
      )}

      {doc.processing_status === "FAILED" && (
        <button
          onClick={handleRetry}
          disabled={retrying}
          className="rounded-md bg-surface-900 px-4 py-2 text-sm font-medium text-white hover:bg-surface-800 disabled:opacity-50"
        >
          {retrying ? "Retrying..." : "Retry Processing"}
        </button>
      )}
    </div>
  );
}

"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import { presignUpload, completeUpload, getMap } from "@/lib/api";
import type { PresignResponse, ProcessingStatus } from "@/lib/types";
import UploadDropzone from "@/components/UploadDropzone";
import { showToast } from "@/components/Toast";
import StatusPill from "@/components/StatusPill";

type FileState =
  | { status: "queued" }
  | { status: "presigning" }
  | { status: "uploading"; progress: number }
  | { status: "completing" }
  | { status: "processing"; processing: ProcessingStatus }
  | { status: "done"; processing: ProcessingStatus }
  | { status: "error"; message: string };

type TransientUploadState = "queued" | "presigning" | "uploading" | "completing";

const TERMINAL_STATUSES: ReadonlySet<ProcessingStatus> = new Set<ProcessingStatus>([
  "COMPLETED",
  "NEEDS_REVIEW",
  "FAILED",
]);

interface FileItem {
  file: File;
  id: string;
  state: FileState;
  docId?: string;
}

export default function UploadPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [batchId] = useState(() => `${Date.now()}`);

  const updateFile = useCallback((id: string, updater: (prev: FileItem) => FileItem) => {
    setFiles((prev) => prev.map((f) => (f.id === id ? updater(f) : f)));
  }, []);

  const processFile = useCallback(
    async (item: FileItem) => {
      try {
        updateFile(item.id, (f) => ({ ...f, state: { status: "presigning" } }));

        let imageInfo: { width: number; height: number };
        try {
          imageInfo = await getImageDimensions(item.file);
        } catch {
          imageInfo = { width: 0, height: 0 };
        }

        const presign: PresignResponse = await presignUpload({
          filename: item.file.name,
          content_type: item.file.type,
          size: item.file.size,
          target_id: null,
        });

        updateFile(item.id, (f) => ({ ...f, state: { status: "uploading", progress: 0 } }));

        await uploadToGarage(item.file, presign.upload_url, presign.headers, (progress) => {
          updateFile(item.id, (f) => ({ ...f, state: { status: "uploading", progress } }));
        });

        updateFile(item.id, (f) => ({ ...f, state: { status: "completing" } }));

        const complete = await completeUpload({
          map_document_id: presign.map_document_id,
          width: imageInfo.width,
          height: imageInfo.height,
          file_size: item.file.size,
        });

        updateFile(item.id, (f) => ({
          ...f,
          docId: presign.map_document_id,
          state: {
            status: "processing",
            processing: complete.map_document.processing_status,
          },
        }));
        showToast(`${item.file.name} uploaded — processing`, "success");
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        updateFile(item.id, (f) => ({ ...f, state: { status: "error", message: msg } }));
        showToast(`${item.file.name}: ${msg}`, "error");
      }
    },
    [updateFile]
  );

  const handleUpload = useCallback(
    async (newFiles: File[]) => {
      const items: FileItem[] = newFiles.map((file, i) => ({
        file,
        id: `${batchId}-${Date.now()}-${i}`,
        state: { status: "queued" },
      }));
      setFiles((prev) => [...prev, ...items]);

      for (const item of items) {
        processFile(item);
      }
    },
    [batchId, processFile]
  );

  const handleRetry = useCallback(
    (id: string) => {
      const item = files.find((f) => f.id === id);
      if (!item) return;
      updateFile(id, (f) => ({ ...f, state: { status: "queued" } }));
      processFile({ ...item, state: { status: "queued" } });
    },
    [files, updateFile, processFile]
  );

  const activeCount = files.filter(
    (f) => f.state.status === "presigning" || f.state.status === "uploading" || f.state.status === "completing"
  ).length;

  const completedCount = files.filter(
    (f) => f.state.status === "done" && f.state.processing === "COMPLETED"
  ).length;
  const reviewCount = files.filter(
    (f) => f.state.status === "done" && f.state.processing === "NEEDS_REVIEW"
  ).length;
  const failedCount = files.filter(
    (f) => f.state.status === "error" || (f.state.status === "done" && f.state.processing === "FAILED")
  ).length;
  const finishedCount = completedCount + reviewCount + failedCount;

  // Track freshly uploaded documents and poll their processing status until they
  // reach a terminal state, so the operator sees what happens to each map.
  const pendingRef = useRef<{ id: string; docId: string }[]>([]);
  useEffect(() => {
    pendingRef.current = files
      .filter((f) => f.state.status === "processing" && f.docId)
      .map((f) => ({ id: f.id, docId: f.docId as string }));
  });

  useEffect(() => {
    const timer = setInterval(() => {
      for (const { id, docId } of pendingRef.current) {
        getMap(docId)
          .then((doc) => {
            const finished = TERMINAL_STATUSES.has(doc.processing_status);
            updateFile(id, (prev) => ({
              ...prev,
              state: finished
                ? { status: "done", processing: doc.processing_status }
                : { status: "processing", processing: doc.processing_status },
            }));
          })
          .catch(() => {
            /* transient failure: keep last known state and retry next tick */
          });
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [updateFile]);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-surface-900">Upload Maps</h1>

      <UploadDropzone onUpload={handleUpload} disabled={false} />

      {finishedCount > 0 && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-surface-200 bg-white px-4 py-3 text-sm shadow-sm">
          <span className="font-medium text-surface-900">{finishedCount} finished</span>
          <span className="text-emerald-700">{completedCount} completed</span>
          <span className="text-rose-700">{reviewCount} need review</span>
          <span className="text-red-600">{failedCount} failed</span>
          <div className="ml-auto flex gap-2">
            {reviewCount > 0 && (
              <Link
                href="/review"
                className="rounded-md border border-surface-300 px-2.5 py-1 text-xs font-medium hover:bg-surface-50"
              >
                Review queue →
              </Link>
            )}
            <Link
              href="/logs"
              className="rounded-md border border-surface-300 px-2.5 py-1 text-xs font-medium hover:bg-surface-50"
            >
              View logs →
            </Link>
          </div>
        </div>
      )}

      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm text-surface-600">
            <span>{files.length} file(s)</span>
            {activeCount > 0 && <span>{activeCount} active</span>}
          </div>
          <div className="divide-y divide-surface-200 rounded-lg border border-surface-200 bg-white shadow-sm">
            {files.map((item) => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <p className="truncate text-sm font-medium text-surface-900">{item.file.name}</p>
                  <p className="text-xs text-surface-500">{(item.file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
                <div className="w-32">
                  {item.state.status === "uploading" && (
                    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-200">
                      <div
                        className="h-full rounded-full bg-surface-800 transition-all"
                        style={{ width: `${item.state.progress}%` }}
                      />
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {item.state.status === "error" ? (
                    <>
                      <span className="max-w-[12rem] truncate text-xs text-red-600">{item.state.message}</span>
                      <button
                        onClick={() => handleRetry(item.id)}
                        className="rounded-md bg-surface-900 px-2 py-1 text-xs font-medium text-white hover:bg-surface-800"
                      >
                        Retry
                      </button>
                    </>
                  ) : item.state.status === "processing" || item.state.status === "done" ? (
                    <StatusPill status={item.state.processing} />
                  ) : (
                    <StatusPill status={mapUploadStatus(item.state.status)} />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function mapUploadStatus(status: TransientUploadState): ProcessingStatus {
  switch (status) {
    case "queued":
      return "UPLOADING";
    case "presigning":
      return "UPLOADING";
    case "uploading":
      return "UPLOADED";
    case "completing":
      return "QUEUED";
  }
}

function getImageDimensions(file: File): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to read image dimensions"));
    };
    img.src = url;
  });
}

function uploadToGarage(
  file: File,
  url: string,
  headers: Record<string, string>,
  onProgress: (p: number) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url, true);
    Object.entries(headers).forEach(([k, v]) => xhr.setRequestHeader(k, v));

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100);
        resolve();
      } else {
        reject(new Error(`Garage upload failed: ${xhr.statusText}`));
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(file);
  });
}

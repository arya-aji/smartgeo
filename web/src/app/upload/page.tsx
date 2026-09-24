"use client";

import { useState, useCallback } from "react";
import { presignUpload, completeUpload } from "@/lib/api";
import type { PresignResponse } from "@/lib/types";
import UploadDropzone from "@/components/UploadDropzone";
import { showToast } from "@/components/Toast";
import StatusPill from "@/components/StatusPill";

type FileState =
  | { status: "queued" }
  | { status: "presigning" }
  | { status: "uploading"; progress: number }
  | { status: "completing" }
  | { status: "done" }
  | { status: "error"; message: string };

interface FileItem {
  file: File;
  id: string;
  state: FileState;
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

        await completeUpload({
          map_document_id: presign.map_document_id,
          width: imageInfo.width,
          height: imageInfo.height,
          file_size: item.file.size,
        });

        updateFile(item.id, (f) => ({ ...f, state: { status: "done" } }));
        showToast(`${item.file.name} uploaded`, "success");
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

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-surface-900">Upload Maps</h1>

      <UploadDropzone onUpload={handleUpload} disabled={false} />

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
                  {item.state.status === "done" && (
                    <span className="text-xs font-medium text-emerald-700">Done</span>
                  )}
                  {item.state.status === "error" && (
                    <>
                      <span className="max-w-[12rem] truncate text-xs text-red-600">{item.state.message}</span>
                      <button
                        onClick={() => handleRetry(item.id)}
                        className="rounded-md bg-surface-900 px-2 py-1 text-xs font-medium text-white hover:bg-surface-800"
                      >
                        Retry
                      </button>
                    </>
                  )}
                  {item.state.status !== "done" && item.state.status !== "error" && (
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

function mapUploadStatus(status: FileState["status"]): import("@/lib/types").ProcessingStatus {
  switch (status) {
    case "queued":
      return "UPLOADING";
    case "presigning":
      return "UPLOADING";
    case "uploading":
      return "UPLOADED";
    case "completing":
      return "QUEUED";
    case "done":
      return "COMPLETED";
    case "error":
      return "FAILED";
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

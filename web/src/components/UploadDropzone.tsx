"use client";

import { useCallback, useState } from "react";
import { showToast } from "./Toast";

interface FileItem {
  file: File;
  id: string;
  status: "queued" | "presigning" | "uploading" | "completing" | "done" | "error";
  progress: number;
  error?: string;
}

interface UploadDropzoneProps {
  onUpload: (files: File[]) => void;
  disabled?: boolean;
}

export default function UploadDropzone({ onUpload, disabled }: UploadDropzoneProps) {
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (disabled) return;
      const files = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith("image/"));
      if (files.length === 0) {
        showToast("Please drop image files only", "error");
        return;
      }
      onUpload(files);
    },
    [disabled, onUpload]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (disabled) return;
      const files = Array.from(e.target.files || []).filter((f) => f.type.startsWith("image/"));
      if (files.length) onUpload(files);
      e.target.value = "";
    },
    [disabled, onUpload]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors ${
        dragOver
          ? "border-surface-800 bg-surface-100"
          : "border-surface-300 bg-white hover:border-surface-500"
      } ${disabled ? "opacity-60" : ""}`}
    >
      <svg className="mb-3 h-10 w-10 text-surface-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5M5.25 12h13.5m-13.5 0L12 3.75l6.75 8.25" />
      </svg>
      <p className="text-sm font-medium text-surface-700">
        Drag and drop image files here
      </p>
      <p className="mt-1 text-xs text-surface-500">or click to browse</p>
      <input
        type="file"
        multiple
        accept="image/*"
        onChange={handleChange}
        className="absolute inset-0 cursor-pointer opacity-0"
        disabled={disabled}
      />
    </div>
  );
}

export type { FileItem };

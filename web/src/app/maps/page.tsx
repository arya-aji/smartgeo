"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMaps } from "@/lib/api";
import type { MapDocumentSummary, ProcessingStatus } from "@/lib/types";
import DataTable from "@/components/DataTable";
import StatusPill from "@/components/StatusPill";
import { formatDate, formatPercent } from "@/lib/format";
import { showToast } from "@/components/Toast";

const STATUS_OPTIONS: ProcessingStatus[] = [
  "UPLOADING",
  "UPLOADED",
  "QUEUED",
  "DETECTING_PAPER",
  "CORRECTING_PERSPECTIVE",
  "DETECTING_ORIENTATION",
  "ENHANCING",
  "UPSCALING",
  "DETECTING_TEXT",
  "RECOGNIZING_ID",
  "VALIDATING_ID",
  "FINALIZING",
  "COMPLETED",
  "NEEDS_REVIEW",
  "FAILED",
];

export default function MapsPage() {
  const [rows, setRows] = useState<MapDocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [status, setStatus] = useState<ProcessingStatus | "">("");
  const [q, setQ] = useState("");
  const [mine, setMine] = useState(false);
  const router = useRouter();

  const fetchData = async (p = page) => {
    setLoading(true);
    try {
      const res = await getMaps({
        status: status || undefined,
        q: q || undefined,
        page: p,
        page_size: pageSize,
        mine,
      });
      setRows(res.items);
      setTotal(res.total);
      setPages(res.pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load maps";
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, mine]);

  useEffect(() => {
    fetchData(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchData(1);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold text-surface-900">Maps</h1>
        <form onSubmit={handleSearch} className="flex flex-wrap items-center gap-2">
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as ProcessingStatus | "");
              setPage(1);
            }}
            className="rounded-md border border-surface-300 px-2 py-1.5 text-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Search IDSUBSLS..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="rounded-md border border-surface-300 px-3 py-1.5 text-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
          />
          <label className="flex items-center gap-2 text-sm text-surface-700">
            <input
              type="checkbox"
              checked={mine}
              onChange={(e) => {
                setMine(e.target.checked);
                setPage(1);
              }}
              className="rounded border-surface-300 text-surface-900 focus:ring-surface-500"
            />
            Mine only
          </label>
          <button
            type="submit"
            className="rounded-md bg-surface-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-surface-800"
          >
            Search
          </button>
        </form>
      </div>

      <DataTable
        columns={[
          {
            key: "preview",
            header: "Preview",
            render: (row) =>
              row.preview_url ? (
                <img
                  src={row.preview_url}
                  alt=""
                  className="h-10 w-10 rounded object-cover"
                />
              ) : (
                <div className="h-10 w-10 rounded bg-surface-200" />
              ),
          },
          { key: "idsubsls", header: "IDSUBSLS" },
          {
            key: "status",
            header: "Status",
            render: (row) => <StatusPill status={row.processing_status} />,
          },
          {
            key: "quality",
            header: "Quality",
            render: (row) => formatPercent(row.quality_score),
            className: "text-right",
          },
          {
            key: "ocr",
            header: "OCR",
            render: (row) => formatPercent(row.ocr_confidence),
            className: "text-right",
          },
          {
            key: "paper",
            header: "Paper",
            render: (row) => formatPercent(row.paper_confidence),
            className: "text-right",
          },
          { key: "uploaded_by_name", header: "Uploaded by" },
          {
            key: "created_at",
            header: "Created",
            render: (row) => formatDate(row.created_at),
          },
        ]}
        rows={rows}
        keyExtractor={(r) => r.id}
        onRowClick={(row) => router.push(`/maps/${row.id}`)}
        loading={loading}
        emptyText="No maps found"
      />

      <div className="flex items-center justify-between text-sm text-surface-600">
        <span>
          {total} results • Page {page} of {pages}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-md border border-surface-300 px-3 py-1.5 text-sm font-medium hover:bg-surface-50 disabled:opacity-50"
          >
            Previous
          </button>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page >= pages}
            className="rounded-md border border-surface-300 px-3 py-1.5 text-sm font-medium hover:bg-surface-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

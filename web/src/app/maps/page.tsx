"use client";

import { useEffect, useState } from "react";
import { getTargets } from "@/lib/api";
import type { WssTarget } from "@/lib/types";
import DataTable from "@/components/DataTable";
import StatusPill from "@/components/StatusPill";
import { showToast } from "@/components/Toast";

const STATUS_OPTIONS = [
  "PENDING",
  "ASSIGNED",
  "PROCESSING",
  "COMPLETED",
  "NEEDS_REVIEW",
  "FAILED",
];

const ACTION_BUTTON =
  "rounded-md border border-surface-300 px-2.5 py-1 text-xs font-medium hover:bg-surface-50";
const ACTION_DISABLED =
  "rounded-md border border-surface-200 px-2.5 py-1 text-xs font-medium text-surface-400";

export default function MapPage() {
  const [rows, setRows] = useState<WssTarget[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");

  const fetchData = async (p = page) => {
    setLoading(true);
    try {
      const res = await getTargets({
        status: status || undefined,
        q: q || undefined,
        page: p,
        page_size: pageSize,
      });
      setRows(res.items);
      setTotal(res.total);
      setPages(res.pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load regions";
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

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
        <h1 className="text-xl font-semibold text-surface-900">Map</h1>
        <form onSubmit={handleSearch} className="flex flex-wrap items-center gap-2">
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
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
            render: (row) => <StatusPill status={row.status} />,
          },
          {
            key: "actions",
            header: "Actions",
            render: (row) => {
              const previewHref = row.final_url || row.preview_url;
              return (
                <div className="flex gap-2">
                  {previewHref ? (
                    <a
                      href={previewHref}
                      target="_blank"
                      rel="noreferrer"
                      className={ACTION_BUTTON}
                    >
                      Preview
                    </a>
                  ) : (
                    <span className={ACTION_DISABLED}>Preview</span>
                  )}
                  {row.download_url ? (
                    <a href={row.download_url} className={ACTION_BUTTON}>
                      Download
                    </a>
                  ) : (
                    <span className={ACTION_DISABLED}>Download</span>
                  )}
                </div>
              );
            },
          },
        ]}
        rows={rows}
        keyExtractor={(r) => r.id}
        loading={loading}
        emptyText="No regions found"
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

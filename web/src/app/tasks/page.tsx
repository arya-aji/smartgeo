"use client";

import { useCallback, useEffect, useState } from "react";
import { claimBatch, getTargets } from "@/lib/api";
import type { WssTarget } from "@/lib/types";
import DataTable from "@/components/DataTable";
import StatusPill from "@/components/StatusPill";
import { showToast } from "@/components/Toast";
import { formatDate } from "@/lib/format";

const STATUS_OPTIONS = ["ASSIGNED", "PROCESSING", "COMPLETED", "NEEDS_REVIEW", "FAILED"];

export default function TasksPage() {
  const [rows, setRows] = useState<WssTarget[]>([]);
  const [loading, setLoading] = useState(true);
  const [claiming, setClaiming] = useState(false);
  const [size, setSize] = useState(10);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [status, setStatus] = useState("");

  const fetchData = useCallback(
    async (p: number) => {
      setLoading(true);
      try {
        const res = await getTargets({
          mine: true,
          status: status || undefined,
          page: p,
          page_size: pageSize,
        });
        setRows(res.items);
        setTotal(res.total);
        setPages(res.pages);
        setPage(p);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load your tasks";
        showToast(msg, "error");
      } finally {
        setLoading(false);
      }
    },
    [status, pageSize]
  );

  useEffect(() => {
    fetchData(1);
  }, [fetchData]);

  const handleClaim = async () => {
    setClaiming(true);
    try {
      const res = await claimBatch(size);
      if (res.targets.length > 0) {
        showToast(
          `Claimed ${res.targets.length} task(s) • ${res.remaining} still unassigned`,
          "success"
        );
      } else {
        showToast("No unassigned tasks left", "info");
      }
      fetchData(1);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not claim tasks";
      showToast(msg, "error");
    } finally {
      setClaiming(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-surface-900">My Tasks</h1>
          <p className="mt-1 text-sm text-surface-500">
            Regions assigned to you. Upload a map for each one — the result is linked back by
            IDSUBSLS.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-surface-700">
            Batch size
            <input
              type="number"
              min={1}
              max={100}
              value={size}
              onChange={(e) => setSize(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
              className="w-20 rounded-md border border-surface-300 px-2 py-1.5 text-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
            />
          </label>
          <button
            onClick={handleClaim}
            disabled={claiming}
            className="rounded-md bg-surface-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-surface-800 disabled:opacity-50"
          >
            {claiming ? "Claiming..." : "Claim tasks"}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-md border border-surface-300 px-2 py-1.5 text-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <span className="text-sm text-surface-500">{total} task(s)</span>
      </div>

      <DataTable
        columns={[
          { key: "idsubsls", header: "IDSUBSLS" },
          {
            key: "status",
            header: "Status",
            render: (row) => <StatusPill status={row.status} />,
          },
          {
            key: "assigned_at",
            header: "Assigned",
            render: (row) => (row.assigned_at ? formatDate(row.assigned_at) : "—"),
          },
        ]}
        rows={rows}
        keyExtractor={(r) => r.id}
        loading={loading}
        emptyText="No tasks assigned yet — claim a batch to get started."
      />

      <div className="flex items-center justify-between text-sm text-surface-600">
        <span>
          {total} results • Page {page} of {pages}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => fetchData(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="rounded-md border border-surface-300 px-3 py-1.5 text-sm font-medium hover:bg-surface-50 disabled:opacity-50"
          >
            Previous
          </button>
          <button
            onClick={() => fetchData(Math.min(pages, page + 1))}
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

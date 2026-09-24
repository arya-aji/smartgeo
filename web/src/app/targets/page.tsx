"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getTargets, importTargets, deleteTarget } from "@/lib/api";
import type { WssTarget } from "@/lib/types";
import DataTable from "@/components/DataTable";
import { showToast } from "@/components/Toast";
import { isAdmin } from "@/lib/auth";

export default function TargetsPage() {
  const router = useRouter();
  const [targets, setTargets] = useState<WssTarget[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [importText, setImportText] = useState("");
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (!isAdmin()) {
      router.push("/maps");
      return;
    }
    fetchData(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchData = async (p = page) => {
    setLoading(true);
    try {
      const res = await getTargets({
        q: q || undefined,
        status: status || undefined,
        page: p,
        page_size: pageSize,
      });
      setTargets(res.items);
      setTotal(res.total);
      setPages(res.pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load targets";
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchData(1);
  };

  const handleImport = async () => {
    const lines = importText
      .split(/\n|,/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    if (lines.length === 0) {
      showToast("Enter at least one IDSUBSLS", "error");
      return;
    }
    setImporting(true);
    try {
      const res = await importTargets({ idsubsls: lines });
      showToast(`Created ${res.created}, skipped ${res.skipped}, invalid ${res.invalid}`, "success");
      setImportText("");
      fetchData(1);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Import failed";
      showToast(msg, "error");
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this target?")) return;
    try {
      await deleteTarget(id);
      showToast("Deleted", "success");
      fetchData(page);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      showToast(msg, "error");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-surface-900">Targets</h1>
      </div>

      <div className="rounded-lg border border-surface-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-surface-500">
          Bulk Import
        </h2>
        <textarea
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
          placeholder="Paste IDSUBSLS values, one per line or comma-separated"
          rows={4}
          className="mt-2 block w-full rounded-md border border-surface-300 px-3 py-2 text-sm font-mono focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
        />
        <div className="mt-2 flex items-center gap-2">
          <button
            onClick={handleImport}
            disabled={importing}
            className="rounded-md bg-surface-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-surface-800 disabled:opacity-50"
          >
            {importing ? "Importing..." : "Import"}
          </button>
        </div>
      </div>

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
          <option value="PENDING">PENDING</option>
          <option value="ASSIGNED">ASSIGNED</option>
          <option value="COMPLETED">COMPLETED</option>
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

      <DataTable
        columns={[
          { key: "idsubsls", header: "IDSUBSLS", className: "font-mono" },
          { key: "status", header: "Status" },
          {
            key: "assigned_to",
            header: "Assigned to",
            render: (row) => row.assigned_to ?? "—",
          },
          {
            key: "assigned_at",
            header: "Assigned at",
            render: (row) =>
              row.assigned_at
                ? new Date(row.assigned_at).toLocaleDateString()
                : "—",
          },
          {
            key: "actions",
            header: "",
            render: (row) => (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(row.id);
                }}
                className="text-sm font-medium text-red-600 hover:text-red-800"
              >
                Delete
              </button>
            ),
          },
        ]}
        rows={targets}
        keyExtractor={(r) => r.id}
        loading={loading}
        emptyText="No targets found"
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

"use client";

import { useEffect, useState } from "react";
import { getDashboard } from "@/lib/api";
import type { DashboardResponse } from "@/lib/types";
import StatCard from "@/components/StatCard";
import ProgressBar from "@/components/ProgressBar";
import DataTable from "@/components/DataTable";
import { showToast } from "@/components/Toast";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const res = await getDashboard();
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load dashboard";
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-surface-200" />
          ))}
        </div>
        <div className="h-8 animate-pulse rounded bg-surface-200" />
        <div className="h-64 animate-pulse rounded-lg bg-surface-200" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-lg border border-surface-200 bg-white p-8 text-center text-surface-500">
        Failed to load dashboard data.
      </div>
    );
  }

  const g = data.global;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-surface-900">Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Total" value={g.total} />
        <StatCard label="Completed" value={g.completed} />
        <StatCard label="Processing" value={g.processing} />
        <StatCard label="Queued" value={g.queued} />
        <StatCard label="Review" value={g.review} />
        <StatCard label="Failed" value={g.failed} />
      </div>

      <div className="rounded-lg border border-surface-200 bg-white p-4 shadow-sm">
        <ProgressBar
          percent={data.progress_percent}
          target={5511}
          current={g.completed}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="CV Pending" value={data.queue.cv_pending} />
        <StatCard label="CV Processing" value={data.queue.cv_processing} />
        <StatCard label="Geo Pending" value={data.queue.geo_pending} />
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-surface-500">
          Operators
        </h2>
        <DataTable
          columns={[
            { key: "name", header: "Name" },
            { key: "username", header: "Username" },
            { key: "completed", header: "Completed", className: "text-right" },
            { key: "assigned", header: "Assigned", className: "text-right" },
            { key: "review", header: "Review", className: "text-right" },
            { key: "failed", header: "Failed", className: "text-right" },
          ]}
          rows={data.operators}
          keyExtractor={(r) => r.id}
          emptyText="No operators found"
        />
      </div>
    </div>
  );
}

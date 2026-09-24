"use client";

import { useEffect, useState } from "react";
import { getReviewQueue, acceptReview, manualReview } from "@/lib/api";
import type { MapDocumentSummary } from "@/lib/types";
import { formatPercent } from "@/lib/format";
import { showToast } from "@/components/Toast";

export default function ReviewPage() {
  const [items, setItems] = useState<MapDocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [manualId, setManualId] = useState<Record<string, string>>({});
  const [acting, setActing] = useState<Record<string, boolean>>({});
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const fetchData = async (p = page) => {
    setLoading(true);
    try {
      const res = await getReviewQueue({ page: p, page_size: pageSize });
      setItems(res.items);
      setTotal(res.total);
      setPages(res.pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load review queue";
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const handleAccept = async (item: MapDocumentSummary) => {
    if (
      !confirm(
        `Accept this result as the final map for ${item.idsubsls ?? "this ID"}?\n\nIt becomes the region's final map and cannot be undone.`
      )
    ) {
      return;
    }
    const id = item.id;
    setActing((prev) => ({ ...prev, [id]: true }));
    try {
      await acceptReview(id);
      showToast("Accepted", "success");
      fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Accept failed";
      showToast(msg, "error");
    } finally {
      setActing((prev) => ({ ...prev, [id]: false }));
    }
  };

  const handleManual = async (item: MapDocumentSummary) => {
    const id = item.id;
    const idsubsls = manualId[id]?.trim();
    if (!idsubsls) {
      showToast("Enter an IDSUBSLS", "error");
      return;
    }
    if (!/^\d{16}$/.test(idsubsls)) {
      showToast("IDSUBSLS must be exactly 16 digits", "error");
      return;
    }
    if (
      !confirm(
        `Apply ${idsubsls} as the final ID?\n\nIt becomes the region's final map and cannot be undone.`
      )
    ) {
      return;
    }
    setActing((prev) => ({ ...prev, [id]: true }));
    try {
      await manualReview(id, { idsubsls });
      showToast("Manual ID applied", "success");
      setManualId((prev) => ({ ...prev, [id]: "" }));
      fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Manual correction failed";
      showToast(msg, "error");
    } finally {
      setActing((prev) => ({ ...prev, [id]: false }));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-surface-900">Review Queue</h1>
        <span className="text-sm text-surface-500">{total} pending</span>
      </div>

      {loading && items.length === 0 ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-lg bg-surface-200" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-surface-200 bg-white p-8 text-center text-surface-500">
          No items awaiting review
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex flex-col gap-4 rounded-lg border border-surface-200 bg-white p-4 shadow-sm sm:flex-row"
            >
              <div className="shrink-0">
                <button
                  type="button"
                  aria-label="Enlarge preview"
                  onClick={() => item.preview_url && setPreviewUrl(item.preview_url)}
                  title={item.preview_url ? "Click to enlarge" : undefined}
                  className={item.preview_url ? "cursor-zoom-in" : "cursor-default"}
                >
                  {item.preview_url ? (
                    <img
                      src={item.preview_url}
                      alt=""
                      className="h-32 w-32 rounded object-cover"
                    />
                  ) : (
                    <div className="h-32 w-32 rounded bg-surface-200" />
                  )}
                </button>
              </div>
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-lg font-semibold text-surface-900">
                    {item.idsubsls}
                  </span>
                  <span className="text-xs text-surface-500">OCR: {formatPercent(item.ocr_confidence)}</span>
                </div>
                {item.review_reason && (
                  <p className="text-sm text-rose-700">{item.review_reason}</p>
                )}
                <div className="flex flex-wrap gap-2 pt-2">
                    <button
                      onClick={() => handleAccept(item)}
                    disabled={acting[item.id]}
                    className="rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50"
                  >
                    Accept
                  </button>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="16-digit IDSUBSLS"
                      value={manualId[item.id] || ""}
                      onChange={(e) =>
                        setManualId((prev) => ({ ...prev, [item.id]: e.target.value }))
                      }
                      className="w-40 rounded-md border border-surface-300 px-2 py-1.5 text-sm font-mono focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
                    />
                    <button
                      onClick={() => handleManual(item)}
                      disabled={acting[item.id]}
                      className="rounded-md bg-surface-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-surface-800 disabled:opacity-50"
                    >
                      Save
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-surface-600">
        <span>
          Page {page} of {pages}
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

      {previewUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setPreviewUrl(null)}
        >
          <button
            type="button"
            onClick={() => setPreviewUrl(null)}
            className="absolute right-4 top-4 rounded-md bg-white/90 px-3 py-1 text-sm font-medium text-surface-900 hover:bg-white"
          >
            Close
          </button>
          <img
            src={previewUrl}
            alt=""
            onClick={(e) => e.stopPropagation()}
            className="max-h-[90vh] max-w-full rounded-lg bg-white object-contain"
          />
        </div>
      )}
    </div>
  );
}

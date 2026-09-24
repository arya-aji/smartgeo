"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border border-surface-200 bg-white p-6 text-center shadow-sm">
        <h1 className="text-lg font-semibold text-surface-900">Something went wrong</h1>
        <p className="mt-2 break-words text-sm text-surface-500">
          {error.message || "An unexpected error occurred while rendering this page."}
        </p>
        <div className="mt-4 flex justify-center gap-2">
          <button
            onClick={reset}
            className="rounded-md bg-surface-900 px-4 py-2 text-sm font-medium text-white hover:bg-surface-800"
          >
            Try again
          </button>
          <Link
            href="/maps"
            className="rounded-md border border-surface-300 px-4 py-2 text-sm font-medium hover:bg-surface-50"
          >
            Go to Map
          </Link>
        </div>
      </div>
    </div>
  );
}

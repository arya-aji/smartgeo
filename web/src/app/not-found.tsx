import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border border-surface-200 bg-white p-6 text-center shadow-sm">
        <h1 className="text-lg font-semibold text-surface-900">Page not found</h1>
        <p className="mt-2 text-sm text-surface-500">
          The page you are looking for does not exist or has moved.
        </p>
        <Link
          href="/maps"
          className="mt-4 inline-block rounded-md bg-surface-900 px-4 py-2 text-sm font-medium text-white hover:bg-surface-800"
        >
          Go to Map
        </Link>
      </div>
    </div>
  );
}

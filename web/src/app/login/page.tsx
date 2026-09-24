"use client";

import { useState } from "react";
import { login } from "@/lib/api";
import { homePathFor, storeAuth } from "@/lib/auth";
import { showToast } from "@/components/Toast";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await login({ username, password });
      storeAuth(res.access_token, res.user);
      // Hard navigation so the freshly set cookies are sent and the edge
      // middleware (not the client router cache) decides where to land.
      window.location.href = homePathFor(res.user.role);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Login failed";
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-100 px-4">
      <div className="w-full max-w-sm rounded-lg border border-surface-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-surface-900">WSS Platform</h1>
        <p className="mt-1 text-sm text-surface-500">Sign in to your account</p>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-surface-700">
              Username
            </label>
            <input
              id="username"
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="mt-1 block w-full rounded-md border border-surface-300 px-3 py-2 text-sm shadow-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-surface-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full rounded-md border border-surface-300 px-3 py-2 text-sm shadow-sm focus:border-surface-500 focus:outline-none focus:ring-1 focus:ring-surface-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center rounded-md bg-surface-900 px-4 py-2 text-sm font-medium text-white hover:bg-surface-800 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getUser, clearAuth, isAdmin } from "@/lib/auth";
import type { User } from "@/lib/types";

const NAV = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Upload", href: "/upload" },
  { label: "Map", href: "/maps" },
  { label: "Logs", href: "/logs" },
  { label: "Review", href: "/review" },
];

const ADMIN_NAV = [
  { label: "Operators", href: "/operators" },
  { label: "Targets", href: "/targets" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setUser(getUser());
  }, []);

  const handleLogout = () => {
    clearAuth();
    window.location.href = "/login";
  };

  const navItems = [...NAV, ...(isAdmin() ? ADMIN_NAV : [])];

  return (
    <div className="flex h-screen bg-surface-50 text-surface-900">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform border-r border-surface-200 bg-white shadow-sm transition-transform duration-200 lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center border-b border-surface-200 px-4">
          <span className="text-lg font-semibold tracking-tight text-surface-900">
            WSS Platform
          </span>
        </div>
        <nav className="space-y-1 px-3 py-4">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-surface-100 text-surface-900"
                    : "text-surface-600 hover:bg-surface-50 hover:text-surface-900"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-14 items-center justify-between border-b border-surface-200 bg-white px-4">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-2 text-surface-600 hover:bg-surface-100 lg:hidden"
            aria-label="Open menu"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <div className="flex items-center gap-3">
            {user && (
              <>
                <span className="hidden text-sm text-surface-600 sm:inline">
                  {user.name}
                </span>
                <span className="rounded bg-surface-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wider text-surface-600">
                  {user.role}
                </span>
                <button
                  onClick={handleLogout}
                  className="rounded-md px-3 py-1.5 text-sm font-medium text-surface-600 hover:bg-surface-100 hover:text-surface-900"
                >
                  Log out
                </button>
              </>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}

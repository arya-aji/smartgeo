"use client";

import type { User } from "./types";

const TOKEN_KEY = "wss_token";
const USER_KEY = "wss_user";

export function storeAuth(token: string, user: User): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  document.cookie = `token=${token}; path=/; max-age=86400; SameSite=Lax`;
  storeUser(user);
}

export function storeUser(user: User): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  // Readable by the edge middleware to gate admin-only routes.
  document.cookie = `role=${user.role}; path=/; max-age=86400; SameSite=Lax`;
}

export function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem(TOKEN_KEY);
  }
  return null;
}

export function getUser(): User | null {
  if (typeof window !== "undefined") {
    const raw = localStorage.getItem(USER_KEY);
    if (raw) {
      try {
        return JSON.parse(raw) as User;
      } catch {
        return null;
      }
    }
  }
  return null;
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  document.cookie = "token=; path=/; max-age=0; SameSite=Lax";
  document.cookie = "role=; path=/; max-age=0; SameSite=Lax";
}

export function isAdmin(): boolean {
  const user = getUser();
  return user?.role === "ADMIN";
}

/** Landing route after login, and where non-admins are sent from admin pages. */
export function homePathFor(role: string | undefined): string {
  return role === "ADMIN" ? "/dashboard" : "/maps";
}

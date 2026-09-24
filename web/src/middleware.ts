import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/api/auth/login"];
const ADMIN_PATHS = ["/dashboard", "/operators", "/targets"];

function isUnder(pathname: string, base: string): boolean {
  return pathname === base || pathname.startsWith(`${base}/`);
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  const token = request.cookies.get("token")?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Admin-only pages. The API enforces this too (require_admin); redirecting
  // here just avoids an operator seeing a page that 403s.
  const role = request.cookies.get("role")?.value;
  if (role !== "ADMIN" && ADMIN_PATHS.some((p) => isUnder(pathname, p))) {
    return NextResponse.redirect(new URL("/maps", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};

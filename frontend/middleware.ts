import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Next.js Edge Middleware.
 *
 * Checks for the presence of the access_token httpOnly cookie on protected routes.
 * Per docs/architecture/system-architecture.md:
 * Middleware ONLY checks cookie presence — it DOES NOT parse or validate the JWT.
 * The backend is the single security boundary.
 */
export function middleware(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;
  const isAuthRoute =
    request.nextUrl.pathname.startsWith("/login") ||
    request.nextUrl.pathname.startsWith("/register");

  // If user is trying to access dashboard/courses without a token cookie, redirect to login
  if (!token && !isAuthRoute && request.nextUrl.pathname.startsWith("/dashboard")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // If user has a token cookie and tries to access login/register, redirect to dashboard
  if (token && isAuthRoute) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};


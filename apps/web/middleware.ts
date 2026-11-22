import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const session = request.cookies.get("paper_session");
  const isLogin = request.nextUrl.pathname === "/login";

  if (session && isLogin) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // The API is the security boundary. Let the client render the shell and
  // redirect to login only when a protected API request returns 401.
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};

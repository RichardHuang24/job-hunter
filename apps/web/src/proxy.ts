// Every page needs a signed-in user (the `authorized` callback in auth.ts);
// sign-in itself, Auth.js's routes and static files don't. /api/backend checks
// the session itself and answers 401 rather than redirecting.
export { auth as proxy } from "@/auth";

export const config = {
  matcher: ["/((?!api/auth|api/backend|signin|_next/static|_next/image|favicon.ico|icon.svg).*)"],
};

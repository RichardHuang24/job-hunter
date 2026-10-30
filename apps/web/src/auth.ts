// Sign-in, with Auth.js. Sessions live in Postgres (@auth/pg-adapter); the
// tables are created by the API's migrations (apps/api/alembic).
//
// Providers turn on from the environment: email links when EMAIL_SERVER is
// set (Mailpit in development), GitHub and Google when their client id and
// secret are.
import NextAuth from "next-auth";
import type { Provider } from "next-auth/providers";
import GitHub from "next-auth/providers/github";
import Google from "next-auth/providers/google";
import Nodemailer from "next-auth/providers/nodemailer";
import PostgresAdapter from "@auth/pg-adapter";
import { pool } from "@/lib/db";

const providers: Provider[] = [];
if (process.env.EMAIL_SERVER) {
  providers.push(
    Nodemailer({ server: process.env.EMAIL_SERVER, from: process.env.EMAIL_FROM ?? "Job Hunter <no-reply@localhost>" }),
  );
}
if (process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET) providers.push(GitHub);
if (process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET) providers.push(Google);

/** The sign-in options to show, without their secrets. */
export const signInOptions = providers.map((provider) => {
  const config = typeof provider === "function" ? provider() : provider;
  return { id: config.id, name: config.name, type: config.type };
});

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: PostgresAdapter(pool),
  providers,
  session: { strategy: "database" },
  pages: { signIn: "/signin", verifyRequest: "/signin/check-email" },
  callbacks: {
    // proxy.ts: pages need a signed-in user; Auth.js sends anyone else to /signin.
    authorized: ({ auth: session }) => Boolean(session?.user),
    session: ({ session, user }) => {
      // Postgres hands the id back as a number; the API token names it as a string.
      session.user.id = String(user.id);
      return session;
    },
  },
});

// The Postgres pool Auth.js keeps its users and sessions in. One DATABASE_URL
// serves the web app and the API; the API's SQLAlchemy form
// (postgresql+psycopg://) is accepted here too.
import { Pool } from "pg";

export function connectionString(url: string | undefined): string | undefined {
  return url?.replace(/^postgresql\+psycopg:\/\//, "postgresql://");
}

const globalForPool = globalThis as unknown as { jobHunterPool?: Pool };

export const pool =
  globalForPool.jobHunterPool ??
  new Pool({
    connectionString: connectionString(process.env.DATABASE_URL),
    max: 10,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
  });

if (process.env.NODE_ENV !== "production") globalForPool.jobHunterPool = pool;

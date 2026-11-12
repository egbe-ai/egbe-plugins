import "server-only";

import { Pool, type QueryResult, type QueryResultRow } from "pg";

declare global {
  // Preserve one pool across Next.js development reloads.
  // eslint-disable-next-line no-var
  var __egbeProductPool: Pool | undefined;
}

function createPool(): Pool {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is required by the product foundation");
  }
  return new Pool({ connectionString });
}

export function productDatabase(): Pool {
  if (!globalThis.__egbeProductPool) {
    globalThis.__egbeProductPool = createPool();
  }
  return globalThis.__egbeProductPool;
}

export function queryProductDatabase<Row extends QueryResultRow = QueryResultRow>(
  text: string,
  values: readonly unknown[] = [],
): Promise<QueryResult<Row>> {
  return productDatabase().query<Row>(text, [...values]);
}

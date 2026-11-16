import "server-only";

import { productDatabase } from "./db";
import type { ProductAccount } from "./session";

export type VerifiedExternalIdentity = {
  provider: string;
  subject: string;
  email: string;
  emailVerified: true;
};

function normalized(value: string, label: string): string {
  const result = value.trim().toLowerCase();
  if (!result) throw new Error(`${label} is required`);
  return result;
}

/** Resolve one verified provider identity to the product's local account. */
export async function resolveOrCreateExternalAccount(
  identity: VerifiedExternalIdentity,
): Promise<ProductAccount> {
  if (identity.emailVerified !== true) {
    throw new Error("External account email must be provider-verified");
  }
  const provider = normalized(identity.provider, "provider");
  const subject = identity.subject.trim();
  const email = normalized(identity.email, "email");
  if (!subject) throw new Error("subject is required");

  const client = await productDatabase().connect();
  try {
    await client.query("begin");
    await client.query(
      "select pg_advisory_xact_lock(hashtextextended($1 || ':' || $2, 0))",
      [provider, subject],
    );
    const existing = await client.query<{
      id: string;
      email: string;
      created_at: Date;
    }>(
      `select u.id, u.email, u.created_at
         from auth_identities i
         join users u on u.id = i.user_id
        where i.provider = $1 and i.subject = $2
        for update of i`,
      [provider, subject],
    );
    if (existing.rows[0]) {
      await client.query("commit");
      const row = existing.rows[0];
      return { id: row.id, email: row.email, createdAt: row.created_at };
    }

    const user = await client.query<{
      id: string;
      email: string;
      created_at: Date;
    }>(
      `insert into users (email, password_hash)
       values ($1, null)
       on conflict ((lower(email))) do update set updated_at = users.updated_at
       returning id, email, created_at`,
      [email],
    );
    await client.query(
      `insert into auth_identities (user_id, provider, subject, email_at_link)
       values ($1, $2, $3, $4)
       on conflict (provider, subject) do nothing`,
      [user.rows[0].id, provider, subject, email],
    );
    const linked = await client.query<{
      id: string;
      email: string;
      created_at: Date;
    }>(
      `select u.id, u.email, u.created_at
         from auth_identities i
         join users u on u.id = i.user_id
        where i.provider = $1 and i.subject = $2`,
      [provider, subject],
    );
    const row = linked.rows[0];
    if (!row) throw new Error("External identity could not be linked");
    await client.query("commit");
    return { id: row.id, email: row.email, createdAt: row.created_at };
  } catch (error) {
    await client.query("rollback");
    throw error;
  } finally {
    client.release();
  }
}

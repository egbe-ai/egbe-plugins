import "server-only";

import { createHash, randomBytes } from "node:crypto";
import { cookies } from "next/headers";

import { queryProductDatabase } from "./db";

export const PRODUCT_SESSION_COOKIE = "egbe_session";
export const PRODUCT_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30;

export type ProductAccount = {
  id: string;
  email: string;
  createdAt: Date;
};

export class ProductAuthenticationRequired extends Error {
  constructor() {
    super("Product authentication is required");
    this.name = "ProductAuthenticationRequired";
  }
}

export function hashProductSessionToken(token: string): string {
  return createHash("sha256").update(token, "utf8").digest("hex");
}

export async function createProductSession(userId: string): Promise<void> {
  const token = randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + PRODUCT_SESSION_TTL_SECONDS * 1000);
  await queryProductDatabase(
    `insert into sessions (user_id, token_hash, expires_at)
     values ($1, $2, $3)`,
    [userId, hashProductSessionToken(token), expiresAt],
  );
  const jar = await cookies();
  jar.set(PRODUCT_SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires: expiresAt,
  });
}

export async function resolveProductSession(
  token: string | undefined,
): Promise<ProductAccount | null> {
  if (!token) return null;
  const result = await queryProductDatabase<{
    id: string;
    email: string;
    created_at: Date;
  }>(
    `select u.id, u.email, u.created_at
       from sessions s
       join users u on u.id = s.user_id
      where s.token_hash = $1
        and s.revoked_at is null
        and s.expires_at > now()
      limit 1`,
    [hashProductSessionToken(token)],
  );
  const row = result.rows[0];
  return row ? { id: row.id, email: row.email, createdAt: row.created_at } : null;
}

export async function currentProductAccount(): Promise<ProductAccount | null> {
  const jar = await cookies();
  return resolveProductSession(jar.get(PRODUCT_SESSION_COOKIE)?.value);
}

export async function requireProductAccount(): Promise<ProductAccount> {
  const account = await currentProductAccount();
  if (!account) throw new ProductAuthenticationRequired();
  return account;
}

export async function revokeCurrentProductSession(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(PRODUCT_SESSION_COOKIE)?.value;
  if (token) {
    await queryProductDatabase(
      `update sessions
          set revoked_at = coalesce(revoked_at, now())
        where token_hash = $1`,
      [hashProductSessionToken(token)],
    );
  }
  jar.delete(PRODUCT_SESSION_COOKIE);
}

import "server-only";

type EgbeEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

function credentials(): { baseUrl: string; apiKey: string } {
  const baseUrl = (process.env.OS_URL || "https://os.hz.egbe.dev").replace(/\/$/, "");
  const apiKey = process.env.OS_API_KEY;
  if (!apiKey) throw new Error("OS_API_KEY is required by the billing foundation");
  return { baseUrl, apiKey };
}

export async function paymentOSRequest<T>(
  path: string,
  options: {
    body?: Record<string, unknown>;
    headers?: Record<string, string>;
  } = {},
): Promise<T> {
  const { baseUrl, apiKey } = credentials();
  const response = await fetch(`${baseUrl}/payments${path}`, {
    method: options.body ? "POST" : "GET",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });
  const envelope = (await response.json().catch(() => null)) as EgbeEnvelope<T> | null;
  if (!response.ok || !envelope || envelope.code >= 400) {
    throw new Error(envelope?.message || `Egbe Payments returned HTTP ${response.status}`);
  }
  return envelope.data;
}

export type CheckoutPayload = {
  price: string;
  mode: "subscription";
  customer?: string;
  customer_email?: string;
  client_reference_id: string;
  success_url: string;
  cancel_url: string;
  app_slug: string;
  webhook_path: string;
  allow_promotion_codes: boolean;
  discounts?: [CheckoutDiscount];
  metadata: Record<string, unknown>;
};

export type CheckoutDiscount =
  | { coupon: string }
  | { promotion_code: string };

export function validateCheckout(
  payload: CheckoutPayload & { idempotency_key: string },
  probeHeaders: Record<string, string>,
): Promise<{ valid: boolean; validation_receipt?: string }> {
  return paymentOSRequest("/checkout-sessions/validate", {
    body: payload,
    headers: probeHeaders,
  });
}

export function createCheckout(
  payload: CheckoutPayload,
  idempotencyKey: string,
): Promise<{ id: string; url: string }> {
  return paymentOSRequest("/checkout-sessions", {
    body: payload,
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export function validatePortal(
  payload: { customer: string; app_slug: string; return_path: string },
  probeHeaders: Record<string, string>,
): Promise<{ valid: boolean; validation_receipt?: string }> {
  return paymentOSRequest("/portal-sessions/validate", {
    body: payload,
    headers: probeHeaders,
  });
}

export function createPortal(payload: {
  customer: string;
  app_slug: string;
  return_path: string;
}): Promise<{ url: string }> {
  return paymentOSRequest("/portal-sessions", { body: payload });
}

import { randomBytes } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

import { ProductAuthenticationRequired, requireProductAccount } from "@/lib/egbe-product";
import { billingCatalog, billingPlan } from "@/lib/egbe-billing/catalog";
import { buildCheckoutPayload } from "@/lib/egbe-billing/checkout-payload";
import { createCheckout, validateCheckout } from "@/lib/egbe-billing/os-client";
import {
  getOrCreateCheckoutAttempt,
  providerPriceForPlan,
  readBillingState,
  recordCheckoutSession,
} from "@/lib/egbe-billing/repository";

const MANAGED_STATUSES = new Set(["trialing", "active", "past_due", "canceling", "paused"]);

async function requestPlanKey(request: NextRequest): Promise<string> {
  if (request.headers.get("content-type")?.includes("application/json")) {
    const body = (await request.json()) as { plan_key?: unknown };
    return String(body.plan_key || "");
  }
  const form = await request.formData();
  return String(form.get("plan_key") || "");
}

function probeHeaders(request: NextRequest): Record<string, string> | null {
  const mode = request.headers.get("x-egbe-payment-probe");
  const probeId = request.headers.get("x-egbe-payment-probe-id");
  if (!mode && !probeId) return null;
  if (mode !== "validate-only" || !probeId || !/^[A-Za-z0-9_-]{16,128}$/.test(probeId)) {
    throw new Error("Invalid payment validation probe");
  }
  return {
    "X-Egbe-Payment-Probe": mode,
    "X-Egbe-Payment-Probe-ID": probeId,
  };
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const account = await requireProductAccount();
    const plan = billingPlan(await requestPlanKey(request));
    if (plan.kind !== "subscription" || !plan.selectable) {
      return NextResponse.json({ error: "paid_plan_required" }, { status: 400 });
    }
    if (!billingCatalog.appSlug) {
      throw new Error("Billing catalog app_slug has not been configured");
    }
    const state = await readBillingState(account.id);
    if (MANAGED_STATUSES.has(state.status)) {
      return NextResponse.json({ error: "subscription_already_managed" }, { status: 409 });
    }
    const price = await providerPriceForPlan(plan.planKey);
    const attempt = await getOrCreateCheckoutAttempt(
      account.id,
      plan.planKey,
      "/account/billing?checkout=success",
      {},
    );
    const origin = process.env.NEXT_PUBLIC_BASE_URL;
    if (!origin) throw new Error("NEXT_PUBLIC_BASE_URL is required for Checkout");
    const payload = buildCheckoutPayload({
      account,
      state,
      attempt,
      appSlug: billingCatalog.appSlug,
      priceId: price,
      origin,
    });
    const validationHeaders = probeHeaders(request);
    if (validationHeaders) {
      const validation = await validateCheckout(
        { ...payload, idempotency_key: attempt.idempotencyKey },
        validationHeaders,
      );
      if (!validation.valid || !validation.validation_receipt) {
        throw new Error("Egbe Payments returned no validation receipt");
      }
      return NextResponse.json({
        validation_only: true,
        operation: "checkout",
        valid: true,
        validation_receipt: validation.validation_receipt,
      });
    }
    const checkout = await createCheckout(payload, attempt.idempotencyKey);
    if (!checkout.id || !checkout.url) throw new Error("Egbe Payments returned no Checkout URL");
    await recordCheckoutSession(attempt.id, checkout.id);
    if (request.headers.get("accept")?.includes("application/json")) {
      return NextResponse.json({ url: checkout.url });
    }
    return NextResponse.redirect(checkout.url, 303);
  } catch (error) {
    if (error instanceof ProductAuthenticationRequired) {
      return NextResponse.json({ error: "authentication_required" }, { status: 401 });
    }
    const requestId = randomBytes(8).toString("hex");
    console.error("billing checkout failed", { requestId, error });
    return NextResponse.json({ error: "checkout_unavailable", request_id: requestId }, { status: 503 });
  }
}

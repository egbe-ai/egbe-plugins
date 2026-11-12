import { NextRequest, NextResponse } from "next/server";

import { ProductAuthenticationRequired, requireProductAccount } from "@/lib/egbe-product";
import { billingCatalog } from "@/lib/egbe-billing/catalog";
import { createPortal, validatePortal } from "@/lib/egbe-billing/os-client";
import { readBillingState } from "@/lib/egbe-billing/repository";

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const account = await requireProductAccount();
    const state = await readBillingState(account.id);
    if (!state.customerId) {
      return NextResponse.json({ error: "billing_customer_unavailable" }, { status: 409 });
    }
    if (!billingCatalog.appSlug) throw new Error("Billing catalog app_slug has not been configured");
    const payload = {
      customer: state.customerId,
      app_slug: billingCatalog.appSlug,
      return_path: "/account/billing",
    };
    const mode = request.headers.get("x-egbe-payment-probe");
    const probeId = request.headers.get("x-egbe-payment-probe-id");
    if (mode || probeId) {
      if (mode !== "validate-only" || !probeId || !/^[A-Za-z0-9_-]{16,128}$/.test(probeId)) {
        return NextResponse.json({ error: "invalid_payment_probe" }, { status: 400 });
      }
      const validation = await validatePortal(payload, {
        "X-Egbe-Payment-Probe": mode,
        "X-Egbe-Payment-Probe-ID": probeId,
      });
      if (!validation.valid || !validation.validation_receipt) {
        throw new Error("Egbe Payments returned no portal validation receipt");
      }
      return NextResponse.json({
        validation_only: true,
        operation: "portal",
        valid: true,
        validation_receipt: validation.validation_receipt,
      });
    }
    const portal = await createPortal(payload);
    if (!portal.url) throw new Error("Egbe Payments returned no Customer Portal URL");
    if (request.headers.get("accept")?.includes("application/json")) {
      return NextResponse.json({ url: portal.url });
    }
    return NextResponse.redirect(portal.url, 303);
  } catch (error) {
    if (error instanceof ProductAuthenticationRequired) {
      return NextResponse.json({ error: "authentication_required" }, { status: 401 });
    }
    console.error("billing portal failed", error);
    return NextResponse.json({ error: "billing_portal_unavailable" }, { status: 503 });
  }
}

import { NextResponse } from "next/server";

import { ProductAuthenticationRequired, requireProductAccount } from "@/lib/egbe-product";
import { readBillingState } from "@/lib/egbe-billing/repository";

export async function GET(): Promise<NextResponse> {
  try {
    const account = await requireProductAccount();
    const state = await readBillingState(account.id);
    return NextResponse.json({
      plan_key: state.planKey,
      subscription_status: state.status,
      current_period_end: state.currentPeriodEnd?.toISOString() ?? null,
      cancel_at_period_end: state.cancelAtPeriodEnd,
    });
  } catch (error) {
    if (error instanceof ProductAuthenticationRequired) {
      return NextResponse.json({ error: "authentication_required" }, { status: 401 });
    }
    return NextResponse.json({ error: "billing_status_unavailable" }, { status: 503 });
  }
}

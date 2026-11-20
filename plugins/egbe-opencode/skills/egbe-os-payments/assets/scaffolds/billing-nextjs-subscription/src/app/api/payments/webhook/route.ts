import { NextRequest, NextResponse } from "next/server";

import {
  applyLiveBillingEvent,
  readBillingStateForEvent,
  type BillingEvent,
  type BillingTransition,
} from "@/lib/egbe-billing/repository";
import { reduceBillingEvent, testLifecycleState } from "@/lib/egbe-billing/lifecycle.mjs";
import { verifyPaymentSignature } from "@/lib/egbe-billing/signature.mjs";

const simulatedEvents = new Set<string>();

export async function POST(request: NextRequest): Promise<NextResponse> {
  const rawBody = await request.text();
  const secret = process.env.EGBE_PAYMENT_WEBHOOK_SECRET;
  if (!secret) return NextResponse.json({ error: "webhook_not_configured" }, { status: 503 });
  try {
    verifyPaymentSignature(rawBody, request.headers.get("x-egbe-payment-signature"), secret);
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "invalid_signature" }, { status: 400 });
  }
  let event: Record<string, unknown>;
  try {
    event = JSON.parse(rawBody) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "invalid_event_json" }, { status: 400 });
  }
  const eventId = String(event.id || "");
  const eventType = String(event.type || "");
  const eventCreated = Number(event.created || 0);
  if (!eventId || !eventType || !Number.isSafeInteger(eventCreated) || eventCreated < 1) {
    return NextResponse.json({ error: "invalid_event" }, { status: 400 });
  }
  const billingEvent = event as BillingEvent;
  const object = (event.data as { object?: Record<string, unknown> } | undefined)?.object ?? {};
  const metadata = (object.metadata as Record<string, unknown> | undefined) ?? {};
  const testEvent = event.livemode === false || metadata.egbe_test || request.headers.get("x-egbe-payment-test") === "1";
  if (testEvent) {
    const duplicate = simulatedEvents.has(eventId);
    simulatedEvents.add(eventId);
    if (simulatedEvents.size > 500) simulatedEvents.delete(simulatedEvents.values().next().value as string);
    const scenario = String(metadata.egbe_lifecycle_test_scenario || "");
    const transition = reduceBillingEvent(testLifecycleState(event, scenario), event) as BillingTransition;
    return NextResponse.json({
      contract_version: 1,
      test_event: true,
      accepted: true,
      duplicate,
      event_id: eventId,
      event_type: eventType,
      transition: { subscription_status: transition.subscription_status },
      side_effects_applied: false,
    });
  }
  try {
    const current = await readBillingStateForEvent(billingEvent);
    const transition = reduceBillingEvent(current, event) as BillingTransition;
    const result = await applyLiveBillingEvent(billingEvent, transition);
    return NextResponse.json({ accepted: true, duplicate: result.duplicate, stale: result.stale });
  } catch (error) {
    console.error("payment webhook commit failed", error);
    return NextResponse.json({ error: "payment_event_not_committed" }, { status: 503 });
  }
}

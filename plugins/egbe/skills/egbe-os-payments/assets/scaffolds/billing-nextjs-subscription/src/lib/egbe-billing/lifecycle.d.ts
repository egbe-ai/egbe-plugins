import type { BillingTransition } from "./repository";

export function reduceBillingEvent(
  current: Record<string, unknown>,
  event: Record<string, unknown>,
): BillingTransition;

export function testLifecycleState(
  event: Record<string, unknown>,
  scenario: string,
): Record<string, unknown>;

export function shouldApplyPaymentEvent(
  previousCreated: number,
  nextCreated: number,
): boolean;

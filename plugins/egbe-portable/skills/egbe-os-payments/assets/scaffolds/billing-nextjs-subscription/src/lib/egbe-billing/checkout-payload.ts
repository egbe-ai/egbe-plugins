import type { ProductAccount } from "@/lib/egbe-product";

import type { CheckoutDiscount, CheckoutPayload } from "./os-client";
import type { BillingState, CheckoutAttempt } from "./repository";

type BuildCheckoutPayloadInput = {
  account: ProductAccount;
  state: BillingState;
  attempt: CheckoutAttempt;
  appSlug: string;
  priceId: string;
  origin: string;
  discount?: CheckoutDiscount;
  allowPromotionCodes?: boolean;
};

export function buildCheckoutPayload({
  account,
  state,
  attempt,
  appSlug,
  priceId,
  origin,
  discount,
  allowPromotionCodes,
}: BuildCheckoutPayloadInput): CheckoutPayload {
  if (discount && allowPromotionCodes === true) {
    throw new Error("Automatic discounts and customer-entered promotion codes are mutually exclusive");
  }
  return {
    price: priceId,
    mode: "subscription",
    ...(state.customerId ? { customer: state.customerId } : { customer_email: account.email }),
    client_reference_id: account.id,
    success_url: new URL(attempt.returnPath, origin).toString(),
    cancel_url: new URL("/account/billing?checkout=canceled", origin).toString(),
    app_slug: appSlug,
    webhook_path: "/api/payments/webhook",
    allow_promotion_codes: discount ? false : (allowPromotionCodes ?? true),
    ...(discount ? { discounts: [discount] } : {}),
    metadata: {
      plan_key: attempt.planKey,
      checkout_attempt_id: attempt.id,
      ...attempt.attribution,
    },
  };
}

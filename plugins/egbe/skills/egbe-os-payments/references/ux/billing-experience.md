# Billing Experience

Use the product's established account layout and design system.

The account billing surface should show:

- current plan and normalized status;
- amount, currency, and billing interval;
- renewal date or effective cancellation/end date;
- a clear warning for `past_due`, `canceling`, or `paused`;
- upgrade/start action for a free account;
- manage billing or reactivate action for an existing customer;
- access to plan changes, cancellation, payment methods, and invoice history
  through Customer Portal.

The shared authenticated user menu should show a compact plan label. Add a
warning treatment only when the user needs to act; do not turn the navigation
into a full billing card.

Expose stable semantic markers on the live interface so account behavior can be
verified without depending on visual copy:

- `data-billing-page` on the protected billing surface;
- `data-billing-plan` and `data-billing-status` on current state;
- `data-billing-action="upgrade|manage|reactivate"` on the applicable enabled
  action;
- `data-billing-plan-badge` in the authenticated user menu;
- `data-billing-error` on a visible portal/provider error.

These markers supplement accessible labels; they do not replace them.

Create Customer Portal sessions on demand from a protected server route using
the stored owned customer id, deployed `app_slug`, and a fixed relative
`return_path`. Never expose a reusable portal URL, accept a customer id from the
browser, or accept a browser-selected absolute return URL. Use the non-mutating
portal validation endpoint before readiness.

Rendering the billing page is a read. It must not create a Stripe Customer,
Checkout Session, or Customer Portal Session. A free account without a stored
customer shows the upgrade flow. Customer creation may occur only inside an
explicit idempotent checkout mutation, and portal creation may occur only after
an explicit manage action for an existing owned customer.

If portal creation fails because of provider configuration, ownership,
permission, or availability, keep the current billing state intact. Show a
plain-language error near the action, preserve navigation, and offer retry. Do
not claim that a plan changed or cancellation succeeded.

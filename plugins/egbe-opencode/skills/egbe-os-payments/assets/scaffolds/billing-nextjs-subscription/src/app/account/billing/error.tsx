"use client";

export default function BillingError({ reset }: { reset: () => void }) {
  return (
    <main data-billing-page>
      <h1>Billing</h1>
      <p data-billing-error>Billing information is temporarily unavailable.</p>
      <button type="button" onClick={reset}>Try again</button>
    </main>
  );
}

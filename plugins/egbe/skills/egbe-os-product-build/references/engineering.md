# Engineering planning

Inspect the repository, framework, dependencies, deployed identity, storage and
affected callers before writing the plan. Reuse established libraries and sound
existing patterns; do not copy a weak local precedent when a relevant, safer
implementation already exists elsewhere in the product. Keep unrelated work intact.

## Close the real behavior

Map each accepted requirement to implementation and proof, or an explicitly deferred
scope. Include nonvisual obligations without inventing screens. Shared mechanisms
need one owner; consumers name the actual output they depend on. Order work by those
dependencies, not by a universal Auth/Product/Billing sequence. Split independently
deliverable and recoverable outcomes when one large task would hide their gaps.

Trace the initiating action, real producer, authoritative state, consumer/application,
visible result and recovery. A readable status, table or interface is not a completed
behavior. State must survive its promised boundary: request, redirect, retry, login,
later session or deployment. Identify the smallest production-capable missing
foundation; absence in the repository is work to implement, not permission to fake
the result or defer it silently.

Read the planned steps literally: could every one be finished while a necessary
producer, transformation, delivery or consumer is still missing? Correct that gap.
Keep producer proof with its producer and combined behavior with the first consumer
where the required real outputs exist. A stub for a later component does not prove
that component or the integrated journey.

## State and access boundaries

For a result coupled to a state change or consumption of a right, use a stable
logical operation identity. Delivery, failure, duplicates, retries, concurrency
and partial failures must converge without double delivery, double spending or
contradictory authority. Choose transactions, idempotency, durable retry or
compensation from the real boundaries; do not assume one transaction spans external
providers. Add consumption bookkeeping only to rights that actually deplete.

Across guest/account or other identity transitions, preserve the actual work,
purchase, prior decisions and consumed capacity without granting them to another
person. A typed email or client-side ID is not proof of ownership. Use the Auth
contract and verified server-side linkage; avoid independent authorities or a reset
at registration. Keep product credentials separate from agent/control-plane credentials.

Authorize private results at every access path: page, API, storage/download and
email link. Apply the accepted roles/sharing policy. A hard-to-guess object ID is
not authorization; an explicitly intended bearer access link requires its own
secure, scoped lifecycle. Never expose secrets, customer data or a test-login bypass
to make verification easier.

## Implementable design and code quality

Choose modules, interfaces, schema changes and tests after inspecting the system.
Record consequential choices and alternatives in the current work plan, not a second
architecture ledger. Changes to accepted behavior or cross-boundary contracts need
that decision resolved; internal implementation choices need not reopen the product.

- Group cohesive features into directories with clear responsibilities. Separate
  orchestration, UI, domain behavior and external effects where they vary independently;
  do not accumulate an entire feature in a flat module or giant view by convenience.
- Reuse shared logic when it represents the same responsibility; avoid both copied
  behavior and speculative abstractions. Preserve the product's performance,
  availability, accessibility and security requirements in the plan and checks.
- Add fallback/legacy paths only for an evidenced supported caller or operational
  need, with an explicit authority, observable failure behavior and removal condition.
  Do not silently return canned success or preserve obsolete branches without a consumer.
- Plan migrations and recovery for existing customer data. Do not replace durable
  storage with memory or rebuild the app merely to simplify a local change.

Before editing, keep a proportional checklist of implementation and direct proof in
the existing work record. Group cases that prove the same boundary, not one document
or TODO for every negative case. Missing inputs block only dependent work; keep the
specific gap and continuation explicit.

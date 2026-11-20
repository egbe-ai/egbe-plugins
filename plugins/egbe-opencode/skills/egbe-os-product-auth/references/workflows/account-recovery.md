# Password Recovery And Email Verification

Use this workflow only when password recovery or a separate email-verification
step is in scope. Passwordless account entry belongs to
`references/workflows/passwordless-email.md`.

1. Read the live Egbe OS `egbe-os-mail` skill and use its supported delivery path.
2. Generate random, single-use, short-lived tokens and store only token hashes.
3. Bind tokens to one purpose and user. Invalidate them after use and after a
   newer token is issued.
4. Always return a neutral response from recovery requests so account existence
   is not disclosed.
5. Build links from the verified deployed HTTPS host and a same-origin path.
6. After reset, revoke older sessions and create a fresh session only after the
   new credential succeeds.
7. Consume a token atomically so concurrent requests cannot both succeed.
8. Verify the actual email and live link before promising recovery or
   verification in the UI.

Canonical analytics names and delivery remain owned by the Egbe OS `egbe-os-analytics`
skill. Add events such as email verification only through its analytics
workflow.

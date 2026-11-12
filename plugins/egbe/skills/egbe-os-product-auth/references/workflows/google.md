# Google account entry

Use this workflow when Google is a selected account-entry method or its existing
implementation needs repair. Egbe OS owns OAuth; this product owns the local
account and session.

First discover and read the live capability contract:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/auth/google/skill" -s
```

Implement the server-side intent and exchange flow exactly from that contract.
Do not copy provider endpoints into browser code, invent another OAuth client,
or put `OS_API_KEY` in a client bundle. Use the real deployed slug and a safe
relative product callback/continuation.

Use a durable external-identity mapping whose authority is `(provider,
subject)`. `email` is verified linking information, not the provider key. When
the verified Google email already belongs to a local user, link that existing
account transactionally and preserve its password or passwordless state. When
it does not, create the user and link once. Create the ordinary product session
only after the one-time Egbe exchange succeeds.

Expose Google on the agreed account-entry surfaces with the selected hierarchy.
It may be the only method; do not add email login to implement or verify it.

Completion requires a live Google signup, repeat Google login to the same local
account, verified-email linking to an existing local account, session persistence,
continuation, logout, and protected denial after logout. Check linking with an
existing or controlled imported account even in a Google-only product, preserving
its credentials and ownership; this does not require exposing another login
method. For a bounded repair, exercise the affected Google behavior and shared
dependencies rather than expanding the implementation.

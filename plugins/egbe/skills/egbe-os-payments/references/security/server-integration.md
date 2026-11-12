# Server Integration And Credentials

The deployed product backend uses the same canonical OS contract as every other
product capability: server-only `OS_URL` and `OS_API_KEY`. Site Gateway injects
the product-purpose identity authoritatively; the agent must not receive, mint,
copy, rename, or deploy it.

The product webhook secret proves webhook authenticity and is not an OS access
credential. Obtain the current product secret from
`GET /payments/webhook-secret` with the current workload credential and pass
only `EGBE_PAYMENT_WEBHOOK_SECRET` as a server-only runtime environment value
through the active Egbe OS deployment mechanism. Capture the response without
printing it. Never write the secret to source, a repository env file, or a
durable workflow artifact.

The deployment mechanism may authoritatively set or refresh the same value with
the current product secret. This is intentional and does not change the agent
workflow.

Never place these values in source, browser bundles, logs, analytics payloads,
or `NEXT_PUBLIC_*` variables. Product routes must call OS from the server.

The deploy mechanism preserves the secret during code-only redeploys. A later
full env update must keep the current product webhook secret. Product OS
credential rotation is owned by the platform and takes effect on the next
deployment.

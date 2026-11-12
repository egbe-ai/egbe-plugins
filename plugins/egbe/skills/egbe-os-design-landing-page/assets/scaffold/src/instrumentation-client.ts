import * as Sentry from "@sentry/nextjs";

import { egbeObservability } from "@/lib/egbe-observability.generated";

if (egbeObservability.sentryDsn) {
  Sentry.init({
    dsn: egbeObservability.sentryDsn,
    tracesSampleRate: 0,
  });
  Sentry.setTag("product_slug", egbeObservability.productSlug);
  Sentry.setTag("openclaw_instance", egbeObservability.instanceId);
  Sentry.setTag("runtime_target", "web");
}

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;

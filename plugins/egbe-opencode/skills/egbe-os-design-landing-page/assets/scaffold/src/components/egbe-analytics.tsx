import Script from "next/script";

import { egbeObservability } from "@/lib/egbe-observability.generated";

export function EgbeAnalytics() {
  const { analytics } = egbeObservability;
  if (!analytics.websiteId || !analytics.scriptUrl) return null;

  return (
    <>
      <Script
        id="egbe-umami"
        src={analytics.scriptUrl}
        data-website-id={analytics.websiteId}
        data-host-url={analytics.hostUrl || undefined}
        data-performance="true"
        strategy="afterInteractive"
      />
      <Script
        id="egbe-umami-recorder"
        src={analytics.recorderScriptUrl}
        defer
        data-website-id={analytics.websiteId}
        data-sample-rate={analytics.replayConfig.sampleRate}
        data-mask-level={analytics.replayConfig.maskLevel}
        data-max-duration={analytics.replayConfig.maxDuration}
        data-block-selector={analytics.replayConfig.blockSelector || undefined}
        strategy="afterInteractive"
      />
      {analytics.inlineScript ? (
        <Script
          id="egbe-attribution"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{ __html: analytics.inlineScript }}
        />
      ) : null}
    </>
  );
}

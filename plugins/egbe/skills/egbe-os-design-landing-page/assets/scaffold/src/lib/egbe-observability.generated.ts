// Public identifiers only. Populate from the product's OS analytics/errors
// bindings before publication; the empty baseline only makes the template buildable.
export const egbeObservability = {
  productSlug: "",
  instanceId: "",
  sentryDsn: "",
  analytics: {
    websiteId: "",
    scriptUrl: "",
    hostUrl: "",
    inlineScript: "",
    recorderScriptUrl: "",
    replayConfig: {
      sampleRate: 1.0,
      maskLevel: "moderate",
      maxDuration: 1800000,
      blockSelector: "",
    },
  },
} as const;

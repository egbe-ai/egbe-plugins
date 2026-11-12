"use strict";

const GTM_IDENTITY_FIELDS = Object.freeze([
  "business_id",
  "product_id",
  "launch_id",
  "experiment_id",
  "variant_id",
]);

const STABLE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const INSTANTLY_PROVIDER = "instantly";
const INSTANTLY_UTM_MEDIUM = "email";

function assertStableGtmIdentifiers(record, label) {
  if (!record || typeof record !== "object" || Array.isArray(record)) {
    throw new Error(`${label} must be a JSON object`);
  }

  for (const field of GTM_IDENTITY_FIELDS) {
    const value = record[field];
    if (value == null) continue;
    if (typeof value !== "string" || !STABLE_ID_PATTERN.test(value)) {
      throw new Error(
        `${label}.${field} must be a stable GTM identifier when provided`,
      );
    }
  }
}

function reconcileRunIdentity(manifest, spec) {
  assertStableGtmIdentifiers(manifest, "manifest");
  assertStableGtmIdentifiers(spec, "run spec");

  const incomingRunKey = spec.run_key;
  const storedRunKey = manifest.run_key;
  if (storedRunKey != null && storedRunKey !== incomingRunKey) {
    throw new Error(
      `Immutable Instantly run identity conflict for run_key: manifest has "${storedRunKey}" but run spec has "${incomingRunKey}"`,
    );
  }
  for (const field of GTM_IDENTITY_FIELDS) {
    const stored = manifest[field];
    const incoming = spec[field];
    if (stored != null && incoming != null && stored !== incoming) {
      throw new Error(
        `Immutable Instantly run identity conflict for ${field}: manifest has "${stored}" but run spec has "${incoming}"`,
      );
    }
  }

  if (storedRunKey == null) manifest.run_key = incomingRunKey;
  for (const field of GTM_IDENTITY_FIELDS) {
    const stored = manifest[field];
    const incoming = spec[field];
    if (stored != null && incoming == null) spec[field] = stored;
    if (stored == null && incoming != null) manifest[field] = incoming;
  }

  return { manifest, spec };
}

function reconcileInstantlyAttribution(
  record,
  { runKey, campaignId = null, label = "artifact" },
) {
  if (!record || typeof record !== "object" || Array.isArray(record)) {
    throw new Error(`${label} must be a JSON object`);
  }
  if (typeof runKey !== "string" || !runKey) {
    throw new Error("run_key is required for Instantly attribution");
  }

  const campaignCandidates = [
    ["campaign.id", record.campaign?.id ?? null],
    ["campaign_id", record.campaign_id ?? null],
    ["provider_campaign_id", record.provider_campaign_id ?? null],
    ["expected provider_campaign_id", campaignId],
  ].filter(([, value]) => value != null && value !== "");
  if (campaignCandidates.length > 1) {
    const expected = String(campaignCandidates[0][1]);
    const conflict = campaignCandidates.find(
      ([, value]) => String(value) !== expected,
    );
    if (conflict) {
      throw new Error(
        `Immutable Instantly attribution conflict for provider_campaign_id: ${campaignCandidates[0][0]} has "${expected}" but ${conflict[0]} has "${conflict[1]}"`,
      );
    }
  }

  const canonical = {
    provider: INSTANTLY_PROVIDER,
    utm_source: INSTANTLY_PROVIDER,
    utm_medium: INSTANTLY_UTM_MEDIUM,
    utm_campaign: runKey,
  };
  for (const [field, expected] of Object.entries(canonical)) {
    if (record[field] != null && record[field] !== expected) {
      throw new Error(
        `Immutable Instantly attribution conflict for ${field}: ${label} has "${record[field]}" but expected "${expected}"`,
      );
    }
  }
  for (const [field, expected] of Object.entries(canonical)) {
    record[field] = expected;
  }

  const providerCampaignId = campaignCandidates.length
    ? String(campaignCandidates[0][1])
    : null;
  if (providerCampaignId) record.provider_campaign_id = providerCampaignId;

  return { ...canonical, provider_campaign_id: providerCampaignId };
}

module.exports = {
  GTM_IDENTITY_FIELDS,
  STABLE_ID_PATTERN,
  INSTANTLY_PROVIDER,
  INSTANTLY_UTM_MEDIUM,
  assertStableGtmIdentifiers,
  reconcileRunIdentity,
  reconcileInstantlyAttribution,
};

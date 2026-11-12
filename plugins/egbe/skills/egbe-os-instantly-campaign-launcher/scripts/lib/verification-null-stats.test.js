#!/usr/bin/env node
// Runtime tests for waitForVerification's null-lead_stats triage. When
// lead_stats is null the gate first falls back to the per-lead
// verification_status (preflight-verification-fallback.test.js covers that
// path). When neither source yields numbers for N polls it must cross-check
// the leads API and either report a degraded read surface (#3790) — flagged
// verification_unread so the launcher does not activate — or abort (import
// actually failed) instead of burning the full timeout.
//
// Run: node scripts/lib/verification-null-stats.test.js

const fs = require("node:fs");
const path = require("node:path");

const SOURCE = fs.readFileSync(
  path.resolve(__dirname, "..", "launch-campaign.js"),
  "utf8",
);

function loadFn() {
  const constsBlock = SOURCE.match(
    /const LEAD_VERIFICATION_VALID[\s\S]*?const LEAD_VERIFICATION_PENDING[^\n]*\n/,
  );
  // listCampaignLeads, readLeadVerification, removeDroppedInvalidLeads.
  const readerBlock = SOURCE.match(
    /async function listCampaignLeads\b[\s\S]*?\nasync function removeDroppedInvalidLeads\b[\s\S]*?\n\}\n/,
  );
  const fnBlock = SOURCE.match(
    /async function waitForVerification\b[\s\S]*?\n\}\n/,
  );
  if (!constsBlock || !readerBlock || !fnBlock) {
    throw new Error("could not extract waitForVerification from source");
  }
  const exporter = new Function(
    `let __failed = null;
     // Shadow setTimeout so the 15s poll interval collapses to a microtask.
     const setTimeout = (fn) => fn();
     const console = { log() {}, error() {} };
     function fail(msg) { __failed = msg; throw new Error("__verify_fail__"); }
     ${constsBlock[0]}
     ${readerBlock[0]}
     ${fnBlock[0]}
     return {
       waitForVerification,
       lastFailure: () => __failed,
       resetFailure: () => { __failed = null; },
     };`,
  );
  return exporter();
}

const { waitForVerification, lastFailure, resetFailure } = loadFn();

// listLeads mirrors countLeadsResult unless given: readable leads WITHOUT a
// verification_status field (the per-lead fallback has nothing to count), or
// the same error status when the leads API is down.
function stubClient({
  leadStats = null,
  countLeadsResult,
  analyticsStatus = 200,
  detailsStatus = 200,
  listLeadsResult,
}) {
  const calls = { polls: 0, countLeads: 0, listLeads: 0 };
  const leadsPage =
    listLeadsResult ||
    (countLeadsResult.ok
      ? {
          status: 200,
          body: {
            items: Array.from({ length: countLeadsResult.total }, (_, i) => ({
              id: `l${i}`,
              email: `lead${i}@example.test`,
            })),
          },
        }
      : { status: countLeadsResult.status, body: null });
  return {
    calls,
    campaignAnalytics: async () => ({ status: analyticsStatus, body: {} }),
    getCampaign: async () => {
      calls.polls += 1;
      return { status: detailsStatus, body: { lead_stats: leadStats } };
    },
    listLeads: async () => {
      calls.listLeads += 1;
      return leadsPage;
    },
    countLeads: async () => {
      calls.countLeads += 1;
      return countLeadsResult;
    },
  };
}

const SPEC = {
  campaign: { verification_stuck_polls: 3, verification_timeout_minutes: 45 },
};

let failed = 0;
function check(name, cond, ...detail) {
  if (cond) {
    console.log(`OK   ${name}`);
  } else {
    console.error(`FAIL ${name}`, ...detail);
    failed += 1;
  }
}

(async () => {
  // 1. Leads API confirms the import — proceed as degraded, don't time out.
  resetFailure();
  const degradedClient = stubClient({
    countLeadsResult: { ok: true, status: 200, total: 42, contacted: 0 },
  });
  const degraded = await waitForVerification(degradedClient, "camp-1", SPEC, {
    importedCount: 42,
  });
  check(
    "degraded read surface: returns after stuck-poll limit with leads-api total",
    degraded?.degraded_read_surface === true && degraded.totalLeads === 42,
    degraded,
  );
  check(
    "degraded read surface: flagged verification_unread (launcher must not auto-activate)",
    degraded?.verification_unread === true &&
      /gate was NOT enforced/.test(degraded.stuck_reason || "") &&
      /exposes no per-lead verification_status/.test(degraded.stuck_reason || ""),
    degraded,
  );
  check(
    "degraded read surface: per-lead fallback was tried on every null poll",
    degradedClient.calls.listLeads === 3,
    degradedClient.calls,
  );
  check(
    "degraded read surface: fail-fast, not timeout (3 polls, 1 countLeads)",
    degradedClient.calls.polls === 3 && degradedClient.calls.countLeads === 1,
    degradedClient.calls,
  );

  // 2. Leads API readable and empty — the import failed; the function
  // returns import_failed so the caller can roll back lead hashes first.
  resetFailure();
  const emptyClient = stubClient({
    countLeadsResult: { ok: true, status: 200, total: 0, contacted: 0 },
  });
  const importFailed = await waitForVerification(emptyClient, "camp-2", SPEC, {
    importedCount: 50,
  });
  check(
    "empty leads API: returns import_failed with diagnosis (caller rolls back hashes)",
    importFailed?.import_failed === true &&
      (importFailed.import_failure_reason || "").includes(
        "import most likely failed",
      ),
    importFailed,
  );

  // 3. Leads API also unreadable — proceed as degraded (import call was 2xx).
  resetFailure();
  const downClient = stubClient({
    countLeadsResult: { ok: false, status: 404, total: 0, contacted: 0 },
  });
  const bothDown = await waitForVerification(downClient, "camp-3", SPEC, {
    importedCount: 17,
  });
  check(
    "both read surfaces down: degraded + verification_unread with importedCount total",
    bothDown?.degraded_read_surface === true &&
      bothDown.verification_unread === true &&
      bothDown.totalLeads === 17,
    bothDown,
  );

  // 4a. Analytics route down must NOT short-circuit the poll: the triage
  // still runs off campaign details (the #3797 production failure had
  // campaigns/analytics 404ing the whole time).
  resetFailure();
  const analyticsDownClient = stubClient({
    analyticsStatus: 404,
    countLeadsResult: { ok: true, status: 200, total: 42, contacted: 0 },
  });
  const analyticsDown = await waitForVerification(
    analyticsDownClient,
    "camp-5",
    SPEC,
    { importedCount: 42 },
  );
  check(
    "analytics 404: poll continues to details and triage still fires",
    analyticsDown?.degraded_read_surface === true &&
      analyticsDownClient.calls.polls === 3,
    analyticsDown,
    analyticsDownClient.calls,
  );

  // 4b. Details route down entirely: counted toward the triage instead of
  // silently burning the timeout.
  resetFailure();
  const detailsDownClient = stubClient({
    detailsStatus: 502,
    countLeadsResult: { ok: true, status: 200, total: 42, contacted: 0 },
  });
  const detailsDown = await waitForVerification(
    detailsDownClient,
    "camp-6",
    SPEC,
    { importedCount: 42 },
  );
  check(
    "details unreadable: triage fires after stuck-poll limit",
    detailsDown?.degraded_read_surface === true &&
      detailsDownClient.calls.polls === 3,
    detailsDown,
    detailsDownClient.calls,
  );

  // 4c. Batch reconciliation: 0 uploaded + 0 already-present means the new
  // batch never landed — import_failed even when the leads API shows OLD
  // leads (reused campaign) and without consulting it.
  resetFailure();
  const neverLandedClient = stubClient({
    countLeadsResult: { ok: true, status: 200, total: 500, contacted: 100 },
  });
  const neverLanded = await waitForVerification(
    neverLandedClient,
    "camp-7",
    SPEC,
    { importedCount: 0, skippedCount: 0 },
  );
  check(
    "0 uploaded + 0 skipped: import_failed even with old leads visible",
    neverLanded?.import_failed === true &&
      (neverLanded.import_failure_reason || "").includes("never landed") &&
      neverLandedClient.calls.countLeads === 0 &&
      neverLandedClient.calls.listLeads === 0,
    neverLanded,
    neverLandedClient.calls,
  );

  // 4d. skippedCount > 0 (rerun, everything already present) still counts as
  // a landed batch — degraded proceed, not import_failed.
  resetFailure();
  const rerunClient = stubClient({
    countLeadsResult: { ok: true, status: 200, total: 50, contacted: 0 },
  });
  const rerun = await waitForVerification(rerunClient, "camp-8", SPEC, {
    importedCount: 0,
    skippedCount: 50,
  });
  check(
    "0 uploaded but 50 already-present: proceeds as degraded",
    rerun?.degraded_read_surface === true && rerun.totalLeads === 50,
    rerun,
  );

  // 4. Healthy path unchanged: lead_stats present, nothing pending.
  resetFailure();
  const healthyClient = {
    campaignAnalytics: async () => ({ status: 200, body: {} }),
    getCampaign: async () => ({
      status: 200,
      body: {
        lead_stats: {
          total: 40,
          verified: 39,
          invalid: 1,
          pending_verification: 0,
        },
      },
    }),
    countLeads: async () => {
      throw new Error("countLeads must not be called on the healthy path");
    },
    listLeads: async () => {
      throw new Error("listLeads must not be called on the healthy path");
    },
  };
  const healthy = await waitForVerification(healthyClient, "camp-4", SPEC, {
    importedCount: 40,
  });
  check(
    "healthy path: verification completes without leads-api cross-check",
    healthy?.verifiedLeads === 39 &&
      healthy.invalidLeads === 1 &&
      !healthy.degraded_read_surface,
    healthy,
  );

  if (failed > 0) {
    console.error(`\n${failed} check(s) failed`);
    process.exit(1);
  }
  console.log("\nAll verification-null-stats checks passed");
})().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(1);
});

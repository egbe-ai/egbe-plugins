#!/usr/bin/env node
// Runtime tests for the verification gate's per-lead fallback. Fina run
// 2026-10-16: lead_stats came back empty 8 times, the launcher declared the
// read surface degraded (#3790) and skipped max_invalid_lead_pct — while the
// per-lead verification_status (GET /leads?campaign_id=…) showed 20 of 157
// invalid (12.7%). The gate must read the per-lead status instead of giving
// up, abort over the threshold with the invalid addresses, keep polling while
// leads are pending and end with "verification pending" (no activation) when
// the wait budget runs out.
//
// Run: node scripts/lib/preflight-verification-fallback.test.js

const fs = require("node:fs");
const path = require("node:path");

const SOURCE = fs.readFileSync(
  path.resolve(__dirname, "..", "launch-campaign.js"),
  "utf8",
);

function loadFns() {
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
  const decisionBlock = SOURCE.match(
    /function verificationActivationBlock\b[\s\S]*?\n\}\n/,
  );
  if (!constsBlock || !readerBlock || !fnBlock || !decisionBlock) {
    throw new Error("could not extract the verification gate from source");
  }
  const exporter = new Function(
    `let __failed = null;
     // Fake clock: every 15s poll advances it, so the wait budget runs out
     // without real waiting.
     let __now = 0;
     const Date = { now: () => __now };
     const setTimeout = (fn, ms) => { __now += ms || 0; fn(); };
     const console = { log() {}, error() {} };
     function fail(msg) { __failed = msg; throw new Error("__verify_fail__"); }
     ${constsBlock[0]}
     ${readerBlock[0]}
     ${fnBlock[0]}
     ${decisionBlock[0]}
     return {
       waitForVerification,
       readLeadVerification,
       removeDroppedInvalidLeads,
       verificationActivationBlock,
       lastFailure: () => __failed,
     };`,
  );
  return exporter();
}

const {
  waitForVerification,
  readLeadVerification,
  removeDroppedInvalidLeads,
  verificationActivationBlock,
  lastFailure,
} = loadFns();

let failed = 0;
function check(name, cond, ...detail) {
  if (cond) {
    console.log(`OK   ${name}`);
  } else {
    console.error(`FAIL ${name}`, ...detail);
    failed += 1;
  }
}

function makeLeads(spec) {
  // spec: array of [count, verification_status]
  const leads = [];
  for (const [count, status] of spec) {
    for (let i = 0; i < count; i++) {
      const n = leads.length;
      leads.push({
        id: `l${n}`,
        email: `Lead${n}@Example.test`,
        verification_status: status,
      });
    }
  }
  return leads;
}

// Paginates like the gateway: 100 per page, starting_after = last id.
// `timeline` is a list of lead arrays; poll k uses timeline[min(k, last)].
function stubClient({ timeline, leadStats = null, detailsStatus = 200 }) {
  const calls = { polls: 0, listLeads: 0, countLeads: 0 };
  let poll = -1;
  return {
    calls,
    campaignAnalytics: async () => ({ status: 404, body: null }),
    getCampaign: async () => {
      calls.polls += 1;
      poll += 1;
      const stats =
        typeof leadStats === "function" ? leadStats(poll) : leadStats;
      return { status: detailsStatus, body: { lead_stats: stats } };
    },
    listLeads: async (_campaignId, { limit = 100, starting_after } = {}) => {
      calls.listLeads += 1;
      const leads = timeline[Math.min(Math.max(poll, 0), timeline.length - 1)];
      const start = starting_after
        ? leads.findIndex((l) => l.id === starting_after) + 1
        : 0;
      return {
        status: 200,
        body: { items: leads.slice(start, start + limit) },
      };
    },
    countLeads: async () => {
      calls.countLeads += 1;
      throw new Error(
        "countLeads must not be needed when per-lead status is readable",
      );
    },
  };
}

const SPEC = {
  campaign: {
    verification_stuck_polls: 3,
    verification_timeout_minutes: 45,
    max_invalid_lead_pct: 5,
  },
};

(async () => {
  // 1. The Fina incident: lead_stats null, 20 of 157 invalid → abort with the
  //    addresses, no degraded proceed.
  const fina = makeLeads([
    [137, 1],
    [20, -1],
  ]);
  const finaClient = stubClient({ timeline: [fina] });
  const finaResult = await waitForVerification(finaClient, "camp", SPEC, {
    importedCount: 157,
  });
  check(
    "incident: gate_failed (not degraded) at 12.7% invalid",
    finaResult?.gate_failed === true &&
      !finaResult.degraded_read_surface &&
      finaResult.totalLeads === 157 &&
      finaResult.invalidLeads === 20 &&
      /12\.7% invalid \(threshold: 5%\)/.test(finaResult.failure_reason) &&
      /20 of 157 leads are invalid/.test(finaResult.failure_reason) &&
      /per-lead verification_status/.test(finaResult.failure_reason) &&
      /NOT activated/.test(finaResult.failure_reason),
    finaResult,
  );
  check(
    "incident: lists the 20 invalid addresses (lowercased) for state/invalid-leads.json",
    finaResult.invalid_leads?.length === 20 &&
      finaResult.invalid_leads[0].email === "lead137@example.test" &&
      finaResult.invalid_leads[0].verification_status === -1,
    finaResult.invalid_leads?.slice(0, 2),
  );
  check(
    "incident: paginated the 157 leads (2 pages) on the first poll, no countLeads",
    finaClient.calls.polls === 1 &&
      finaClient.calls.listLeads === 2 &&
      finaClient.calls.countLeads === 0,
    finaClient.calls,
  );

  // 2. Pending leads: keep polling, then pass under the threshold.
  const pendingThenDone = stubClient({
    timeline: [
      makeLeads([
        [30, 11],
        [10, 12],
      ]),
      makeLeads([
        [30, 1],
        [10, 11],
      ]),
      makeLeads([
        [39, 1],
        [1, -1],
      ]),
    ],
  });
  const passed = await waitForVerification(pendingThenDone, "camp", SPEC, {
    importedCount: 40,
  });
  check(
    "pending → verified: passes once nothing is pending, within threshold",
    passed &&
      !passed.gate_failed &&
      !passed.verification_pending &&
      passed.source === "per_lead_verification_status" &&
      passed.verifiedLeads === 39 &&
      passed.invalidLeads === 1 &&
      pendingThenDone.calls.polls === 3,
    passed,
    pendingThenDone.calls,
  );

  // 3. Still pending when the wait budget ends (pending keeps moving, so the
  //    stuck rule does not fire): verification_pending, not a crash, not a
  //    pass.
  const slow = stubClient({
    timeline: Array.from({ length: 8 }, (_, k) =>
      makeLeads([
        [40 + k, 1],
        [10 - k, 11],
      ]),
    ),
  });
  const pending = await waitForVerification(
    slow,
    "camp",
    { campaign: { ...SPEC.campaign, verification_timeout_minutes: 2 } },
    { importedCount: 50 },
  );
  check(
    "budget spent with pending leads: verification_pending with a rerun-later reason",
    pending?.verification_pending === true &&
      !pending.stuck &&
      !pending.gate_failed &&
      pending.pendingLeads === 3 &&
      /still pending after 2 minutes/.test(pending.pending_reason) &&
      /NOT activated/.test(pending.pending_reason) &&
      /Rerun the same launch command later/.test(pending.pending_reason) &&
      lastFailure() === null &&
      slow.calls.polls === 8,
    pending,
    slow.calls,
  );

  // 3b. Per-lead pending count unchanged for verification_stuck_polls polls:
  //     stuck → pending (blocked unless allow_unverified_activation).
  const stuck = stubClient({
    timeline: [
      makeLeads([
        [40, 1],
        [10, 11],
      ]),
    ],
  });
  const stuckPerLead = await waitForVerification(stuck, "camp", SPEC, {
    importedCount: 50,
  });
  check(
    "per-lead pending unchanged for 3 polls: stuck + verification_pending after 4 polls",
    stuckPerLead?.verification_pending === true &&
      stuckPerLead.stuck === true &&
      stuckPerLead.pendingLeads === 10 &&
      /Verification appears stuck: 10 leads still pending/.test(stuckPerLead.pending_reason) &&
      /source: per-lead verification_status/.test(stuckPerLead.pending_reason) &&
      /allow_unverified_activation/.test(stuckPerLead.pending_reason) &&
      stuck.calls.polls === 4,
    stuckPerLead,
    stuck.calls,
  );

  // 4. Invalid share already over the threshold while others are pending:
  //    abort early (pending leads can only add invalids).
  const earlyClient = stubClient({
    timeline: [
      makeLeads([
        [40, 11],
        [8, -1],
        [52, 1],
      ]),
    ],
  });
  const early = await waitForVerification(earlyClient, "camp", SPEC, {
    importedCount: 100,
  });
  check(
    "over threshold with leads still pending: aborts on the first poll",
    early?.gate_failed === true &&
      /8\.0% invalid/.test(early.failure_reason) &&
      /40 are still pending/.test(early.failure_reason) &&
      earlyClient.calls.polls === 1,
    early,
  );

  // 5. The gate counts the WHOLE campaign: leads that are no longer in the
  //    leads file but still in the campaign keep counting (they would be
  //    mailed) — the rerun deletes them first (removeDroppedInvalidLeads).
  const scoped = makeLeads([
    [45, 1],
    [5, -1],
  ]);
  const keep = new Set(scoped.slice(0, 47).map((l) => l.email.toLowerCase()));
  const wholeCampaign = await waitForVerification(
    stubClient({ timeline: [scoped] }),
    "camp",
    SPEC,
    { importedCount: 0, skippedCount: 47, fileEmails: keep, expectedLeads: 47 },
  );
  check(
    "per-lead: leads dropped from the file but still in the campaign count (5/50 fails)",
    wholeCampaign?.gate_failed === true &&
      wholeCampaign.totalLeads === 50 &&
      /10\.0% invalid/.test(wholeCampaign.failure_reason),
    wholeCampaign,
  );

  // 6. lead_stats over the threshold: no file-scoped exception any more.
  const rerun = await waitForVerification(
    stubClient({
      timeline: [scoped],
      leadStats: { total: 50, verified: 45, invalid: 5, pending_verification: 0 },
    }),
    "camp",
    SPEC,
    { importedCount: 0, skippedCount: 47, fileEmails: keep },
  );
  check(
    "lead_stats over threshold with leads dropped from the file: still gate_failed",
    rerun?.gate_failed === true && /source: campaign lead_stats/.test(rerun.failure_reason),
    rerun,
  );

  // 7. lead_stats over the threshold and no scope: gate_failed, addresses
  //    come from the per-lead listing.
  const statsFail = await waitForVerification(
    stubClient({
      timeline: [fina],
      leadStats: {
        total: 157,
        verified: 137,
        invalid: 20,
        pending_verification: 0,
      },
    }),
    "camp",
    SPEC,
    { importedCount: 157 },
  );
  check(
    "lead_stats over threshold: gate_failed with addresses from the leads listing",
    statsFail?.gate_failed === true &&
      /source: campaign lead_stats/.test(statsFail.failure_reason) &&
      statsFail.invalid_leads.length === 20,
    statsFail,
  );

  // 8. Other verification codes (risky / catch-all) are neither invalid nor
  //    pending.
  const other = await readLeadVerification(
    stubClient({
      timeline: [
        makeLeads([
          [3, 1],
          [1, -1],
          [1, -2],
          [1, -3],
          [2, 11],
          [1, 12],
        ]),
      ],
    }),
    "camp",
  );
  check(
    "readLeadVerification: -2/-3 count as risky, bad = invalid + risky",
    other.ok &&
      other.has_status &&
      other.total === 9 &&
      other.valid === 3 &&
      other.invalid === 1 &&
      other.risky === 2 &&
      other.bad === 3 &&
      other.pending === 3 &&
      other.invalid_leads.map((l) => `${l.kind}:${l.verification_status}`).join(",") ===
        "invalid:-1,risky:-2,risky:-3",
    other,
  );

  // 9. A listing without any verification_status field is not a verification
  //    source: has_status=false, so the gate falls through to the triage.
  const noField = await readLeadVerification(
    stubClient({ timeline: [[{ id: "a", email: "a@x.test" }]] }),
    "camp",
  );
  check(
    "readLeadVerification: no verification_status field → has_status=false",
    noField.ok && !noField.has_status && noField.total === 1,
    noField,
  );

  // 10. A cursor the gateway ignores (same page forever) is unreadable.
  const loopClient = {
    listLeads: async () => ({
      status: 200,
      body: { items: makeLeads([[100, 1]]) },
    }),
  };
  const loop = await readLeadVerification(loopClient, "camp");
  check(
    "readLeadVerification: ignored cursor → ok=false",
    loop.ok === false,
    loop,
  );

  // --- main(): activation and persistence contract (source checks) ---
  const main = SOURCE.slice(SOURCE.indexOf("async function main()"));
  // --- F1: a stuck lead_stats queue is pending, not a pass ---
  const stuckStats = { total: 50, verified: 40, invalid: 1, pending_verification: 9 };
  const stuckQueue = stubClient({ timeline: [[]], leadStats: stuckStats });
  const stuckResult = await waitForVerification(stuckQueue, "camp", SPEC, {
    importedCount: 50,
  });
  check(
    "stuck lead_stats queue: verification_pending + stuck, not a pass",
    stuckResult?.verification_pending === true &&
      stuckResult.stuck === true &&
      stuckResult.pendingLeads === 9 &&
      /Campaign was NOT activated/.test(stuckResult.pending_reason) &&
      /allow_unverified_activation/.test(stuckResult.pending_reason) &&
      stuckQueue.calls.polls === 4,
    stuckResult,
    stuckQueue.calls,
  );

  // --- F2: risky codes count as invalid; no file-scoped exception ---
  const riskyLeads = makeLeads([[47, 1], [1, -1], [2, -3]]);
  const riskyPerLead = await waitForVerification(
    stubClient({ timeline: [riskyLeads] }),
    "camp",
    SPEC,
    { importedCount: 50 },
  );
  check(
    "per-lead: catch-all (-3) counts as invalid for the threshold and is listed as risky",
    riskyPerLead?.gate_failed === true &&
      /6\.0% invalid/.test(riskyPerLead.failure_reason) &&
      /1 invalid \+ 2 risky \/ catch-all, counted as invalid/.test(riskyPerLead.failure_reason) &&
      riskyPerLead.invalid_leads.filter((l) => l.kind === "risky").length === 2,
    riskyPerLead,
  );
  const noDrop = await waitForVerification(
    stubClient({
      timeline: [riskyLeads],
      leadStats: { total: 50, verified: 47, invalid: 3, pending_verification: 0 },
    }),
    "camp",
    SPEC,
    {
      importedCount: 50,
      fileEmails: new Set(riskyLeads.map((l) => l.email.toLowerCase())),
    },
  );
  check(
    "lead_stats failure stands; catch-all leads listed among the addresses",
    noDrop?.gate_failed === true &&
      /source: campaign lead_stats/.test(noDrop.failure_reason) &&
      noDrop.invalid_leads.length === 3,
    noDrop,
  );

  // --- F4: a lagging leads listing must not pass ---
  const lagging = stubClient({
    timeline: [makeLeads([[10, 1]]), makeLeads([[10, 1]]), makeLeads([[50, 1]])],
  });
  const fifty = new Set(makeLeads([[50, 1]]).map((l) => l.email.toLowerCase()));
  const lagResult = await waitForVerification(lagging, "camp", SPEC, {
    importedCount: 50,
    fileEmails: fifty,
    expectedLeads: 50,
  });
  check(
    "10 of 50 expected leads visible: keeps polling, passes only when all 50 are verified",
    lagResult &&
      !lagResult.gate_failed &&
      !lagResult.verification_pending &&
      lagResult.totalLeads === 50 &&
      lagging.calls.polls === 3,
    lagResult,
    lagging.calls,
  );
  const neverVisible = await waitForVerification(
    stubClient({ timeline: [makeLeads([[10, 1]])] }),
    "camp",
    { campaign: { ...SPEC.campaign, verification_timeout_minutes: 1 } },
    { importedCount: 50, fileEmails: fifty, expectedLeads: 50 },
  );
  check(
    "expected leads never all visible: verification_pending (missing leads counted as pending)",
    neverVisible?.verification_pending === true &&
      neverVisible.pendingLeads === 40 &&
      neverVisible.totalLeads === 50,
    neverVisible,
  );
  const lagInvalid = await waitForVerification(
    stubClient({ timeline: [makeLeads([[7, 1], [3, -1]])] }),
    "camp",
    SPEC,
    { importedCount: 50, fileEmails: fifty, expectedLeads: 50 },
  );
  check(
    "early abort uses the expected total as denominator (3/50 = 6%)",
    lagInvalid?.gate_failed === true && /6\.0% invalid/.test(lagInvalid.failure_reason),
    lagInvalid,
  );

  // --- Rerun cleanup: leads dropped from the file are deleted from the campaign ---
  function cleanupClient({ live, deleteStatus = () => 200, listStatus = 200 }) {
    const deletes = [];
    return {
      deletes,
      listLeads: async () =>
        listStatus === 200
          ? { status: 200, body: { items: live } }
          : { status: listStatus, body: null },
      deleteLead: async (id) => {
        deletes.push(id);
        return { status: deleteStatus(id), body: null };
      },
    };
  }
  const record = {
    campaign_id: "camp",
    leads: [
      { email: "bad1@x.test", id: "old-1", verification_status: -1, kind: "invalid" },
      { email: "bad2@x.test", id: "old-2", verification_status: -3, kind: "risky" },
      { email: "gone@x.test", id: "old-3", verification_status: -1, kind: "invalid" },
      { email: "kept@x.test", id: "old-4", verification_status: -1, kind: "invalid" },
    ],
  };
  const live = [
    { id: "L1", email: "Bad1@x.test" },
    { id: "L2", email: "bad2@x.test" },
    { id: "L4", email: "kept@x.test" },
    { id: "L5", email: "ok@x.test" },
  ];
  const fileNow = new Set(["kept@x.test", "ok@x.test"]);
  const okClient = cleanupClient({ live });
  const cleaned = await removeDroppedInvalidLeads(okClient, "camp", record, fileNow);
  check(
    "cleanup: deletes dropped invalid AND risky leads by their live id, not the dropped-from-file kept one",
    cleaned.ok &&
      okClient.deletes.join(",") === "L1,L2" &&
      cleaned.deleted.map((d) => `${d.email}:${d.kind}`).join(",") ===
        "bad1@x.test:invalid,bad2@x.test:risky" &&
      cleaned.already_absent.join(",") === "gone@x.test" &&
      cleaned.kept_in_file.join(",") === "kept@x.test",
    cleaned,
  );
  const failClient = cleanupClient({ live, deleteStatus: (id) => (id === "L2" ? 502 : 200) });
  const failedCleanup = await removeDroppedInvalidLeads(failClient, "camp", record, fileNow);
  check(
    "cleanup: a failed delete (502, not retried) reports ok=false with the lead",
    failedCleanup.ok === false &&
      failClient.deletes.join(",") === "L1,L2" &&
      failedCleanup.failed.length === 1 &&
      failedCleanup.failed[0].email === "bad2@x.test" &&
      failedCleanup.failed[0].status === 502 &&
      failedCleanup.deleted.length === 1,
    failedCleanup,
  );
  const unreadable = await removeDroppedInvalidLeads(
    cleanupClient({ live, listStatus: 404 }),
    "camp",
    record,
    fileNow,
  );
  check(
    "cleanup: unreadable campaign listing → ok=false, nothing deleted",
    unreadable.ok === false && unreadable.deleted.length === 0 && unreadable.failed.length === 3,
    unreadable,
  );
  const nothingDropped = await removeDroppedInvalidLeads(
    { listLeads: async () => { throw new Error("must not list"); } },
    "camp",
    { leads: [{ email: "kept@x.test", id: "x" }] },
    fileNow,
  );
  check("cleanup: nothing dropped → no listing, no deletes", nothingDropped.ok);
  check(
    "main(): cleanup runs before the gate, records deleted-leads.json, aborts on failure, prunes carry-over",
    main.indexOf("removeDroppedInvalidLeads(") > 0 &&
      main.indexOf("removeDroppedInvalidLeads(") < main.indexOf("await waitForVerification(") &&
      /"deleted-leads\.json"/.test(main) &&
      /if \(!invalidCleanup\.ok\) \{\s*fail\(/.test(main) &&
      /writeJson\(carryOverPath, kept\)/.test(main) &&
      !/scopeEmails/.test(SOURCE),
  );

  // --- F1/F3: activation decision (blocked → launcher exits 2) ---
  const d = verificationActivationBlock;
  check(
    "activation decision: pass / no gate → not blocked",
    d({ verifiedLeads: 1 }, false).blocked === null && d(null, false).blocked === null,
  );
  check(
    "activation decision: pending after budget → blocked even with allow_unverified_activation",
    d({ verification_pending: true }, false).blocked === "verification_pending" &&
      d({ verification_pending: true }, true).blocked === "verification_pending",
  );
  check(
    "activation decision: stuck → blocked unless allow_unverified_activation (with warning)",
    d({ verification_pending: true, stuck: true, pending_reason: "r" }, false).blocked ===
      "verification_pending" &&
      d({ verification_pending: true, stuck: true, pending_reason: "r" }, true).blocked === null &&
      d({ verification_pending: true, stuck: true, pending_reason: "r" }, true).warning === "r",
  );
  check(
    "activation decision: unread → blocked unless allow_unverified_activation (with warning)",
    d({ verification_unread: true, stuck_reason: "u" }, false).blocked === "verification_unread" &&
      d({ verification_unread: true, stuck_reason: "u" }, true).blocked === null &&
      d({ verification_unread: true, stuck_reason: "u" }, false).warning === "u",
  );
  check(
    "main(): activation only when not blocked; every block exits 2 after the summary",
    /spec\.campaign\.activate_on_launch === true && !activationBlocked/.test(main) &&
      /spec\.campaign\.allow_unverified_activation === true/.test(main) &&
      /if \(activationBlocked\) \{[\s\S]*?process\.exit\(2\)/.test(main),
  );
  check(
    "main(): expected leads passed to the gate (already imported + batch - not added)",
    /expectedLeads: Math\.max\(\s*0,\s*alreadyImportedCount \+ pendingLeads\.length - notAddedCount/.test(main),
  );
  check(
    "main(): gate failure writes state/invalid-leads.json before failing",
    /path\.join\(stateDir, "invalid-leads\.json"\)/.test(main) &&
      main.indexOf("writeJson(invalidLeadsPath") <
        main.indexOf("verificationResult.failure_reason"),
  );
  check(
    "main(): exit 2 comes after writing the summary",
    main.indexOf("writeJson(summaryPath, summary)") <
      main.indexOf("process.exit(2)"),
  );
  check(
    "main(): a rerun re-checks a gate that did not pass",
    /previousVerification\.status !== "passed"/.test(main) &&
      /verification-state\.json/.test(main),
  );

  if (failed > 0) {
    console.error(`\n${failed} check(s) failed`);
    process.exit(1);
  }
  console.log("\nAll preflight-verification-fallback checks passed");
})().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(1);
});

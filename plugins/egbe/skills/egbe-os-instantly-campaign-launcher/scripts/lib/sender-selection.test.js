const test = require("node:test");
const assert = require("node:assert");
const { selectSenders } = require("./sender-selection");

const acc = (email, extra = {}) => ({
  email,
  status: 1,
  daily_limit: 30,
  first_name: "A",
  ...extra,
});

// A shared workspace: two businesses' mailboxes side by side.
const workspace = [
  acc("emma@getagbis.com", { first_name: "Emma" }),
  acc("emma@tryagbis.com", { first_name: "Emma" }),
  acc("Carter@GetAgbis.com", { first_name: "Emma" }),
  acc("paused@getagbis.com", { status: 2 }),
  acc("sara@getfinateam.com", { first_name: "Sara" }),
  acc("andrew@smartcreateinc.org"),
];

test("no senders named: launch stops instead of picking workspace mailboxes", () => {
  for (const campaign of [
    {},
    { email_list: [] },
    { sender_domains: [] },
    undefined,
  ]) {
    const r = selectSenders(campaign, workspace);
    assert.match(r.error, /email_list or campaign\.sender_domains/);
    assert.strictEqual(r.senders, undefined);
  }
});

test("both named: rejected", () => {
  const r = selectSenders(
    { email_list: ["emma@getagbis.com"], sender_domains: ["getagbis.com"] },
    workspace,
  );
  assert.match(r.error, /only one/);
});

test("email_list: exactly those mailboxes, in order, with names", () => {
  const r = selectSenders(
    { email_list: [" Emma@TryAgbis.com", "carter@getagbis.com"] },
    workspace,
  );
  assert.deepStrictEqual(
    r.senders.map((s) => s.email),
    ["emma@tryagbis.com", "carter@getagbis.com"],
  );
  assert.strictEqual(r.senders[0].first_name, "Emma");
});

test("email_list: address outside the workspace is an error", () => {
  const r = selectSenders(
    { email_list: ["emma@getagbis.com", "typo@getagbis.co"] },
    workspace,
  );
  assert.match(r.error, /Not in the Instantly workspace: typo@getagbis\.co/);
});

test("email_list: paused or zero-limit mailbox is an error, not silently dropped", () => {
  const ws = [...workspace, acc("zero@getagbis.com", { daily_limit: 0 })];
  const r = selectSenders(
    {
      email_list: [
        "emma@getagbis.com",
        "paused@getagbis.com",
        "zero@getagbis.com",
      ],
    },
    ws,
  );
  assert.match(r.error, /paused@getagbis\.com, zero@getagbis\.com/);
});

test("sender_domains: only active mailboxes on those domains, sorted", () => {
  const r = selectSenders(
    { sender_domains: ["@GetAgbis.com", "tryagbis.com"] },
    workspace,
  );
  assert.deepStrictEqual(
    r.senders.map((s) => s.email),
    ["carter@getagbis.com", "emma@getagbis.com", "emma@tryagbis.com"],
  );
});

test("sender_domains: max_sending_accounts caps the list deterministically", () => {
  const campaign = {
    sender_domains: ["getagbis.com", "tryagbis.com"],
    max_sending_accounts: 2,
  };
  const a = selectSenders(campaign, workspace).senders.map((s) => s.email);
  const b = selectSenders(campaign, [...workspace].reverse()).senders.map(
    (s) => s.email,
  );
  assert.deepStrictEqual(a, ["carter@getagbis.com", "emma@getagbis.com"]);
  assert.deepStrictEqual(a, b);
});

test("sender_domains: no active mailbox on the domain is an error", () => {
  const r = selectSenders({ sender_domains: ["unknown.com"] }, workspace);
  assert.match(r.error, /No active mailboxes on unknown\.com/);
});

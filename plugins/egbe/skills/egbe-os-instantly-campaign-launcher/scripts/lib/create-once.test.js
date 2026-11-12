const test = require("node:test");
const assert = require("node:assert");
const http = require("http");
const { InstantlyClient } = require("./instantly-client");
const { leadsNotInCampaign } = require("./create-once");

function server(handler) {
  const seen = [];
  const srv = http.createServer((req, res) => {
    seen.push(`${req.method} ${req.url.split("?")[0]}`);
    const { status, body } = handler(req);
    res.writeHead(status, { "content-type": "application/json" });
    res.end(JSON.stringify(body ?? {}));
  });
  return new Promise((resolve) => srv.listen(0, "127.0.0.1", () => resolve({ srv, seen })));
}
const clientFor = (srv) => new InstantlyClient({ osApiKey: "test", osUrl: `http://127.0.0.1:${srv.address().port}` });

for (const [name, call] of [
  ["createCampaign", (c) => c.createCampaign({ name: "x" })],
  ["addLeadsToCampaign", (c) => c.addLeadsToCampaign({ campaign_id: "c", leads: [{ email: "a@example.test" }] })],
  ["createCustomTag", (c) => c.createCustomTag({ label: "t" })],
]) {
  test(`${name} is sent once on 504`, async () => {
    const { srv, seen } = await server(() => ({ status: 504 }));
    try {
      const res = await call(clientFor(srv));
      assert.strictEqual(res.status, 504);
      assert.strictEqual(seen.filter((s) => s.startsWith("POST")).length, 1);
    } finally {
      srv.close();
    }
  });
}

test("reads are still retried on 503", async () => {
  const { srv, seen } = await server(() => ({ status: 503 }));
  try {
    await clientFor(srv).getCampaign("c");
    assert.strictEqual(seen.length, 5);
  } finally {
    srv.close();
  }
});

test("listLeadEmails pages through the campaign", async () => {
  const page1 = Array.from({ length: 100 }, (_, i) => ({ id: `l${i}`, campaign: "c", email: `P${i}@Example.test` }));
  const { srv } = await server((req) => ({
    status: 200,
    body: { data: { items: req.url.includes("starting_after") ? [{ id: "l100", campaign: "c", email: "last@example.test" }] : page1 } },
  }));
  try {
    const present = await clientFor(srv).listLeadEmails("c");
    assert.strictEqual(present.ok, true);
    assert.strictEqual(present.emails.size, 101);
    assert.ok(present.emails.has("p7@example.test"));
  } finally {
    srv.close();
  }
});

test("an unreadable lead list is reported as unknown", async () => {
  const { srv } = await server(() => ({ status: 404 }));
  try {
    assert.strictEqual((await clientFor(srv).listLeadEmails("c")).ok, false);
  } finally {
    srv.close();
  }
});

test("only leads not yet in the campaign are sent", () => {
  const leads = [{ email: "A@example.test" }, { email: "b@example.test" }];
  const present = { ok: true, emails: new Set(["a@example.test"]) };
  assert.deepStrictEqual(leadsNotInCampaign(leads, present), [{ email: "b@example.test" }]);
  assert.throws(() => leadsNotInCampaign(leads, { ok: false, emails: new Set() }), /import stopped/);
});

test("a server that ignores the cursor does not loop forever", async () => {
  const page = Array.from({ length: 100 }, (_, i) => ({ id: `l${i}`, campaign: "c", email: `p${i}@example.test` }));
  const { srv, seen } = await server(() => ({ status: 200, body: { data: { items: page } } }));
  try {
    const client = clientFor(srv);
    const present = await client.listLeadEmails("c");
    assert.strictEqual(present.ok, false);
    const counted = await client.countLeads("c");
    assert.strictEqual(counted.partial, true);
    assert.strictEqual(counted.total, 100);
    assert.ok(seen.length <= 4, `made ${seen.length} requests`);
  } finally {
    srv.close();
  }
});

test("an ambiguous import is not resent when the next lead read is unavailable", async () => {
  let imported = false;
  const { srv, seen } = await server((req) => {
    if (req.method === "POST") {
      imported = true;
      return { status: 504 };
    }
    return imported ? { status: 404 } : { status: 200, body: { data: { items: [] } } };
  });
  try {
    const client = clientFor(srv);
    const leads = [{ email: "a@example.test" }];
    const first = leadsNotInCampaign(leads, await client.listLeadEmails("c"));
    assert.strictEqual((await client.addLeadsToCampaign({ campaign_id: "c", leads: first })).status, 504);
    await assert.rejects(async () => {
      const retry = leadsNotInCampaign(leads, await client.listLeadEmails("c"));
      await client.addLeadsToCampaign({ campaign_id: "c", leads: retry });
    }, /import stopped/);
    assert.strictEqual(seen.filter((s) => s.startsWith("POST")).length, 1);
  } finally {
    srv.close();
  }
});

for (const [label, body] of [
  ["missing items", { data: {} }],
  ["wrong items type", { data: { items: {} } }],
  ["missing email", { data: { items: [{ id: "l1" }] } }],
  ["full page missing cursor", { data: { items: Array.from({ length: 100 }, () => ({ email: "a@example.test" })) } }],
]) {
  test(`an incomplete lead response (${label}) prevents import`, async () => {
    const { srv, seen } = await server(() => ({ status: 200, body }));
    try {
      const client = clientFor(srv);
      await assert.rejects(async () => {
        const leads = leadsNotInCampaign([{ email: "new@example.test" }], await client.listLeadEmails("c"));
        await client.addLeadsToCampaign({ campaign_id: "c", leads });
      }, /import stopped/);
      assert.strictEqual(seen.filter((s) => s.startsWith("POST")).length, 0);
    } finally {
      srv.close();
    }
  });
}

function countingClient(pages) {
  const client = new InstantlyClient({ osApiKey: "test", osUrl: "http://127.0.0.1" });
  let index = 0;
  client.listLeads = async () => ({ status: 200, body: pages[Math.min(index++, pages.length - 1)] });
  return client;
}

for (const fixture of [
  { name: "malformed first page", pages: [{}] },
  { name: "duplicate identities", pages: [{ items: [
    { id: "one", email: "one@example.test" }, { id: "one", email: "two@example.test" },
  ] }] },
  { name: "duplicate addresses", pages: [{ items: [
    { id: "one", email: "one@example.test" }, { id: "two", email: "ONE@example.test" },
  ] }] },
  { name: "missing identity", pages: [{ items: [{ status: 1 }] }] },
  { name: "foreign membership", pages: [{ items: [{ id: "one", campaign: "other" }] }] },
  { name: "full page without cursor IDs", pages: [{ items: Array.from({ length: 100 }, (_, i) => ({ email: `p${i}@example.test` })) }] },
]) {
  test(`countLeads never reports a complete population for ${fixture.name}`, async () => {
    const result = await countingClient(fixture.pages).countLeads("c");
    assert.ok(!result.ok || result.partial);
  });
}

test("complete pagination does not imply known contact activity", async () => {
  const result = await countingClient([{ items: [
    { id: "unknown", status: 1 },
    { id: "unsent", status: 1, timestamp_last_contact: null },
    { id: "sent", status: 1, timestamp_last_contact: "2026-11-02T12:00:00Z" },
  ] }]).countLeads("c");
  assert.equal(result.ok, true);
  assert.equal(result.partial, false);
  assert.equal(result.total, 3);
  assert.equal(result.contacted, 1);
  assert.equal(result.contact_activity_unknown, 1);
});

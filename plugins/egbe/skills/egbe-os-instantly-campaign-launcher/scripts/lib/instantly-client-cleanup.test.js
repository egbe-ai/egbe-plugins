const test = require("node:test");
const assert = require("node:assert");
const http = require("http");
const { InstantlyClient } = require("./instantly-client");

// Records every request and answers each with `status` and `body`.
function serverAnswering(status, body = "{}") {
  const requests = [];
  const server = http.createServer((req, res) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => {
      requests.push({
        method: req.method,
        url: req.url,
        body: data ? JSON.parse(data) : null,
      });
      res.writeHead(status, { "content-type": "application/json" });
      res.end(body);
    });
  });
  return new Promise((resolve) =>
    server.listen(0, "127.0.0.1", () => resolve({ server, requests })),
  );
}

function clientFor(server) {
  return new InstantlyClient({
    osApiKey: "test",
    osUrl: `http://127.0.0.1:${server.address().port}`,
  });
}

test("deleteCampaign sends DELETE without a body", async () => {
  const { server, requests } = await serverAnswering(
    200,
    JSON.stringify({ data: { deleted: true, campaign_id: "c1" } }),
  );
  try {
    const res = await clientFor(server).deleteCampaign("c1");
    assert.strictEqual(res.status, 200);
    assert.deepStrictEqual(res.body, { deleted: true, campaign_id: "c1" });
    assert.deepStrictEqual(requests, [
      { method: "DELETE", url: "/outreach/instantly/campaigns/c1", body: null },
    ]);
  } finally {
    server.close();
  }
});

test("deleteLead sends DELETE without a body", async () => {
  const { server, requests } = await serverAnswering(200);
  try {
    const res = await clientFor(server).deleteLead("l1");
    assert.strictEqual(res.status, 200);
    assert.deepStrictEqual(requests, [
      { method: "DELETE", url: "/outreach/instantly/leads/l1", body: null },
    ]);
  } finally {
    server.close();
  }
});

test("updateLead sends PATCH with the payload wrapper", async () => {
  const { server, requests } = await serverAnswering(200);
  try {
    const fields = { first_name: "Ann", custom_variables: { hook: "x" } };
    const res = await clientFor(server).updateLead("l1", fields);
    assert.strictEqual(res.status, 200);
    assert.deepStrictEqual(requests, [
      {
        method: "PATCH",
        url: "/outreach/instantly/leads/l1",
        body: { payload: fields },
      },
    ]);
  } finally {
    server.close();
  }
});

// A 5xx can arrive after the delete happened upstream, so the client must
// not repeat it on its own.
for (const method of ["deleteCampaign", "deleteLead"]) {
  for (const status of [500, 502, 503, 504]) {
    test(`${method} sends once on ${status}`, async () => {
      const { server, requests } = await serverAnswering(status);
      try {
        const res = await clientFor(server)[method]("x1");
        assert.strictEqual(res.status, status);
        assert.strictEqual(requests.length, 1);
      } finally {
        server.close();
      }
    });
  }
}

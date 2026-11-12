const test = require("node:test");
const assert = require("node:assert");
const http = require("http");
const { InstantlyClient } = require("./instantly-client");

// A reply is an email: a 5xx can arrive after Instantly sent it, so the client
// must not repeat the POST on its own.
function serverAnswering(status) {
  const posts = [];
  const server = http.createServer((req, res) => {
    if (req.method === "POST") posts.push(req.url);
    res.writeHead(status, { "content-type": "application/json" });
    res.end("{}");
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({ server, posts })));
}

for (const status of [500, 502, 503, 504]) {
  test(`replyToEmail sends once on ${status}`, async () => {
    const { server, posts } = await serverAnswering(status);
    try {
      const client = new InstantlyClient({ osApiKey: "test", osUrl: `http://127.0.0.1:${server.address().port}` });
      const res = await client.replyToEmail({ reply_to_uuid: "m1", eaccount: "a@example.test", subject: "Re:", body: { text: "hi" } });
      assert.strictEqual(res.status, status);
      assert.strictEqual(posts.length, 1);
    } finally {
      server.close();
    }
  });
}

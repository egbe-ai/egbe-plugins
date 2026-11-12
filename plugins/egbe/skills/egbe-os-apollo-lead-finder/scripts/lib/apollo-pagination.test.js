#!/usr/bin/env node
// Unit test: ApolloClient.searchAllPeople must keep paging when the OS
// gateway strips pagination metadata (empty pagination object), stop on a
// short page, honor pagination.total_pages when it IS present, and stop
// via the seen-ids guard when the gateway ignores the page param and
// returns the same page repeatedly.
//
// Pure stub test — no network calls.
// Run: node scripts/lib/apollo-pagination.test.js

const assert = require("node:assert/strict");
const { ApolloClient } = require("./apollo-client");

function people(start, count) {
  return Array.from({ length: count }, (_, i) => ({ id: `p${start + i}` }));
}

/**
 * Build a client whose searchPeople returns pages[page - 1] (or an empty
 * page past the end) and records every request's params in client.calls.
 */
function stubClient(pages) {
  const client = new ApolloClient({
    osUrl: "https://os.invalid",
    osApiKey: "test-key",
  });
  client.calls = [];
  client.searchPeople = async (params) => {
    client.calls.push(params);
    const body = pages[params.page - 1] || { people: [] };
    return { status: 200, headers: {}, body };
  };
  return client;
}

async function check(name, fn) {
  try {
    await fn();
    console.log(`OK   ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

async function main() {
  await check(
    "empty pagination + full pages -> keeps paging until the short page",
    async () => {
      const client = stubClient([
        { people: people(1, 100), pagination: {} },
        { people: people(101, 100), pagination: {} },
        { people: people(201, 40), pagination: {} },
      ]);
      const result = await client.searchAllPeople({}, { maxPages: 10, maxResults: 500 });
      assert.equal(result.people.length, 240);
      assert.equal(client.calls.length, 3);
      assert.deepEqual(client.calls.map((c) => c.page), [1, 2, 3]);
      assert.equal(client.calls[0].per_page, 100);
      assert.equal(result.people[0].id, "p1");
      assert.equal(result.people[239].id, "p240");
    },
  );

  await check("short first page -> a single request", async () => {
    const client = stubClient([{ people: people(1, 5), pagination: {} }]);
    const result = await client.searchAllPeople({}, { maxPages: 10, maxResults: 500 });
    assert.equal(result.people.length, 5);
    assert.equal(client.calls.length, 1);
  });

  await check("pagination.total_pages honored when present", async () => {
    const client = stubClient([
      { people: people(1, 100), pagination: { total_pages: 2 } },
      { people: people(101, 100), pagination: { total_pages: 2 } },
      // Page 3 must never be requested even though pages 1-2 were full.
      { people: people(201, 100), pagination: { total_pages: 2 } },
    ]);
    const result = await client.searchAllPeople({}, { maxPages: 10, maxResults: 500 });
    assert.equal(result.people.length, 200);
    assert.equal(client.calls.length, 2);
  });

  await check("total_pages: 1 with a full page -> a single request", async () => {
    const client = stubClient([
      { people: people(1, 100), pagination: { total_pages: 1 } },
      { people: people(101, 100), pagination: { total_pages: 1 } },
    ]);
    const result = await client.searchAllPeople({}, { maxPages: 10, maxResults: 500 });
    assert.equal(result.people.length, 100);
    assert.equal(client.calls.length, 1);
  });

  await check(
    "repeated page content -> stops via the seen-ids guard",
    async () => {
      const samePage = { people: people(1, 100), pagination: {} };
      const client = stubClient([samePage, samePage, samePage, samePage]);
      const result = await client.searchAllPeople({}, { maxPages: 10, maxResults: 500 });
      assert.equal(result.people.length, 100);
      assert.equal(result.complete, false);
      assert.equal(result.stop_reason, "repeated_page");
      // Page 2 contributes zero new ids -> break; pages 3+ never requested.
      assert.equal(client.calls.length, 2);
      const ids = new Set(result.people.map((p) => p.id));
      assert.equal(ids.size, 100);
    },
  );

  await check("maxResults still truncates and stops paging", async () => {
    const client = stubClient([
      { people: people(1, 100), pagination: {} },
      { people: people(101, 100), pagination: {} },
      { people: people(201, 100), pagination: {} },
    ]);
    const result = await client.searchAllPeople({}, { maxPages: 10, maxResults: 150 });
    assert.equal(result.people.length, 150);
    assert.equal(result.complete, true);
    assert.equal(result.stop_reason, "max_results");
    assert.equal(client.calls.length, 2);
  });

  console.log("\nAll pagination checks passed");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

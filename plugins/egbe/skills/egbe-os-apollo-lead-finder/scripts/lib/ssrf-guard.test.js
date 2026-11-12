"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const dns = require("node:dns");
const http = require("node:http");
const { EventEmitter } = require("node:events");
const { isGlobalIp, resolvePublicAddress, fetchHtml } = require("../places-leads");

test("rejects loopback, private, reserved, internal and malformed IPs", () => {
  for (const ip of ["127.0.0.1", "127.8.8.8", "0.0.0.0", "10.0.0.5",
    "172.16.0.1", "172.31.255.255", "192.168.1.1", "169.254.169.254",
    "100.64.0.1", "192.0.2.10", "198.51.100.7", "203.0.113.9",
    "224.0.0.1", "255.255.255.255", "::1", "::", "fd00::1", "fc00::abcd",
    "fe80::1", "ff02::1", "2001:db8::1", "::ffff:10.0.0.1",
    "::ffff:169.254.169.254", "not-an-ip", ""]) assert.equal(isGlobalIp(ip), false, ip);
  for (const ip of ["8.8.8.8", "142.250.64.78", "185.199.108.153",
    "2607:f8b0:4004:c07::71", "2a00:1450:4001:830::200e", "::ffff:8.8.8.8"])
    assert.equal(isGlobalIp(ip), true, ip);
});

test("mixed DNS results and internal hostnames are rejected before requests", async (t) => {
  t.mock.method(dns.promises, "lookup", async () => [{ address: "8.8.8.8" }, { address: "10.0.0.1" }]);
  assert.equal(await resolvePublicAddress("public.test"), null);
  assert.equal(await resolvePublicAddress("service.gcp.egbe.dev"), null);
  assert.equal(await resolvePublicAddress("localhost"), null);
  assert.equal(await fetchHtml("http://user:password@public.test/"), null);
});

test("fetch pins the vetted address, preserves Host and rechecks every redirect", async (t) => {
  const lookedUp = [];
  t.mock.method(dns.promises, "lookup", async (host) => { lookedUp.push(host); return [{ address: "8.8.8.8" }]; });
  const connections = [];
  t.mock.method(http, "get", (options, callback) => {
    connections.push(options);
    const req = new EventEmitter();
    req.destroy = () => {};
    process.nextTick(() => {
      const response = new EventEmitter();
      response.statusCode = 302;
      response.headers = { location: "http://169.254.169.254/latest/meta-data/" };
      response.resume = () => {};
      callback(response);
    });
    return req;
  });
  assert.equal(await fetchHtml("http://public.test/start"), null);
  assert.deepEqual(lookedUp, ["public.test"]);
  assert.equal(connections.length, 1, "private redirect must not connect");
  assert.equal(connections[0].host, "8.8.8.8");
  assert.equal(connections[0].headers.Host, "public.test");
  assert.equal(connections[0].headers.Authorization, undefined);
});

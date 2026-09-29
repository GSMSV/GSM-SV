import assert from "node:assert/strict";
import { test } from "node:test";
import express from "express";
import { prisma } from "../src/db/prisma";

const ownershipChecks: Array<[string, number, string]> = [];
const ownerPath = require.resolve("../src/services/functionService.ts");
require.cache[ownerPath] = { id: ownerPath, filename: ownerPath, loaded: true, exports: { assertOwnership: async (id: string, userId: number, role: string) => {
  ownershipChecks.push([id, userId, role]);
  if (id === "other" && role !== "admin") throw Object.assign(new Error("Not found"), { statusCode: 404 });
} } } as NodeModule;
const mutations: Array<{ action: string; args: unknown[] }> = [];
const triggerPath = require.resolve("../src/services/triggerService.ts");
require.cache[triggerPath] = { id: triggerPath, filename: triggerPath, loaded: true, exports: {
  createTrigger: async () => ({ id: "t", secretToken: "one-time" }),
  updateTrigger: async (...args: unknown[]) => { mutations.push({ action: "update", args }); return { id: "t", ...args[2] as object }; },
  deleteTrigger: async (...args: unknown[]) => { mutations.push({ action: "delete", args }); },
} } as NodeModule;
const router = require("../src/routes/triggers").default;
const app = express();
app.use(express.json());
app.use("/functions/:id/triggers", router);

async function send(method: string, body?: unknown, functionId = "f1", role = "user", triggerId = "t") {
  const server = app.listen(0);
  try {
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("No listener address");
    const response = await fetch(`http://127.0.0.1:${address.port}/functions/${functionId}/triggers${["PUT", "DELETE"].includes(method) ? `/${triggerId}` : ""}`, {
      method, headers: { "content-type": "application/json", "x-user-id": "1", "x-user-role": role },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return { status: response.status, body: response.status === 204 ? null : await response.json() };
  } finally { server.close(); }
}

test("list never exposes persisted digest", async () => {
  const original = prisma.trigger.findMany;
  (prisma.trigger as any).findMany = async () => [{ id: "t", secretTokenHash: "digest", enabled: true }];
  try { assert.deepEqual((await send("GET")).body, [{ id: "t", enabled: true }]); }
  finally { (prisma.trigger as any).findMany = original; }
});

test("update does not accept secret hash or token from caller", async () => {
  assert.deepEqual((await send("PUT", { enabled: false, secretTokenHash: null, secretToken: "injected" })).body, { id: "t", enabled: false });
});

test("HTTP create response exposes one-time token", async () => {
  assert.deepEqual(await send("POST", { type: "http", httpMethod: "GET" }), { status: 201, body: { id: "t", secretToken: "one-time" } });
});

test("PUT rejects invalid HTTP method without mutating trigger", async () => {
  mutations.length = 0;
  assert.equal((await send("PUT", { httpMethod: "TRACE" })).status, 400);
  assert.deepEqual(mutations, []);
});

test("PUT and DELETE scope trigger mutations to the owned parent function", async () => {
  mutations.length = 0;
  assert.equal((await send("PUT", { enabled: false }, "f1", "user", "foreign-trigger")).status, 200);
  assert.equal((await send("DELETE", undefined, "f1", "user", "foreign-trigger")).status, 204);
  assert.deepEqual(mutations, [
    { action: "update", args: ["f1", "foreign-trigger", { enabled: false }] },
    { action: "delete", args: ["f1", "foreign-trigger"] },
  ]);
});

test("non-owner cannot mutate a trigger even with its ID", async () => {
  mutations.length = 0;
  assert.equal((await send("PUT", { enabled: false }, "other")).status, 404);
  assert.equal((await send("DELETE", undefined, "other")).status, 404);
  assert.deepEqual(mutations, []);
});

test("admin can mutate a trigger only under its requested parent function", async () => {
  mutations.length = 0;
  assert.equal((await send("PUT", { enabled: false }, "other", "admin")).status, 200);
  assert.equal((await send("DELETE", undefined, "other", "admin")).status, 204);
  assert.deepEqual(mutations.map(m => m.args.slice(0, 2)), [["other", "t"], ["other", "t"]]);
  assert.ok(ownershipChecks.some(([id, userId, role]) => id === "other" && userId === 1 && role === "admin"));
});

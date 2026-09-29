import assert from "node:assert/strict";
import { test } from "node:test";
import express from "express";
import { prisma } from "../src/db/prisma";

const ownerPath = require.resolve("../src/services/functionService.ts");
require.cache[ownerPath] = { id: ownerPath, filename: ownerPath, loaded: true, exports: { assertOwnership: async () => {} } } as NodeModule;
const triggerPath = require.resolve("../src/services/triggerService.ts");
require.cache[triggerPath] = { id: triggerPath, filename: triggerPath, loaded: true, exports: {
  createTrigger: async () => ({ id: "t", secretToken: "one-time" }),
  updateTrigger: async (_id: string, data: unknown) => ({ id: "t", ...data as object }),
  deleteTrigger: async () => {},
} } as NodeModule;
const router = require("../src/routes/triggers").default;
const app = express();
app.use(express.json());
app.use("/functions/:id/triggers", router);

async function send(method: string, body?: unknown) {
  const server = app.listen(0);
  try {
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("No listener address");
    const response = await fetch(`http://127.0.0.1:${address.port}/functions/f1/triggers${method === "PUT" ? "/t" : ""}`, {
      method, headers: { "content-type": "application/json", "x-user-id": "1", "x-user-role": "user" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return { status: response.status, body: await response.json() };
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

import assert from "node:assert/strict";
import { test } from "node:test";
import express from "express";
import { prisma } from "../src/db/prisma";
import { createHttpTriggerToken } from "../src/services/triggerAuth";

let receivedMeta: any;
const executionPath = require.resolve("../src/services/executionService.ts");
require.cache[executionPath] = { id: executionPath, filename: executionPath, loaded: true, exports: {
  runFunction: async (_func: unknown, _body: unknown, _type: unknown, meta: unknown) => {
    receivedMeta = meta;
    return { statusCode: 200, headers: {}, body: "ok" };
  },
} } as NodeModule;
const gateway = require("../src/routes/gateway").default;

const credential = createHttpTriggerToken();
const func = { status: "active", triggers: [{ type: "http", enabled: true, httpMethod: "POST", secretTokenHash: credential.secretTokenHash }] };

async function request(method: string, path: string, token?: string) {
  const original = prisma.function.findUnique;
  (prisma.function as any).findUnique = async () => func;
  const app = express();
  app.use(express.json());
  app.use(gateway);
  const server = app.listen(0);
  try {
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("No listener address");
    return await fetch(`http://127.0.0.1:${address.port}${path}`, { method, headers: token ? { "X-Secret-Token": token } : undefined });
  } finally {
    server.close();
    (prisma.function as any).findUnique = original;
  }
}

test("gateway rejects absent and incorrect token before execution", async () => {
  receivedMeta = undefined;
  assert.equal((await request("POST", "/42/demo")).status, 401);
  assert.equal((await request("POST", "/42/demo", "incorrect")).status, 401);
  assert.equal(receivedMeta, undefined);
});

test("gateway executes with valid token but never passes credential to handler", async () => {
  assert.equal((await request("POST", "/42/demo", credential.token)).status, 200);
  assert.equal(receivedMeta.headers["x-secret-token"], undefined);
});

test("gateway rejects query token and disallowed method", async () => {
  assert.equal((await request("POST", `/42/demo?secretToken=${credential.token}`)).status, 401);
  assert.equal((await request("PUT", "/42/demo", credential.token)).status, 405);
});

test("public trigger cannot bypass protected trigger at the same method", async () => {
  func.triggers = [
    { type: "http", enabled: true, httpMethod: "POST", secretTokenHash: null },
    { type: "http", enabled: true, httpMethod: "POST", secretTokenHash: credential.secretTokenHash },
  ] as any;
  try {
    assert.equal((await request("POST", "/42/demo")).status, 401);
    assert.equal((await request("POST", "/42/demo", "wrong")).status, 401);
    assert.equal((await request("POST", "/42/demo", credential.token)).status, 200);
  } finally { func.triggers = [{ type: "http", enabled: true, httpMethod: "POST", secretTokenHash: credential.secretTokenHash }]; }
});

test("legacy gateway trigger stays public", async () => {
  func.triggers = [{ type: "http", enabled: true, httpMethod: "POST", secretTokenHash: null }] as any;
  try { assert.equal((await request("POST", "/42/demo")).status, 200); }
  finally { func.triggers = [{ type: "http", enabled: true, httpMethod: "POST", secretTokenHash: credential.secretTokenHash }]; }
});

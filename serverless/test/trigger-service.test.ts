import assert from "node:assert/strict";
import { test } from "node:test";
import { prisma } from "../src/db/prisma";
import { hashTriggerToken } from "../src/services/triggerAuth";

// Isolate the scheduler's native isolated-vm dependency; this suite tests persistence.
const schedulerPath = require.resolve("../src/services/schedulerService.ts");
require.cache[schedulerPath] = { id: schedulerPath, filename: schedulerPath, loaded: true, exports: { scheduler: { addTrigger: async () => {}, reloadTrigger: async () => {}, removeTrigger: () => {} } } } as NodeModule;
const { createTrigger, updateTrigger, deleteTrigger } = require("../src/services/triggerService") as typeof import("../src/services/triggerService");

test("HTTP creation stores only a digest and returns plaintext once", async () => {
  const original = prisma.trigger.create;
  let saved: any;
  (prisma.trigger as any).create = async ({ data }: any) => {
    saved = data;
    return { id: "t1", ...data };
  };
  try {
    const result = await createTrigger("f1", { type: "http", httpMethod: "POST" });
    assert.match(result.secretToken!, /^[a-f0-9]{64}$/);
    assert.equal(saved.secretTokenHash, hashTriggerToken(result.secretToken!));
    assert.equal(saved.secretToken, undefined);
    assert.equal("secretTokenHash" in result, false);
  } finally { (prisma.trigger as any).create = original; }
});

test("cron creation does not issue a token", async () => {
  const original = prisma.trigger.create;
  let saved: any;
  (prisma.trigger as any).create = async ({ data }: any) => {
    saved = data;
    return { id: "t2", ...data, enabled: false };
  };
  try {
    const result = await createTrigger("f1", { type: "cron", cronExpr: "0 * * * *", enabled: false });
    assert.equal(saved.secretTokenHash, undefined);
    assert.equal("secretToken" in result, false);
  } finally { (prisma.trigger as any).create = original; }
});

test("updates are atomically scoped to the requested function, including cron", async () => {
  const original = prisma.trigger.update;
  let where: unknown;
  (prisma.trigger as any).update = async (args: any) => {
    where = args.where;
    return { id: "t", functionId: "f1", type: "cron", enabled: false, secretTokenHash: null };
  };
  try {
    await updateTrigger("f1", "t", { enabled: false });
    assert.deepEqual(where, { id: "t", functionId: "f1" });
  } finally { (prisma.trigger as any).update = original; }
});

test("deletes are atomically scoped to the requested function", async () => {
  const original = prisma.trigger.delete;
  let where: unknown;
  (prisma.trigger as any).delete = async (args: any) => { where = args.where; return { id: "t" }; };
  try {
    await deleteTrigger("f1", "t");
    assert.deepEqual(where, { id: "t", functionId: "f1" });
  } finally { (prisma.trigger as any).delete = original; }
});

test("missing or cross-function trigger yields 404 on PUT and DELETE", async () => {
  const originalUpdate = prisma.trigger.update;
  const originalDelete = prisma.trigger.delete;
  const missing = () => { throw Object.assign(new Error("Record not found"), { code: "P2025" }); };
  (prisma.trigger as any).update = missing;
  (prisma.trigger as any).delete = missing;
  try {
    for (const run of [() => updateTrigger("f1", "foreign", { enabled: false }), () => deleteTrigger("f1", "foreign")]) {
      await assert.rejects(run, (err: any) => err.statusCode === 404);
    }
  } finally {
    (prisma.trigger as any).update = originalUpdate;
    (prisma.trigger as any).delete = originalDelete;
  }
});

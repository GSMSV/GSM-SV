import assert from "node:assert/strict";
import { test } from "node:test";
import { prisma } from "../src/db/prisma";
import { setupDb } from "../src/setup-db";

test("startup upgrades setup-db legacy trigger table before opening service", async () => {
  const original = prisma.$executeRaw;
  const sql: string[] = [];
  (prisma as any).$executeRaw = async (parts: TemplateStringsArray) => { sql.push(parts.join("")); return 0; };
  try {
    await setupDb();
    assert.ok(sql.some(s => s.includes('CREATE TABLE IF NOT EXISTS "sv_triggers"') && s.includes('"secretTokenHash" TEXT')));
    const createIndex = sql.findIndex(s => s.includes('CREATE TABLE IF NOT EXISTS "sv_triggers"'));
    const alterIndex = sql.findIndex(s => s.includes('ALTER TABLE "sv_triggers" ADD COLUMN IF NOT EXISTS "secretTokenHash" TEXT'));
    assert.ok(createIndex >= 0 && alterIndex > createIndex);
    assert.equal(sql.filter(s => s.includes('ALTER TABLE "sv_triggers" ADD COLUMN')).length, 1);
  } finally { (prisma as any).$executeRaw = original; }
});

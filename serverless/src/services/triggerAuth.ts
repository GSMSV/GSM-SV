import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

export function hashTriggerToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export function createHttpTriggerToken(): { token: string; secretTokenHash: string } {
  const token = randomBytes(32).toString("hex");
  return { token, secretTokenHash: hashTriggerToken(token) };
}

export function redactTrigger<T extends { secretTokenHash?: string | null }>(trigger: T): Omit<T, "secretTokenHash"> {
  const { secretTokenHash: _digest, ...safe } = trigger;
  return safe;
}

type HttpTrigger = { httpMethod: string | null; secretTokenHash: string | null };

// An exact method beats ANY. Within that method, a protected trigger takes
// precedence over a legacy public trigger so a public row cannot bypass it.
export function authorizeHttpTrigger(
  triggers: HttpTrigger[], method: string, token: string | undefined
): "authorized" | "unauthorized" | "method-not-allowed" {
  const exact = triggers.filter(t => t.httpMethod === method);
  const candidates = exact.length ? exact : triggers.filter(t => t.httpMethod === "ANY");
  if (!candidates.length) return "method-not-allowed";

  const protectedTriggers = candidates.filter(t => t.secretTokenHash !== null);
  if (!protectedTriggers.length) return "authorized";
  if (!token || token.length > 256) return "unauthorized";
  const actual = Buffer.from(hashTriggerToken(token), "hex");
  // Corrupt stored digests cannot authorize a request or throw on comparison.
  const matches = protectedTriggers.map(t => {
    const expected = Buffer.from(t.secretTokenHash!, "hex");
    return expected.length === actual.length && timingSafeEqual(actual, expected);
  });
  return matches.some(Boolean) ? "authorized" : "unauthorized";
}

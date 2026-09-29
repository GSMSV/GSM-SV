import assert from "node:assert/strict";
import { test } from "node:test";
import { createHttpTriggerToken, hashTriggerToken, authorizeHttpTrigger, redactTrigger } from "../src/services/triggerAuth";

const legacy = { httpMethod: "GET", secretTokenHash: null };

test("new token is random and only its digest is retained", () => {
  const first = createHttpTriggerToken();
  const second = createHttpTriggerToken();
  assert.match(first.token, /^[a-f0-9]{64}$/);
  assert.notEqual(first.token, second.token);
  assert.equal(first.secretTokenHash, hashTriggerToken(first.token));
  assert.notEqual(first.secretTokenHash, first.token);
});

test("legacy null-hash triggers remain public", () => {
  assert.equal(authorizeHttpTrigger([legacy], "GET", undefined), "authorized");
});

test("secured trigger requires matching header token", () => {
  const { token, secretTokenHash } = createHttpTriggerToken();
  const triggers = [{ httpMethod: "POST", secretTokenHash }];
  assert.equal(authorizeHttpTrigger(triggers, "POST", undefined), "unauthorized");
  assert.equal(authorizeHttpTrigger(triggers, "POST", "wrong"), "unauthorized");
  assert.equal(authorizeHttpTrigger(triggers, "POST", token), "authorized");
});

test("unrelated public trigger cannot bypass protected method", () => {
  const { token, secretTokenHash } = createHttpTriggerToken();
  const triggers = [legacy, { httpMethod: "POST", secretTokenHash }];
  assert.equal(authorizeHttpTrigger(triggers, "POST", undefined), "unauthorized");
  assert.equal(authorizeHttpTrigger(triggers, "PUT", token), "method-not-allowed");
});

test("protected match wins over public match at same method specificity", () => {
  const { secretTokenHash } = createHttpTriggerToken();
  assert.equal(authorizeHttpTrigger([legacy, { httpMethod: "GET", secretTokenHash }], "GET", undefined), "unauthorized");
});

test("exact-method public trigger wins over protected ANY fallback", () => {
  const { secretTokenHash } = createHttpTriggerToken();
  assert.equal(authorizeHttpTrigger([{ httpMethod: "ANY", secretTokenHash }, legacy], "GET", undefined), "authorized");
  assert.equal(authorizeHttpTrigger([{ httpMethod: "ANY", secretTokenHash }, legacy], "POST", undefined), "unauthorized");
});

test("one of multiple protected triggers can authorize without bypass", () => {
  const { token, secretTokenHash } = createHttpTriggerToken();
  const other = createHttpTriggerToken();
  assert.equal(authorizeHttpTrigger([{ httpMethod: "ANY", secretTokenHash: other.secretTokenHash }, { httpMethod: "ANY", secretTokenHash }], "POST", token), "authorized");
});

test("legacy public ANY remains callable on other methods beside protected POST", () => {
  const { secretTokenHash } = createHttpTriggerToken();
  const triggers = [{ httpMethod: "ANY", secretTokenHash: null }, { httpMethod: "POST", secretTokenHash }];
  assert.equal(authorizeHttpTrigger(triggers, "POST", undefined), "unauthorized");
  assert.equal(authorizeHttpTrigger(triggers, "GET", undefined), "authorized");
  assert.equal(authorizeHttpTrigger(triggers, "PUT", undefined), "authorized");
});

test("trigger JSON never contains a persisted digest", () => {
  assert.deepEqual(redactTrigger({ id: "t1", enabled: true, secretTokenHash: "digest" }), { id: "t1", enabled: true });
});

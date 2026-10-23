import { prisma } from "../db/prisma";
import { scheduler } from "./schedulerService";
import { createHttpTriggerToken, redactTrigger } from "./triggerAuth";

export async function createTrigger(functionId: string, data: {
  type: string;
  httpMethod?: string;
  cronExpr?: string;
  enabled?: boolean;
}) {
  const credential = data.type === "http" ? createHttpTriggerToken() : undefined;
  const trigger = await prisma.trigger.create({ data: { functionId, ...data, ...(credential && { secretTokenHash: credential.secretTokenHash }) } });
  if (trigger.type === "cron" && trigger.enabled) {
    await scheduler.addTrigger(trigger.id);
  }
  return { ...redactTrigger(trigger), ...(credential && { secretToken: credential.token }) };
}

function rethrowMissingTrigger(err: unknown): never {
  if (typeof err === "object" && err !== null && "code" in err && err.code === "P2025") {
    throw Object.assign(new Error("Not found"), { statusCode: 404 });
  }
  throw err;
}

export async function updateTrigger(functionId: string, id: string, data: Partial<{
  httpMethod: string;
  cronExpr: string;
  enabled: boolean;
}>) {
  let trigger;
  try {
    trigger = await prisma.trigger.update({ where: { id, functionId }, data });
  } catch (err) {
    rethrowMissingTrigger(err);
  }
  if (trigger.type === "cron") {
    await scheduler.reloadTrigger(id);
  }
  return redactTrigger(trigger);
}

export async function deleteTrigger(functionId: string, id: string) {
  try {
    await prisma.trigger.delete({ where: { id, functionId } });
  } catch (err) {
    rethrowMissingTrigger(err);
  }
  scheduler.removeTrigger(id);
}

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

export async function updateTrigger(id: string, data: Partial<{
  httpMethod: string;
  cronExpr: string;
  enabled: boolean;
}>) {
  const trigger = await prisma.trigger.update({ where: { id }, data });
  if (trigger.type === "cron") {
    await scheduler.reloadTrigger(id);
  }
  return redactTrigger(trigger);
}

export async function deleteTrigger(id: string) {
  scheduler.removeTrigger(id);
  await prisma.trigger.delete({ where: { id } });
}

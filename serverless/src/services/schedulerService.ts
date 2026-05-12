import cron from "node-cron";
import { prisma } from "../db/prisma";
import { runFunction } from "./executionService";
import { Trigger, Function as Fn } from "@prisma/client";

class SchedulerService {
  private jobs = new Map<string, cron.ScheduledTask>();

  async loadFromDB(): Promise<void> {
    const triggers = await prisma.trigger.findMany({
      where: { type: "cron", enabled: true },
      include: { function: true },
    });

    for (const trigger of triggers) {
      if (!trigger.cronExpr || !cron.validate(trigger.cronExpr)) {
        console.warn(`[scheduler] invalid cron for trigger ${trigger.id}: ${trigger.cronExpr}`);
        continue;
      }
      this.scheduleJob(trigger, trigger.function);
    }
    console.log(`[scheduler] loaded ${triggers.length} cron jobs`);
  }

  scheduleJob(trigger: Trigger, func: Fn): void {
    if (!trigger.cronExpr) return;
    const task = cron.schedule(
      trigger.cronExpr,
      async () => {
        console.log(`[scheduler] firing ${trigger.id} for ${func.name}`);
        try {
          await runFunction(func, null, "cron");
        } catch (err) {
          console.error(`[scheduler] execution error for ${func.name}:`, err);
        }
      },
      { timezone: "Asia/Seoul" }
    );
    this.jobs.set(trigger.id, task);
  }

  async addTrigger(triggerId: string): Promise<void> {
    const trigger = await prisma.trigger.findUnique({
      where: { id: triggerId },
      include: { function: true },
    });
    if (!trigger || !trigger.enabled || trigger.type !== "cron") return;
    this.scheduleJob(trigger, trigger.function);
  }

  removeTrigger(triggerId: string): void {
    const task = this.jobs.get(triggerId);
    if (task) {
      task.stop();
      this.jobs.delete(triggerId);
    }
  }

  async reloadTrigger(triggerId: string): Promise<void> {
    this.removeTrigger(triggerId);
    await this.addTrigger(triggerId);
  }
}

export const scheduler = new SchedulerService();

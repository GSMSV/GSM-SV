import app from "./app";
import { prisma } from "./db/prisma";
import { scheduler } from "./services/schedulerService";
import { config } from "./config";
import { setupDb } from "./setup-db";

async function bootstrap() {
  await prisma.$connect();
  console.log("[db] connected");
  await setupDb();
  await scheduler.loadFromDB();
  app.listen(config.port, () => {
    console.log(`[server] serverless service running on :${config.port}`);
  });
}

bootstrap().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

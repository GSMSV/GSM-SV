import express from "express";
import functionsRouter from "./routes/functions";
import executeRouter from "./routes/execute";
import logsRouter from "./routes/logs";
import triggersRouter from "./routes/triggers";
import gatewayRouter from "./routes/gateway";
import { errorHandler } from "./middleware/errorHandler";

const app = express();
app.use(express.json({ limit: "1mb" }));

app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.use("/functions/:id/execute", executeRouter);
app.use("/functions/:id/logs", logsRouter);
app.use("/functions/:id/triggers", triggersRouter);
app.use("/functions", functionsRouter);
app.use("/", gatewayRouter);

app.use(errorHandler);

export default app;

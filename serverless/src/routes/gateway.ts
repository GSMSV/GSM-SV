import { Router } from "express";
import { prisma } from "../db/prisma";
import { runFunction } from "../services/executionService";

const router = Router();

router.all(/^\/(\d+)\/([^/]+)$/, async (req, res, next) => {
  try {
    const [, userIdStr, funcName] = req.path.match(/^\/(\d+)\/([^/]+)$/) || [];
    const ownerId = parseInt(userIdStr);

    const func = await prisma.function.findUnique({
      where: { ownerId_name: { ownerId, name: funcName } },
      include: { triggers: { where: { type: "http", enabled: true } } },
    });

    if (!func || func.status !== "active") return res.status(404).json({ error: "Function not found" });
    if (func.triggers.length === 0) return res.status(404).json({ error: "No HTTP trigger enabled" });

    const trigger = func.triggers[0];
    if (trigger.httpMethod !== "ANY" && req.method !== trigger.httpMethod) {
      return res.status(405).json({ error: "Method Not Allowed" });
    }

    const result = await runFunction(func, req.body || null, "http", {
      method: req.method,
      headers: req.headers as Record<string, string>,
      query: req.query as Record<string, string>,
    });

    res.status(result.statusCode).set(result.headers).send(result.body);
  } catch (err) { next(err); }
});

export default router;

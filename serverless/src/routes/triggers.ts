import { Router, Request } from "express";
import { requireAuth } from "../middleware/auth";
import { assertOwnership } from "../services/functionService";
import { prisma } from "../db/prisma";
import { createTrigger, updateTrigger, deleteTrigger } from "../services/triggerService";

const router = Router({ mergeParams: true });
router.use(requireAuth);

router.get("/", async (req: Request<{ id: string }>, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    const triggers = await prisma.trigger.findMany({ where: { functionId: req.params.id } });
    res.json(triggers);
  } catch (err: any) {
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

router.post("/", async (req: Request<{ id: string }>, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    const { type, httpMethod, cronExpr, enabled } = req.body;
    if (!type || !["http", "cron"].includes(type)) return res.status(400).json({ error: "type은 'http' 또는 'cron'이어야 합니다." });
    if (type === "cron" && !cronExpr) return res.status(400).json({ error: "cron 트리거에는 cronExpr이 필요합니다." });
    const trigger = await createTrigger(req.params.id, { type, httpMethod, cronExpr, enabled });
    res.status(201).json(trigger);
  } catch (err: any) {
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

router.put("/:tid", async (req: Request<{ id: string; tid: string }>, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    const trigger = await updateTrigger(req.params.tid, req.body);
    res.json(trigger);
  } catch (err: any) {
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

router.delete("/:tid", async (req: Request<{ id: string; tid: string }>, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    await deleteTrigger(req.params.tid);
    res.status(204).send();
  } catch (err: any) {
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

export default router;

import { Router, Request } from "express";
import { requireAuth } from "../middleware/auth";
import { assertOwnership } from "../services/functionService";
import { prisma } from "../db/prisma";

const router = Router({ mergeParams: true });
router.use(requireAuth);

router.get("/", async (req: Request<{ id: string }>, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    const limit = parseInt(req.query.limit as string) || 50;
    const offset = parseInt(req.query.offset as string) || 0;
    const logs = await prisma.executionLog.findMany({
      where: { functionId: req.params.id },
      orderBy: { createdAt: "desc" },
      take: limit,
      skip: offset,
    });
    res.json(logs.map(l => ({ ...l, logs: JSON.parse(l.logs) })));
  } catch (err: any) {
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

router.delete("/", async (req: Request<{ id: string }>, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    await prisma.executionLog.deleteMany({ where: { functionId: req.params.id } });
    res.status(204).send();
  } catch (err: any) {
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

export default router;

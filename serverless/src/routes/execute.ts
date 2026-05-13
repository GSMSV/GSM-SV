import { Router, Request } from "express";
import { requireAuth } from "../middleware/auth";
import { assertOwnership } from "../services/functionService";
import { runFunction } from "../services/executionService";
import { prisma } from "../db/prisma";

const router = Router({ mergeParams: true });
router.use(requireAuth);

router.post("/", async (req: Request<{ id: string }>, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    const func = await prisma.function.findUnique({ where: { id: req.params.id } });
    if (!func) return res.status(404).json({ error: "Not found" });
    if (func.status !== "active") return res.status(400).json({ error: "비활성화된 함수입니다." });
    const result = await runFunction(func, req.body || {}, "manual");
    res.json(result);
  } catch (err: any) {
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

export default router;

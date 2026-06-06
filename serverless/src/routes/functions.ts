import { Router } from "express";
import { prisma } from "../db/prisma";
import { requireAuth } from "../middleware/auth";
import { checkFunctionLimit, assertOwnership } from "../services/functionService";
import { compileTypeScript, compileJavaScript } from "../engine/runtime";
import { config } from "../config";

const router = Router();
router.use(requireAuth);

router.post("/", async (req, res, next) => {
  try {
    const { name, description, code, runtime = "javascript", timeout = 30000, memoryLimit = 128, envVars = {} } = req.body;
    if (!name || !code) return res.status(400).json({ error: "name, code는 필수입니다." });
    if (timeout > 60000) return res.status(400).json({ error: "timeout은 최대 60000ms입니다." });
    if (memoryLimit > 256) return res.status(400).json({ error: "memoryLimit은 최대 256MB입니다." });

    await checkFunctionLimit(req.user!.userId);

    let compiledCode: string | undefined;
    if (runtime === "typescript") {
      try {
        compiledCode = await compileTypeScript(code);
      } catch (e: any) {
        return res.status(400).json({ error: `TypeScript 컴파일 오류: ${e.message}` });
      }
    } else {
      // JS도 esbuild로 CJS 변환해서 저장 — 실행 시 재컴파일 없이 사용 + 문법 오류 조기 발견
      try {
        compiledCode = await compileJavaScript(code);
      } catch (e: any) {
        return res.status(400).json({ error: `JavaScript 컴파일 오류: ${e.message}` });
      }
    }

    const func = await prisma.function.create({
      data: { name, description, code, compiledCode, runtime, timeout, memoryLimit, envVars: JSON.stringify(envVars), ownerId: req.user!.userId },
    });
    res.status(201).json({ ...func, envVars: JSON.parse(func.envVars) });
  } catch (err: any) {
    if (err.code === "P2002") return res.status(409).json({ error: "같은 이름의 함수가 이미 존재합니다." });
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

router.get("/", async (req, res, next) => {
  try {
    const where = { ownerId: req.user!.userId };
    const functions = await prisma.function.findMany({ where, orderBy: { createdAt: "desc" } });
    res.json(functions.map(f => ({ ...f, envVars: JSON.parse(f.envVars) })));
  } catch (err) { next(err); }
});

router.get("/quota", async (req, res, next) => {
  try {
    const current = await prisma.function.count({ where: { ownerId: req.user!.userId } });
    res.json({ current, max: config.maxFunctionsPerUser });
  } catch (err) { next(err); }
});

router.get("/:id", async (req, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    const func = await prisma.function.findUnique({ where: { id: req.params.id } });
    if (!func) return res.status(404).json({ error: "Not found" });
    res.json({ ...func, envVars: JSON.parse(func.envVars) });
  } catch (err: any) {
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

router.put("/:id", async (req, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    const { name, description, code, runtime, timeout, memoryLimit, envVars, status } = req.body;
    if (timeout && timeout > 60000) return res.status(400).json({ error: "timeout은 최대 60000ms입니다." });
    if (memoryLimit && memoryLimit > 256) return res.status(400).json({ error: "memoryLimit은 최대 256MB입니다." });

    let compiledCode: string | null | undefined;
    if (code !== undefined || runtime !== undefined) {
      const existing = await prisma.function.findUnique({ where: { id: req.params.id }, select: { code: true, runtime: true } });
      if (!existing) return res.status(404).json({ error: "Not found" });
      const effectiveRuntime = runtime ?? existing.runtime;
      const effectiveCode = code ?? existing.code;
      if (effectiveRuntime === "typescript") {
        try {
          compiledCode = await compileTypeScript(effectiveCode);
        } catch (e: any) {
          return res.status(400).json({ error: `TypeScript 컴파일 오류: ${e.message}` });
        }
      } else {
        // JS → CJS 변환
        try {
          compiledCode = await compileJavaScript(effectiveCode);
        } catch (e: any) {
          return res.status(400).json({ error: `JavaScript 컴파일 오류: ${e.message}` });
        }
      }
    }

    const updated = await prisma.function.update({
      where: { id: req.params.id },
      data: {
        ...(name !== undefined && { name }),
        ...(description !== undefined && { description }),
        ...(code !== undefined && { code }),
        ...(runtime !== undefined && { runtime }),
        ...(timeout !== undefined && { timeout }),
        ...(memoryLimit !== undefined && { memoryLimit }),
        ...(envVars !== undefined && { envVars: JSON.stringify(envVars) }),
        ...(status !== undefined && { status }),
        ...(compiledCode !== undefined && { compiledCode }),
      },
    });
    res.json({ ...updated, envVars: JSON.parse(updated.envVars) });
  } catch (err: any) {
    if (err.code === "P2002") return res.status(409).json({ error: "같은 이름의 함수가 이미 존재합니다." });
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

router.delete("/:id", async (req, res, next) => {
  try {
    await assertOwnership(req.params.id, req.user!.userId, req.user!.role);
    await prisma.function.delete({ where: { id: req.params.id } });
    res.status(204).send();
  } catch (err: any) {
    if (err.statusCode) return res.status(err.statusCode).json({ error: err.message });
    next(err);
  }
});

export default router;

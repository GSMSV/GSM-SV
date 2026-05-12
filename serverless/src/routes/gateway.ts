// HTTP 트리거 게이트웨이:
// 외부에서 fn.gsmsv.site/{ownerId}/{funcName}[/subpath] 으로 요청이 들어오면
// URL에서 ownerId와 함수 이름을 추출해 DB에서 함수를 조회하고 실행한다.
// 인증 없이 공개 접근 가능 — 트리거에 httpMethod가 설정된 함수만 호출 가능.
import { Router } from "express";
import { prisma } from "../db/prisma";
import { runFunction } from "../services/executionService";

const router = Router();

// /{ownerId}/{funcName} 또는 /{ownerId}/{funcName}/subpath 패턴
router.all(/^\/(\d+)\/([^/?#]+)(\/.*)?$/, async (req, res, next) => {
  try {
    const [, userIdStr, funcName] = req.path.match(/^\/(\d+)\/([^/?#]+)/) || [];
    const ownerId = parseInt(userIdStr);

    const func = await prisma.function.findUnique({
      where: { ownerId_name: { ownerId, name: funcName } },
      include: { triggers: { where: { type: "http", enabled: true } } },
    });

    if (!func || func.status !== "active") return res.status(404).json({ error: "Function not found" });
    if (func.triggers.length === 0) return res.status(404).json({ error: "No HTTP trigger enabled" });

    // httpMethod가 ANY이거나 실제 메서드와 일치하는 트리거만 통과
    const trigger = func.triggers.find(t => t.httpMethod === "ANY" || t.httpMethod === req.method);
    if (!trigger) return res.status(405).json({ error: "Method Not Allowed" });

    // HTTP 메타데이터(method/headers/query)를 포함해 함수 실행
    // req.body는 express.json() 미들웨어가 파싱한 JSON 객체
    const result = await runFunction(func, req.body || null, "http", {
      method: req.method,
      headers: req.headers as Record<string, string>,
      query: req.query as Record<string, string>,
    });

    // 사용자 handler가 반환한 Response의 status/headers/body를 그대로 응답
    res.status(result.statusCode).set(result.headers).send(result.body);
  } catch (err) { next(err); }
});

export default router;

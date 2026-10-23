// HTTP 트리거 게이트웨이:
// 외부에서 fn.gsmsv.site/{ownerId}/{funcName}[/subpath] 으로 요청이 들어오면
// URL에서 ownerId와 함수 이름을 추출해 DB에서 함수를 조회하고 실행한다.
// Legacy HTTP triggers remain public; new triggers require X-Secret-Token.
import { Router } from "express";
import { authorizeHttpTrigger } from "../services/triggerAuth";
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

    const token = req.get("X-Secret-Token");
    const authorization = authorizeHttpTrigger(func.triggers, req.method, token);
    if (authorization === "method-not-allowed") return res.status(405).json({ error: "Method Not Allowed" });
    if (authorization === "unauthorized") return res.status(401).json({ error: "Unauthorized" });

    // Never expose credentials to user code or execution logs.
    const { "x-secret-token": _token, ...headers } = req.headers;
    const { secretToken: _queryToken, ...query } = req.query;
    // HTTP 메타데이터(method/headers/query)를 포함해 함수 실행
    // req.body는 express.json() 미들웨어가 파싱한 JSON 객체
    const result = await runFunction(func, req.body || null, "http", {
      method: req.method,
      headers: headers as Record<string, string>,
      query: query as Record<string, string>,
    });

    // 사용자 handler가 반환한 Response의 status/headers/body를 그대로 응답
    res.status(result.statusCode).set(result.headers).send(result.body);
  } catch (err) { next(err); }
});

export default router;

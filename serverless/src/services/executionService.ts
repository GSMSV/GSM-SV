import { prisma } from "../db/prisma";
import { executeFunction, compileTypeScript, FunctionRequest } from "../engine/runtime";
import { Function as Fn } from "@prisma/client";

export async function runFunction(
  func: Fn,
  payload: unknown,
  triggerType: "manual" | "http" | "cron",
  httpMeta?: { method: string; headers: Record<string, string>; query: Record<string, string> }
) {
  const envVars = JSON.parse(func.envVars || "{}") as Record<string, string>;

  const request: FunctionRequest = {
    method: httpMeta?.method || "POST",
    url: httpMeta ? `https://fn.gsmsv.site/${func.ownerId}/${func.name}` : "",
    headers: httpMeta?.headers || {},
    body: payload ? JSON.stringify(payload) : null,
  };

  let compiledCode = func.compiledCode;
  if (!compiledCode && func.runtime === "typescript") {
    compiledCode = await compileTypeScript(func.code);
    await prisma.function.update({ where: { id: func.id }, data: { compiledCode } });
  }

  const result = await executeFunction(
    func.code,
    func.runtime as "javascript" | "typescript",
    request,
    envVars,
    { timeout: func.timeout, memoryLimit: func.memoryLimit },
    compiledCode
  );

  await prisma.executionLog.create({
    data: {
      functionId: func.id,
      trigger: triggerType,
      status: result.status,
      duration: result.duration,
      logs: JSON.stringify(result.logs),
      error: result.error,
      requestBody: payload ? JSON.stringify(payload) : null,
      response: result.body,
    },
  });

  return result;
}

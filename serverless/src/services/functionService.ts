import { prisma } from "../db/prisma";
import { config } from "../config";

export async function checkFunctionLimit(ownerId: number): Promise<void> {
  const count = await prisma.function.count({ where: { ownerId } });
  if (count >= config.maxFunctionsPerUser) {
    throw Object.assign(new Error(`함수 최대 개수(${config.maxFunctionsPerUser}개)에 도달했습니다.`), { statusCode: 429 });
  }
}

export async function assertOwnership(id: string, ownerId: number, role: string): Promise<void> {
  if (role === "admin") return;
  const func = await prisma.function.findUnique({ where: { id } });
  if (!func || func.ownerId !== ownerId) {
    throw Object.assign(new Error("Not found"), { statusCode: 404 });
  }
}

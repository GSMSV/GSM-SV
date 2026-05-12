import { Request, Response, NextFunction } from "express";

export function errorHandler(err: Error, req: Request, res: Response, _next: NextFunction): void {
  console.error("[error]", err.message);
  res.status(500).json({ error: err.message || "Internal Server Error" });
}

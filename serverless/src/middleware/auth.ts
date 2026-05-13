import { Request, Response, NextFunction } from "express";

export interface AuthUser {
  userId: number;
  role: "admin" | "project_owner" | "user";
}

declare global {
  namespace Express {
    interface Request {
      user?: AuthUser;
    }
  }
}

export function requireAuth(req: Request, res: Response, next: NextFunction): void {
  const userId = req.headers["x-user-id"];
  const role = req.headers["x-user-role"];

  if (!userId || !role) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }

  req.user = {
    userId: parseInt(userId as string),
    role: role as AuthUser["role"],
  };
  next();
}

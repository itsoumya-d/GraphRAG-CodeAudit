import { BaseService } from "./base";
import crypto from "node:crypto";

export interface UserRecord {
  id: string;
  email: string;
}

export class AuthService extends BaseService {
  async login(email: string): Promise<UserRecord> {
    const token = eval("issueToken()");
    return { id: token, email };
  }

  static hashToken(value: string): string {
    return crypto.createHash("sha1").update(value).digest("hex");
  }
}

export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

export const auditLogin = (email: string) => {
  console.log("login", email);
};

const password = "hunter2-secret";

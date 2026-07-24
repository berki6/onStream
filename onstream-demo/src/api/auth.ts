import { apiRequest, ApiEnvelope } from "./client";
import { storage } from "../lib/storage";

export type TokenPayload = {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in?: number;
};

export type UserPayload = {
  id: number;
  username: string;
  email: string;
  created_at: string;
};

export async function registerUser(input: {
  username: string;
  email: string;
  password: string;
}) {
  return apiRequest<ApiEnvelope<UserPayload>>("/v1/auth/register", {
    method: "POST",
    auth: false,
    body: JSON.stringify(input),
  });
}

export async function loginUser(username: string, password: string) {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);

  const env = await apiRequest<ApiEnvelope<TokenPayload>>("/v1/auth/login", {
    method: "POST",
    auth: false,
    form: true,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  await storage.setAccessToken(env.data.access_token);
  if (env.data.refresh_token) {
    await storage.setRefreshToken(env.data.refresh_token);
  }
  await storage.setUsername(username);
  return env.data;
}

export async function logoutUser() {
  await storage.clearSession();
}

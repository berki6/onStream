import { apiRequest, type ApiEnvelope } from "./client";

export type ApiKey = {
  id: number;
  name: string;
  key_prefix: string;
  scopes: string;
  is_active: boolean;
  created_at?: string | null;
  last_used_at?: string | null;
  api_key?: string;
};

export async function listApiKeys() {
  return apiRequest<ApiEnvelope<ApiKey[]>>("/v1/api-keys");
}

export async function createApiKey(name: string, scopes: string) {
  return apiRequest<ApiEnvelope<ApiKey>>("/v1/api-keys", {
    method: "POST",
    body: JSON.stringify({ name, scopes }),
  });
}

export async function revokeApiKey(id: number) {
  return apiRequest<ApiEnvelope<ApiKey>>(`/v1/api-keys/${id}`, {
    method: "DELETE",
  });
}

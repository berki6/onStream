import { apiRequest, ApiEnvelope } from "./client";

export type WebhookEndpoint = {
  id: number;
  url: string;
  events: string[];
  is_active: boolean;
  secret?: string;
  created_at?: string;
};

export type WebhookDelivery = {
  id: number;
  endpoint_id: number;
  event: string;
  status: string;
  attempts: number;
  last_error?: string | null;
  payload_preview?: string;
  created_at?: string | null;
};

const LAB_EVENTS = [
  "live.created",
  "live.started",
  "live.idle",
  "live.ended",
  "video.ready",
  "video.failed",
  "video.captions_ready",
];

export async function listWebhookEndpoints() {
  return apiRequest<ApiEnvelope<WebhookEndpoint[]>>("/v1/webhooks/");
}

export async function createWebhookEndpoint(input: {
  url: string;
  events?: string[];
}) {
  return apiRequest<ApiEnvelope<WebhookEndpoint>>("/v1/webhooks/", {
    method: "POST",
    body: JSON.stringify({
      url: input.url,
      events: input.events || LAB_EVENTS,
    }),
  });
}

export async function deleteWebhookEndpoint(endpointId: number) {
  return apiRequest<ApiEnvelope<unknown> | null>(`/v1/webhooks/${endpointId}`, {
    method: "DELETE",
  });
}

export async function listWebhookDeliveries(limit = 40) {
  return apiRequest<ApiEnvelope<WebhookDelivery[]>>(
    `/v1/webhooks/deliveries?limit=${limit}`
  );
}

export { LAB_EVENTS };

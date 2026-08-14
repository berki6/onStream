import { getApiBase } from "@/api/client";

/** PC Chrome secure context without installing a lab CA. */
export const PC_DEMO_ORIGIN = "http://127.0.0.1:8000";

/**
 * Phone browser origin for WHIP/WHEP demo pages.
 * Expo Go stays on http://LAN:8000 (user CAs are not trusted by the app).
 * Camera / RTCPeerConnection need https://LAN via Caddy.
 */
export function phoneHttpsOrigin(apiBase = getApiBase()): string {
  try {
    const u = new URL(apiBase.replace(/\/$/, ""));
    const host = u.hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      return PC_DEMO_ORIGIN;
    }
    u.protocol = "https:";
    u.port = "";
    return u.origin;
  } catch {
    return apiBase.replace(/\/$/, "");
  }
}

/** Direct MediaMTX WHIP so the API proxy never has to trust mkcert. */
export function loopbackWhipUrl(whipUrl: string): string {
  try {
    const u = new URL(whipUrl);
    u.protocol = "http:";
    u.hostname = "127.0.0.1";
    u.port = "8889";
    return u.href;
  } catch {
    return whipUrl;
  }
}

export function whipPublisherUrl(whipUrl: string, pageOrigin?: string): string {
  const origin = pageOrigin || phoneHttpsOrigin();
  const base = origin.replace(/\/$/, "");
  const whip =
    origin === PC_DEMO_ORIGIN ? loopbackWhipUrl(whipUrl) : whipUrl;
  return `${base}/demo/whip/?whip=${encodeURIComponent(whip)}`;
}

export function whepWatchUrl(
  streamId: string,
  token: string,
  pageOrigin?: string
): string {
  const base = (pageOrigin || phoneHttpsOrigin()).replace(/\/$/, "");
  return `${base}/demo/whep/?stream=${encodeURIComponent(streamId)}&token=${encodeURIComponent(token)}`;
}

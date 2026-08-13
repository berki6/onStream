/** Shared secondary status line for VOD rows / detail. */
export function videoPipelineHint(video: {
  status?: string | null;
  caption_vtt_path?: string | null;
  detected_language?: string | null;
}): { tone: "ok" | "warn" | "danger" | "muted"; text: string } {
  const status = String(video.status || "").toUpperCase();

  if (status === "QUARANTINED") {
    return {
      tone: "warn",
      text: "Quarantined — review in moderation before playback",
    };
  }
  if (status === "ERROR") {
    return { tone: "danger", text: "Transcode failed — check job / retry" };
  }
  if (status === "DELETED") {
    return { tone: "muted", text: "Deleted" };
  }
  if (
    status === "PENDING" ||
    status === "PROCESSING" ||
    status === "QUEUED" ||
    status === "UPLOADING"
  ) {
    return { tone: "warn", text: "Encoding… playback unlocks at READY" };
  }
  if (status === "READY") {
    if (video.caption_vtt_path) {
      const lang = video.detected_language
        ? ` · ${video.detected_language}`
        : "";
      return {
        tone: "ok",
        text: `READY · captions in playlist${lang}`,
      };
    }
    return {
      tone: "muted",
      text: "READY · captions pending or AI off",
    };
  }
  return { tone: "muted", text: status || "Unknown" };
}

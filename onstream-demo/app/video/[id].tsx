import { Stack, useLocalSearchParams } from "expo-router";
import * as Linking from "expo-linking";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";

import { ApiError, getApiBase } from "@/api/client";
import {
  createPlaybackToken,
  getVideo,
  Video,
} from "@/api/videos";
import { Button } from "@/components/Button";
import { CopyRow } from "@/components/CopyRow";
import { HlsPlayer } from "@/components/HlsPlayer";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { colors, spacing } from "@/theme/tokens";

const IN_FLIGHT = new Set(["PENDING", "PROCESSING", "QUEUED", "UPLOADING"]);

function captionsLabel(video: Video | null): string {
  if (!video) return "—";
  const status = String(video.status || "").toUpperCase();
  if (video.caption_vtt_path) {
    const lang = video.detected_language
      ? ` · ${video.detected_language}`
      : "";
    return `Ready${lang} — in HLS playlist`;
  }
  if (IN_FLIGHT.has(status)) return "Pending (after READY)";
  if (status === "READY") return "Pending or not enabled";
  if (status === "ERROR" || status === "QUARANTINED") return "Unavailable";
  return "Not ready";
}

export default function VideoDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [video, setVideo] = useState<Video | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tokenLoading, setTokenLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const focusedRef = useRef(true);

  const captionsReady = Boolean(video?.caption_vtt_path);

  const load = useCallback(async () => {
    if (!id) return;
    setError(null);
    try {
      const res = await getVideo(id);
      setVideo(res.data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load video");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      focusedRef.current = true;
      load();
      return () => {
        focusedRef.current = false;
      };
    }, [load])
  );

  useEffect(() => {
    const status = String(video?.status || "").toUpperCase();
    const waitingCaptions = status === "READY" && !video?.caption_vtt_path;
    if (!IN_FLIGHT.has(status) && !waitingCaptions) return;

    let ticks = 0;
    const maxTicks = waitingCaptions && !IN_FLIGHT.has(status) ? 12 : Infinity;
    const timer = setInterval(() => {
      ticks += 1;
      if (ticks > maxTicks) {
        clearInterval(timer);
        return;
      }
      if (focusedRef.current) load();
    }, 2500);
    return () => clearInterval(timer);
  }, [video?.status, video?.caption_vtt_path, load]);

  const ensurePlaybackUrl = useCallback(async () => {
    if (playbackUrl) return playbackUrl;
    if (!id) throw new Error("Missing video id");
    const res = await createPlaybackToken(id);
    setPlaybackUrl(res.data.playback_url);
    return res.data.playback_url;
  }, [id, playbackUrl]);

  return (
    <Screen>
      <Stack.Screen
        options={{
          title: video?.title || "Playback",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
        }}
      />
      {loading ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          {video ? (
            <View style={styles.meta}>
              <StatusPill status={video.status} />
              <Text style={styles.id}>{video.upload_id}</Text>
            </View>
          ) : null}

          {video ? (
            <View style={styles.infoBox}>
              <Text style={styles.section}>Captions</Text>
              <Text style={styles.infoLine}>{captionsLabel(video)}</Text>
              {captionsReady ? (
                <Text style={styles.infoDim}>
                  expo-video has limited track UI — use /demo/ for the captions
                  menu (master must include EXT-X-MEDIA SUBTITLES).
                </Text>
              ) : null}
              {video.caption_vtt_path ? (
                <Text style={styles.infoDim}>{video.caption_vtt_path}</Text>
              ) : null}
            </View>
          ) : null}

          <HlsPlayer uri={playbackUrl} title={video?.title} />

          {note ? <Text style={styles.note}>{note}</Text> : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Button
            label="Issue playback token"
            loading={tokenLoading}
            onPress={async () => {
              if (!id) return;
              setTokenLoading(true);
              setError(null);
              setNote(null);
              try {
                const res = await createPlaybackToken(id);
                setPlaybackUrl(res.data.playback_url);
              } catch (e) {
                setError(
                  e instanceof ApiError ? e.message : "Token request failed"
                );
              } finally {
                setTokenLoading(false);
              }
            }}
          />

          <Button
            label="Open in /demo/ (captions)"
            variant="ghost"
            loading={demoLoading}
            disabled={String(video?.status || "").toUpperCase() !== "READY"}
            onPress={async () => {
              setDemoLoading(true);
              setError(null);
              setNote(null);
              try {
                const url = await ensurePlaybackUrl();
                const demo = `${getApiBase()}/demo/?url=${encodeURIComponent(url)}`;
                const can = await Linking.canOpenURL(demo);
                if (!can) {
                  setNote(`Open this on the PC browser: ${demo}`);
                  return;
                }
                await Linking.openURL(demo);
                setNote(
                  captionsReady
                    ? "Opened /demo/ with this playback URL — use the Captions menu."
                    : "Opened /demo/ — captions appear after the AI captions job finishes."
                );
              } catch (e) {
                setError(
                  e instanceof ApiError
                    ? e.message
                    : e instanceof Error
                      ? e.message
                      : "Could not open /demo/"
                );
              } finally {
                setDemoLoading(false);
              }
            }}
          />

          <Button label="Refresh status" variant="ghost" onPress={load} />

          {playbackUrl ? <CopyRow label="Playback URL" value={playbackUrl} /> : null}
        </ScrollView>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: spacing.lg,
    gap: 14,
    paddingBottom: 40,
  },
  meta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  id: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
  },
  infoBox: { gap: 4 },
  section: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 16,
  },
  infoLine: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
  },
  infoDim: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    lineHeight: 17,
  },
  note: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
  },
});

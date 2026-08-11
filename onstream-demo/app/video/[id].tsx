import { Ionicons } from "@expo/vector-icons";
import { Stack, useFocusEffect, useLocalSearchParams } from "expo-router";
import * as Linking from "expo-linking";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

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
import { videoPipelineHint } from "@/lib/videoStatus";
import { colors, radii, spacing } from "@/theme/tokens";

const IN_FLIGHT = new Set(["PENDING", "PROCESSING", "QUEUED", "UPLOADING"]);

const HINT_COLOR = {
  ok: colors.ready,
  warn: colors.warning,
  danger: colors.danger,
  muted: colors.textDim,
} as const;

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
  const status = String(video?.status || "").toUpperCase();
  const isReady = status === "READY";
  const isBlocked = status === "ERROR" || status === "QUARANTINED";
  const pipeline = video ? videoPipelineHint(video) : null;

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
    const st = String(video?.status || "").toUpperCase();
    const waitingCaptions = st === "READY" && !video?.caption_vtt_path;
    if (!IN_FLIGHT.has(st) && !waitingCaptions) return;

    let ticks = 0;
    const maxTicks = waitingCaptions && !IN_FLIGHT.has(st) ? 12 : Infinity;
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
        <ScrollView
          contentContainerStyle={styles.content}
          bounces
          alwaysBounceVertical
          overScrollMode="always"
        >
          {video && pipeline ? (
            <View style={styles.statusBlock}>
              <View style={styles.meta}>
                <StatusPill status={video.status} />
                <Text style={styles.id}>{video.upload_id}</Text>
              </View>
              <View
                style={[
                  styles.pipelineBanner,
                  {
                    borderColor: HINT_COLOR[pipeline.tone],
                    backgroundColor:
                      pipeline.tone === "ok"
                        ? "rgba(46,230,166,0.08)"
                        : pipeline.tone === "warn"
                          ? "rgba(240,194,75,0.08)"
                          : pipeline.tone === "danger"
                            ? "rgba(255,107,107,0.08)"
                            : "rgba(0,0,0,0.2)",
                  },
                ]}
              >
                <Ionicons
                  name={
                    pipeline.tone === "ok"
                      ? "checkmark-circle"
                      : pipeline.tone === "danger"
                        ? "close-circle"
                        : pipeline.tone === "warn"
                          ? "alert-circle"
                          : "ellipse-outline"
                  }
                  size={18}
                  color={HINT_COLOR[pipeline.tone]}
                />
                <Text
                  style={[
                    styles.pipelineText,
                    { color: HINT_COLOR[pipeline.tone] },
                  ]}
                >
                  {pipeline.text}
                </Text>
              </View>
              {isReady && !captionsReady ? (
                <Text style={styles.infoDim}>
                  Asset is playable now. Captions arrive asynchronously after
                  the AI job — this is not an error.
                </Text>
              ) : null}
              {isBlocked ? (
                <Text style={styles.infoDim}>
                  {status === "QUARANTINED"
                    ? "Playback tokens are blocked until moderation clears quarantine."
                    : "Transcode failed — check worker logs or re-upload."}
                </Text>
              ) : null}
            </View>
          ) : null}

          {video ? (
            <View style={styles.infoBox}>
              <Text style={styles.section}>Captions</Text>
              {captionsReady ? (
                <>
                  <Text style={styles.infoLine}>
                    In HLS playlist
                    {video.detected_language
                      ? ` · ${video.detected_language}`
                      : ""}
                  </Text>
                  <Text style={styles.infoDim}>
                    expo-video has limited track UI — use /demo/ for the
                    captions menu.
                  </Text>
                  {video.caption_vtt_path ? (
                    <Text style={styles.infoDim}>{video.caption_vtt_path}</Text>
                  ) : null}
                </>
              ) : isReady ? (
                <Text style={styles.infoLine}>
                  Pending — video READY, waiting on captions job (or AI off)
                </Text>
              ) : IN_FLIGHT.has(status) ? (
                <Text style={styles.infoLine}>
                  After encode finishes (READY), then captions run
                </Text>
              ) : (
                <Text style={styles.infoLine}>Unavailable for this status</Text>
              )}
            </View>
          ) : null}

          <HlsPlayer uri={playbackUrl} title={video?.title} />

          {note ? <Text style={styles.note}>{note}</Text> : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Button
            label="Issue playback token"
            loading={tokenLoading}
            disabled={isBlocked}
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
            disabled={!isReady}
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

          {playbackUrl ? (
            <CopyRow label="Playback URL" value={playbackUrl} />
          ) : null}
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
  statusBlock: { gap: 10 },
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
  pipelineBanner: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    padding: 12,
    borderRadius: radii.md,
    borderWidth: 1,
  },
  pipelineText: {
    flex: 1,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
    lineHeight: 20,
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

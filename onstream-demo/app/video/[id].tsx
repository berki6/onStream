import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Clipboard from "expo-clipboard";
import { Stack, useFocusEffect, useLocalSearchParams } from "expo-router";
import * as Linking from "expo-linking";
import React, { useCallback, useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError, getApiBase } from "@/api/client";
import { favoriteVideo, listSavedVideos, unfavoriteVideo } from "@/api/favorites";
import {
  createShareLink,
  listShareLinks,
  revokeShareLink,
  type ShareLink,
} from "@/api/shareLinks";
import { createPlaybackToken } from "@/api/videos";
import {
  getWatchProgress,
  upsertWatchProgress,
} from "@/api/watch";
import { Button } from "@/components/Button";
import { CinemaSheet } from "@/components/CinemaSheet";
import { CopyRow } from "@/components/CopyRow";
import { DetailSkeleton } from "@/components/DetailSkeleton";
import { HlsPlayer } from "@/components/HlsPlayer";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { videoPipelineHint } from "@/lib/videoStatus";
import { videoKeys } from "@/query/keys";
import { useVideoQuery } from "@/query/videos";
import { scrollPhysics } from "@/theme/scroll";
import { colors, radii, spacing } from "@/theme/tokens";

const IN_FLIGHT = new Set(["PENDING", "PROCESSING", "QUEUED", "UPLOADING"]);

const HINT_COLOR = {
  ok: colors.ready,
  warn: colors.warning,
  danger: colors.danger,
  muted: colors.textDim,
} as const;

const EXPIRY_PRESETS = [
  { label: "1 hour", seconds: 3600 },
  { label: "24 hours", seconds: 86400 },
  { label: "7 days", seconds: 86400 * 7 },
  { label: "30 days", seconds: 86400 * 30 },
] as const;

export default function VideoDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const qc = useQueryClient();
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [tokenLoading, setTokenLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [focused, setFocused] = useState(true);
  const [shareOpen, setShareOpen] = useState(false);
  const [shareBusy, setShareBusy] = useState(false);
  const [createdWatchUrl, setCreatedWatchUrl] = useState<string | null>(null);
  const [expirySeconds, setExpirySeconds] = useState(86400);
  const [favorited, setFavorited] = useState(false);

  const {
    data: video,
    isPending,
    isError,
    error,
    refetch,
  } = useVideoQuery(id, { focused });

  const progressQuery = useQuery({
    queryKey: videoKeys.progress(id || ""),
    enabled: Boolean(id),
    queryFn: async () => (await getWatchProgress(id!)).data,
  });

  const sharesQuery = useQuery({
    queryKey: videoKeys.shares(id || ""),
    enabled: Boolean(id) && shareOpen,
    queryFn: async () => (await listShareLinks(id!)).data,
  });

  useFocusEffect(
    useCallback(() => {
      setFocused(true);
      refetch();
      void progressQuery.refetch();
      void listSavedVideos(100).then((res) => {
        setFavorited(
          Boolean(res.data?.some((v) => v.upload_id === id))
        );
      });
      return () => setFocused(false);
    }, [refetch, progressQuery.refetch, id])
  );

  const captionsReady = Boolean(video?.caption_vtt_path);
  const status = String(video?.status || "").toUpperCase();
  const isReady = status === "READY";
  const isBlocked = status === "ERROR" || status === "QUARANTINED";
  const pipeline = video ? videoPipelineHint(video) : null;
  const cold = isPending && !video;
  const loadError =
    isError && !video
      ? error instanceof Error
        ? error.message
        : "Failed to load video"
      : null;

  const resumeAt = useMemo(() => {
    const p = progressQuery.data;
    if (!p || p.completed) return 0;
    return p.position_seconds > 5 ? p.position_seconds : 0;
  }, [progressQuery.data]);

  const ensurePlaybackUrl = useCallback(async () => {
    if (playbackUrl) return playbackUrl;
    if (!id) throw new Error("Missing video id");
    const res = await createPlaybackToken(id);
    setPlaybackUrl(res.data.playback_url);
    return res.data.playback_url;
  }, [id, playbackUrl]);

  const toggleFavorite = async () => {
    if (!id) return;
    try {
      if (favorited) {
        await unfavoriteVideo(id);
        setFavorited(false);
      } else {
        await favoriteVideo(id);
        setFavorited(true);
      }
      await qc.invalidateQueries({ queryKey: videoKeys.saved() });
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Favorite failed");
    }
  };

  const createShare = async () => {
    if (!id) return;
    setShareBusy(true);
    setActionError(null);
    try {
      const res = await createShareLink({
        videoId: id,
        expiresInSeconds: expirySeconds,
      });
      setCreatedWatchUrl(res.data.watch_url || res.data.share_url || null);
      if (res.data.watch_url) {
        await Clipboard.setStringAsync(res.data.watch_url);
        setNote("Watch link copied — token shown once.");
      }
      await sharesQuery.refetch();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Share failed");
    } finally {
      setShareBusy(false);
    }
  };

  const revoke = async (link: ShareLink) => {
    setShareBusy(true);
    try {
      await revokeShareLink(link.public_id);
      await sharesQuery.refetch();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Revoke failed");
    } finally {
      setShareBusy(false);
    }
  };

  return (
    <Screen>
      <Stack.Screen
        options={{
          title: video?.title || "Playback",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
          headerRight: () =>
            video ? (
              <Pressable
                onPress={() => {
                  void toggleFavorite();
                }}
                hitSlop={12}
                style={{ marginRight: 4 }}
              >
                <Ionicons
                  name={favorited ? "heart" : "heart-outline"}
                  size={24}
                  color={favorited ? colors.live : colors.text}
                />
              </Pressable>
            ) : null,
        }}
      />

      {cold ? (
        <DetailSkeleton variant="video" />
      ) : loadError ? (
        <View style={styles.content}>
          <Text style={styles.error}>{loadError}</Text>
          <Button label="Retry" onPress={() => { void refetch(); }} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          {...scrollPhysics}
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
              {resumeAt > 0 ? (
                <Text style={styles.resumeHint}>
                  Resuming near {Math.floor(resumeAt / 60)}:
                  {String(Math.floor(resumeAt % 60)).padStart(2, "0")}
                </Text>
              ) : null}
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

          <HlsPlayer
            uri={playbackUrl}
            title={video?.title}
            initialPositionSeconds={resumeAt}
            onProgress={(pos, dur) => {
              if (!id || pos < 1) return;
              void upsertWatchProgress(id, pos, dur).then(() => {
                void qc.invalidateQueries({ queryKey: videoKeys.continue() });
                void qc.invalidateQueries({
                  queryKey: videoKeys.progress(id),
                });
              });
            }}
          />

          {note ? <Text style={styles.note}>{note}</Text> : null}
          {actionError ? <Text style={styles.error}>{actionError}</Text> : null}

          <Button
            label={resumeAt > 0 ? "Play / resume" : "Issue playback token"}
            loading={tokenLoading}
            disabled={isBlocked}
            onPress={async () => {
              if (!id) return;
              setTokenLoading(true);
              setActionError(null);
              setNote(null);
              try {
                const res = await createPlaybackToken(id);
                setPlaybackUrl(res.data.playback_url);
              } catch (e) {
                setActionError(
                  e instanceof ApiError ? e.message : "Token request failed"
                );
              } finally {
                setTokenLoading(false);
              }
            }}
          />

          <View style={styles.actionToolbar}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Share link"
              disabled={!isReady}
              hitSlop={8}
              onPress={() => {
                setCreatedWatchUrl(null);
                setShareOpen(true);
              }}
              style={({ pressed }) => [
                styles.iconBtn,
                !isReady && styles.iconBtnDisabled,
                pressed && isReady && styles.iconBtnPressed,
              ]}
            >
              <Ionicons
                name="share-outline"
                size={22}
                color={isReady ? colors.text : colors.textDim}
              />
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Refresh status"
              hitSlop={8}
              onPress={() => {
                void refetch();
              }}
              style={({ pressed }) => [
                styles.iconBtn,
                pressed && styles.iconBtnPressed,
              ]}
            >
              <Ionicons name="refresh" size={22} color={colors.text} />
            </Pressable>
            <View style={styles.toolbarSpacer} />
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Open in demo player"
              disabled={!isReady || demoLoading}
              hitSlop={8}
              onPress={async () => {
                setDemoLoading(true);
                setActionError(null);
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
                  setActionError(
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
              style={({ pressed }) => [
                styles.demoChip,
                (!isReady || demoLoading) && styles.iconBtnDisabled,
                pressed && isReady && !demoLoading && styles.iconBtnPressed,
              ]}
            >
              <Ionicons
                name="desktop-outline"
                size={18}
                color={isReady ? colors.brand : colors.textDim}
              />
              <Text
                style={[
                  styles.demoChipLabel,
                  !isReady && { color: colors.textDim },
                ]}
              >
                {demoLoading ? "Opening…" : "Demo"}
              </Text>
            </Pressable>
          </View>

          {playbackUrl ? (
            <CopyRow label="Playback URL" value={playbackUrl} />
          ) : null}
        </ScrollView>
      )}

      <CinemaSheet
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        dismissEnabled={!shareBusy}
        onExited={() => {
          setCreatedWatchUrl(null);
        }}
      >
        <View style={styles.sheetHead}>
          <View style={styles.sheetTitleRow}>
            <Ionicons name="share-social" size={22} color={colors.brand} />
            <Text style={styles.sheetTitle}>Share link</Text>
          </View>
          <Pressable
            hitSlop={12}
            onPress={() => setShareOpen(false)}
            disabled={shareBusy}
            accessibilityRole="button"
            accessibilityLabel="Close"
          >
            <Ionicons
              name="close"
              size={24}
              color={shareBusy ? colors.textDim : colors.textMuted}
            />
          </Pressable>
        </View>
        <Text style={styles.sheetBody}>
          Anyone with the link can watch until it expires or you revoke it.
        </Text>
        <View style={styles.presetRow}>
          {EXPIRY_PRESETS.map((p) => (
            <Pressable
              key={p.seconds}
              onPress={() => setExpirySeconds(p.seconds)}
              style={[
                styles.preset,
                expirySeconds === p.seconds && styles.presetOn,
              ]}
            >
              <Text
                style={[
                  styles.presetText,
                  expirySeconds === p.seconds && styles.presetTextOn,
                ]}
              >
                {p.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <Button
          label="Create & copy watch URL"
          loading={shareBusy}
          onPress={() => {
            void createShare();
          }}
        />
        {createdWatchUrl ? (
          <CopyRow label="Watch URL (token once)" value={createdWatchUrl} />
        ) : null}
        <Text style={styles.section}>Active links</Text>
        {(sharesQuery.data ?? [])
          .filter((l) => l.active)
          .map((link) => (
            <View key={link.public_id} style={styles.shareRow}>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={styles.shareId}>{link.public_id}</Text>
                <Text style={styles.infoDim}>
                  Expires {new Date(link.expires_at).toLocaleString()} ·{" "}
                  {link.view_count} views
                </Text>
              </View>
              <Pressable onPress={() => void revoke(link)}>
                <Text style={styles.revoke}>Revoke</Text>
              </Pressable>
            </View>
          ))}
      </CinemaSheet>
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
  resumeHint: {
    color: colors.brand,
    fontFamily: "DMSans_500Medium",
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
  actionToolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  iconBtn: {
    width: 48,
    height: 48,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  iconBtnPressed: { opacity: 0.85, transform: [{ scale: 0.97 }] },
  iconBtnDisabled: { opacity: 0.4 },
  toolbarSpacer: { flex: 1 },
  demoChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 48,
    paddingHorizontal: 14,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  demoChipLabel: {
    color: colors.brand,
    fontFamily: "DMSans_700Bold",
    fontSize: 14,
  },
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
  },
  sheetHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sheetTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  sheetTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 20,
  },
  sheetBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
    lineHeight: 20,
    marginTop: -4,
  },
  presetRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  preset: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  presetOn: {
    borderColor: colors.brand,
    backgroundColor: colors.brandSoft,
  },
  presetText: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
  presetTextOn: { color: colors.brand },
  shareRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  shareId: {
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
  },
  revoke: {
    color: colors.danger,
    fontFamily: "DMSans_700Bold",
    fontSize: 13,
  },
});

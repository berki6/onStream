import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Clipboard from "expo-clipboard";
import { Stack, useFocusEffect, useLocalSearchParams, useRouter, type Href } from "expo-router";
import * as Linking from "expo-linking";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  Alert,
} from "react-native";

import { ApiError, getApiBase } from "@/api/client";
import { favoriteVideo, listSavedVideos, unfavoriteVideo } from "@/api/favorites";
import {
  createShareLink,
  listShareLinks,
  revokeShareLink,
  type ShareLink,
} from "@/api/shareLinks";
import {
  addVideoToPlaylist,
  type Playlist,
} from "@/api/playlists";
import {
  createPlaybackToken,
  deleteVideo,
  getVideoChapters,
  updateVideo,
  type VideoVisibility,
} from "@/api/videos";
import {
  clearWatchProgress,
  getWatchProgress,
  upsertWatchProgress,
} from "@/api/watch";
import { Button } from "@/components/Button";
import { CinemaSheet } from "@/components/CinemaSheet";
import { CopyRow } from "@/components/CopyRow";
import { DetailSkeleton } from "@/components/DetailSkeleton";
import { Field } from "@/components/Field";
import { HlsPlayer, type HlsPlayerHandle } from "@/components/HlsPlayer";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { StoryboardStrip } from "@/components/StoryboardStrip";
import { videoPipelineHint } from "@/lib/videoStatus";
import { playlistKeys, videoKeys } from "@/query/keys";
import { usePlaylistsQuery } from "@/query/playlists";
import { useVideoQuery } from "@/query/videos";
import { scrollPhysics } from "@/theme/scroll";
import { colors, radii, spacing } from "@/theme/tokens";

function formatChapterTime(seconds: number) {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

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

const MAX_VIEWS_PRESETS: { label: string; value: number | null }[] = [
  { label: "Unlimited", value: null },
  { label: "1 view", value: 1 },
  { label: "5 views", value: 5 },
  { label: "10 views", value: 10 },
  { label: "50 views", value: 50 },
];

export default function VideoDetailScreen() {
  const { id, play, playlist: playlistParam } = useLocalSearchParams<{
    id?: string;
    play?: string;
    playlist?: string;
  }>();
  const router = useRouter();
  const qc = useQueryClient();
  const playerRef = useRef<HlsPlayerHandle>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [tokenLoading, setTokenLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [focused, setFocused] = useState(true);
  const [shareOpen, setShareOpen] = useState(false);
  const [shareBusy, setShareBusy] = useState(false);
  const [createdWatchUrl, setCreatedWatchUrl] = useState<string | null>(null);
  const [createdAppUrl, setCreatedAppUrl] = useState<string | null>(null);
  const [expirySeconds, setExpirySeconds] = useState(86400);
  const [maxViews, setMaxViews] = useState<number | null>(null);
  const [favorited, setFavorited] = useState(false);
  const [resumeAt, setResumeAt] = useState(0);
  const resumeAppliedForId = useRef<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editBusy, setEditBusy] = useState(false);
  const [editVisibility, setEditVisibility] =
    useState<VideoVisibility>("private");
  const [clipOpen, setClipOpen] = useState(false);
  const [clipStart, setClipStart] = useState("0");
  const [clipEnd, setClipEnd] = useState("");
  const [playlistOpen, setPlaylistOpen] = useState(false);
  const [createdEmbed, setCreatedEmbed] = useState<string | null>(null);
  const playlistId = playlistParam ? Number(playlistParam) : NaN;

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
  const playlistsQuery = usePlaylistsQuery({
    enabled: playlistOpen || Number.isFinite(playlistId),
  });

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

  const chaptersQuery = useQuery({
    queryKey: videoKeys.chapters(id || ""),
    enabled: Boolean(id) && isReady,
    queryFn: async () => (await getVideoChapters(id!)).data.chapters ?? [],
    refetchInterval: (q) => {
      if (!focused) return false;
      const ch = q.state.data;
      if (ch && ch.length > 0) return false;
      return q.state.dataUpdateCount < 18 ? 3000 : false;
    },
  });

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      setFocused(true);
      refetch();
      void progressQuery.refetch();
      void listSavedVideos(100).then((res) => {
        if (cancelled) return;
        setFavorited(
          Boolean(res.data?.some((v) => v.upload_id === id))
        );
      });
      return () => {
        cancelled = true;
        setFocused(false);
      };
    }, [refetch, progressQuery.refetch, id])
  );

  // Freeze resume once per video id so progress upserts cannot re-seek.
  useEffect(() => {
    setPlaybackUrl(null);
    setResumeAt(0);
    resumeAppliedForId.current = null;
  }, [id]);

  useEffect(() => {
    if (!id) return;
    if (resumeAppliedForId.current === id) return;
    if (progressQuery.isSuccess) {
      resumeAppliedForId.current = id;
      const p = progressQuery.data;
      if (!p || p.completed) {
        setResumeAt(0);
        return;
      }
      setResumeAt(p.position_seconds > 5 ? p.position_seconds : 0);
      return;
    }
    if (progressQuery.isError) {
      resumeAppliedForId.current = id;
      setResumeAt(0);
    }
  }, [
    id,
    progressQuery.isSuccess,
    progressQuery.isError,
    progressQuery.data,
  ]);

  // Only auto-start when opened from Continue / History with ?play=1.
  // Wait until progress settles so HlsPlayer gets the correct resume seek.
  // Normal Library opens keep resume available but wait for Play.
  useEffect(() => {
    if (!id || !isReady || !focused) return;
    if (play !== "1" || playbackUrl) return;
    if (!progressQuery.isFetched) return;
    if (resumeAppliedForId.current !== id) return;

    let cancelled = false;
    setTokenLoading(true);
    setActionError(null);
    void createPlaybackToken(id)
      .then((res) => {
        if (!cancelled) setPlaybackUrl(res.data.playback_url);
      })
      .catch((e) => {
        if (!cancelled) {
          setActionError(
            e instanceof ApiError ? e.message : "Token request failed"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setTokenLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    id,
    isReady,
    focused,
    play,
    playbackUrl,
    progressQuery.isFetched,
    resumeAt,
  ]);

  const ensurePlaybackUrl = useCallback(async () => {
    if (playbackUrl) return playbackUrl;
    if (!id) throw new Error("Missing video id");
    const res = await createPlaybackToken(id);
    setPlaybackUrl(res.data.playback_url);
    return res.data.playback_url;
  }, [id, playbackUrl]);

  const toggleFavorite = async () => {
    if (!id) return;
    const prev = favorited;
    setFavorited(!prev);
    try {
      if (prev) {
        await unfavoriteVideo(id);
      } else {
        await favoriteVideo(id);
      }
      await qc.invalidateQueries({ queryKey: videoKeys.saved() });
    } catch (e) {
      setFavorited(prev);
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
        maxViews: maxViews ?? undefined,
      });
      const browser =
        res.data.watch_url || res.data.share_url || null;
      const app =
        res.data.app_url ||
        (res.data.public_id && res.data.token
          ? `onstream://watch?s=${res.data.public_id}&t=${res.data.token}`
          : null);
      setCreatedWatchUrl(browser);
      setCreatedAppUrl(app);
      setCreatedEmbed(
        browser
          ? `<iframe src="${browser}${browser.includes("?") ? "&" : "?"}embed=1" width="640" height="360" allow="autoplay; fullscreen" allowfullscreen></iframe>`
          : null
      );
      const copyTarget = app || browser;
      if (copyTarget) {
        await Clipboard.setStringAsync(copyTarget);
        setNote(
          app
            ? "App deep link copied — browser URL also listed below."
            : "Watch link copied — token shown once."
        );
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

  const openEdit = () => {
    setEditTitle(video?.title || "");
    setEditDescription(video?.description || "");
    setEditVisibility(
      (video?.visibility as VideoVisibility) ||
        (video?.is_public ? "public" : "private")
    );
    setEditOpen(true);
  };

  const saveEdit = async () => {
    if (!id) return;
    const title = editTitle.trim();
    if (title.length < 2) {
      setActionError("Title must be at least 2 characters.");
      return;
    }
    setEditBusy(true);
    setActionError(null);
    try {
      await updateVideo(id, {
        title,
        description: editDescription.trim() || null,
        visibility: editVisibility,
      });
      await qc.invalidateQueries({ queryKey: videoKeys.detail(id) });
      await qc.invalidateQueries({ queryKey: videoKeys.list() });
      setEditOpen(false);
      setNote("Title saved.");
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Update failed");
    } finally {
      setEditBusy(false);
    }
  };

  const confirmDelete = () => {
    if (!id || !video) return;
    Alert.alert(
      "Delete video?",
      `Permanently delete “${video.title}”. This cannot be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => {
            void (async () => {
              setEditBusy(true);
              setActionError(null);
              try {
                await deleteVideo(id);
                setEditOpen(false);
                await qc.invalidateQueries({ queryKey: videoKeys.list() });
                await qc.invalidateQueries({ queryKey: videoKeys.continue() });
                await qc.invalidateQueries({ queryKey: videoKeys.saved() });
                await qc.invalidateQueries({ queryKey: videoKeys.history() });
                if (router.canGoBack()) router.back();
                else router.replace("/(tabs)/videos");
              } catch (e) {
                setActionError(
                  e instanceof ApiError ? e.message : "Delete failed"
                );
              } finally {
                setEditBusy(false);
              }
            })();
          },
        },
      ]
    );
  };

  const jumpToChapter = async (start: number) => {
    if (!id || isBlocked) return;
    setActionError(null);
    try {
      if (!playbackUrl) {
        setTokenLoading(true);
        const res = await createPlaybackToken(id);
        setPlaybackUrl(res.data.playback_url);
        setTokenLoading(false);
        // Allow player to mount with uri, then seek.
        setTimeout(() => playerRef.current?.seekTo(start), 350);
      } else {
        playerRef.current?.seekTo(start);
      }
    } catch (e) {
      setTokenLoading(false);
      setActionError(
        e instanceof ApiError ? e.message : "Could not start playback"
      );
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
              <View style={styles.headerActions}>
                <Pressable
                  onPress={openEdit}
                  hitSlop={10}
                  accessibilityLabel="Edit video"
                  style={{ marginRight: 10 }}
                >
                  <Ionicons
                    name="create-outline"
                    size={22}
                    color={colors.text}
                  />
                </Pressable>
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
              </View>
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
                <View style={styles.resumeRow}>
                  <Text style={styles.resumeHint}>
                    Resuming near {Math.floor(resumeAt / 60)}:
                    {String(Math.floor(resumeAt % 60)).padStart(2, "0")}
                  </Text>
                  <Pressable
                    hitSlop={8}
                    onPress={() => {
                      if (!id) return;
                      Alert.alert(
                        "Clear resume position?",
                        "Starts this video from the beginning next time.",
                        [
                          { text: "Cancel", style: "cancel" },
                          {
                            text: "Clear",
                            style: "destructive",
                            onPress: () => {
                              void (async () => {
                                try {
                                  await clearWatchProgress(id);
                                  setResumeAt(0);
                                  await qc.invalidateQueries({
                                    queryKey: videoKeys.progress(id),
                                  });
                                  await qc.invalidateQueries({
                                    queryKey: videoKeys.continue(),
                                  });
                                  await qc.invalidateQueries({
                                    queryKey: videoKeys.history(),
                                  });
                                } catch {
                                  /* ignore */
                                }
                              })();
                            },
                          },
                        ]
                      );
                    }}
                  >
                    <Text style={styles.clearResume}>Clear</Text>
                  </Pressable>
                </View>
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
            ref={playerRef}
            uri={playbackUrl}
            title={video?.title}
            initialPositionSeconds={resumeAt}
            onEnded={() => {
              if (!Number.isFinite(playlistId) || !id) return;
              const items = playlistsQuery.data;
              void (async () => {
                const { listPlaylistVideos } = await import("@/api/playlists");
                const vids = (await listPlaylistVideos(playlistId)).data || [];
                const idx = vids.findIndex((v) => v.upload_id === id);
                const next = idx >= 0 ? vids[idx + 1] : null;
                if (next) {
                  router.replace(
                    `/video/${next.upload_id}?playlist=${playlistId}&play=1` as Href
                  );
                }
              })();
            }}
            onProgress={(pos, dur) => {
              if (!id || pos < 1) return;
              void upsertWatchProgress(id, pos, dur).then(() => {
                void qc.invalidateQueries({ queryKey: videoKeys.continue() });
                // Do not invalidate progress — that would change resumeAt and
                // remount/re-seek the player mid-watch.
              });
            }}
          />

          {playbackUrl && (video?.storyboard_vtt_url || video?.storyboard_url) ? (
            <StoryboardStrip
              vttUrl={
                video.storyboard_vtt_url
                  ? `${video.storyboard_vtt_url}${
                      video.storyboard_vtt_url.includes("?") ? "&" : "?"
                    }token=${encodeURIComponent(
                      playbackUrl.split("token=")[1]?.split("&")[0] || ""
                    )}`
                  : null
              }
              imageUrl={
                video.storyboard_url
                  ? `${video.storyboard_url}${
                      video.storyboard_url.includes("?") ? "&" : "?"
                    }token=${encodeURIComponent(
                      playbackUrl.split("token=")[1]?.split("&")[0] || ""
                    )}`
                  : null
              }
              onSeek={(sec) => playerRef.current?.seekTo(sec)}
            />
          ) : null}

          {isReady ? (
            <View style={styles.infoBox}>
              <Text style={styles.section}>Chapters</Text>
              {chaptersQuery.isPending ? (
                <Text style={styles.infoDim}>Loading chapters…</Text>
              ) : (chaptersQuery.data?.length ?? 0) > 0 ? (
                <View style={styles.chapterList}>
                  {chaptersQuery.data!.map((ch, i) => (
                    <Pressable
                      key={`${ch.start}-${i}`}
                      onPress={() => {
                        void jumpToChapter(Number(ch.start) || 0);
                      }}
                      style={({ pressed }) => [
                        styles.chapterRow,
                        pressed && { opacity: 0.85 },
                      ]}
                    >
                      <Text style={styles.chapterTime}>
                        {formatChapterTime(Number(ch.start) || 0)}
                      </Text>
                      <Text style={styles.chapterTitle} numberOfLines={2}>
                        {ch.title || `Chapter ${i + 1}`}
                      </Text>
                      <Ionicons
                        name="play-circle-outline"
                        size={20}
                        color={colors.brand}
                      />
                    </Pressable>
                  ))}
                </View>
              ) : (
                <Text style={styles.infoLine}>
                  {captionsReady
                    ? "No chapters yet — they appear after the chapters job finishes."
                    : "Chapters follow captions; waiting on AI jobs."}
                </Text>
              )}
            </View>
          ) : null}

          {note ? <Text style={styles.note}>{note}</Text> : null}
          {actionError ? <Text style={styles.error}>{actionError}</Text> : null}

          <Button
            label={
              playbackUrl
                ? "Reload stream"
                : resumeAt > 0
                  ? "Play / resume"
                  : "Issue playback token"
            }
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
              accessibilityLabel="Add to playlist"
              disabled={!isReady}
              hitSlop={8}
              onPress={() => setPlaylistOpen(true)}
              style={({ pressed }) => [
                styles.iconBtn,
                !isReady && styles.iconBtnDisabled,
                pressed && isReady && styles.iconBtnPressed,
              ]}
            >
              <Ionicons
                name="list-outline"
                size={22}
                color={isReady ? colors.text : colors.textDim}
              />
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Create clip"
              disabled={!isReady}
              hitSlop={8}
              onPress={() => setClipOpen(true)}
              style={({ pressed }) => [
                styles.iconBtn,
                !isReady && styles.iconBtnDisabled,
                pressed && isReady && styles.iconBtnPressed,
              ]}
            >
              <Ionicons
                name="cut-outline"
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
          setCreatedAppUrl(null);
          setCreatedEmbed(null);
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
          Anyone with the link can watch until it expires, hits the view limit,
          or you revoke it.
        </Text>
        <Text style={styles.sheetLabel}>Expires</Text>
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
        <Text style={styles.sheetLabel}>Max views</Text>
        <View style={styles.presetRow}>
          {MAX_VIEWS_PRESETS.map((p) => (
            <Pressable
              key={p.label}
              onPress={() => setMaxViews(p.value)}
              style={[
                styles.preset,
                maxViews === p.value && styles.presetOn,
              ]}
            >
              <Text
                style={[
                  styles.presetText,
                  maxViews === p.value && styles.presetTextOn,
                ]}
              >
                {p.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <Button
          label="Create & copy app link"
          loading={shareBusy}
          onPress={() => {
            void createShare();
          }}
        />
        {createdAppUrl ? (
          <CopyRow label="App deep link (onstream://)" value={createdAppUrl} />
        ) : null}
        {createdWatchUrl ? (
          <CopyRow label="Browser watch URL" value={createdWatchUrl} />
        ) : null}
        {createdEmbed ? (
          <CopyRow label="Embed iframe" value={createdEmbed} />
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
                  {link.max_views != null
                    ? `${link.view_count}/${link.max_views} views`
                    : `${link.view_count} views · unlimited`}
                </Text>
              </View>
              <Pressable onPress={() => void revoke(link)}>
                <Text style={styles.revoke}>Revoke</Text>
              </Pressable>
            </View>
          ))}
      </CinemaSheet>

      <CinemaSheet
        visible={editOpen}
        onClose={() => setEditOpen(false)}
        dismissEnabled={!editBusy}
      >
        <View style={styles.sheetHead}>
          <View style={styles.sheetTitleRow}>
            <Ionicons name="create-outline" size={22} color={colors.brand} />
            <Text style={styles.sheetTitle}>Edit video</Text>
          </View>
          <Pressable
            hitSlop={12}
            onPress={() => setEditOpen(false)}
            disabled={editBusy}
            accessibilityRole="button"
            accessibilityLabel="Close"
          >
            <Ionicons
              name="close"
              size={24}
              color={editBusy ? colors.textDim : colors.textMuted}
            />
          </Pressable>
        </View>
        <Field
          label="Title"
          value={editTitle}
          onChangeText={setEditTitle}
          autoCapitalize="sentences"
          maxLength={200}
        />
        <Field
          label="Description"
          value={editDescription}
          onChangeText={setEditDescription}
          multiline
          style={{ minHeight: 96, textAlignVertical: "top", paddingTop: 14 }}
          maxLength={2000}
        />
        <Text style={styles.sheetLabel}>Visibility</Text>
        <View style={styles.presetRow}>
          {(["private", "unlisted", "public"] as VideoVisibility[]).map(
            (v) => (
              <Pressable
                key={v}
                onPress={() => setEditVisibility(v)}
                style={[
                  styles.preset,
                  editVisibility === v && styles.presetOn,
                ]}
              >
                <Text
                  style={[
                    styles.presetText,
                    editVisibility === v && styles.presetTextOn,
                  ]}
                >
                  {v}
                </Text>
              </Pressable>
            )
          )}
        </View>
        <View style={styles.editActions}>
          <Pressable
            hitSlop={12}
            onPress={confirmDelete}
            disabled={editBusy}
            accessibilityRole="button"
            accessibilityLabel="Delete video"
            style={({ pressed }) => [
              pressed && !editBusy && { opacity: 0.7 },
              editBusy && { opacity: 0.4 },
            ]}
          >
            <Ionicons name="trash-outline" size={24} color={colors.danger} />
          </Pressable>
          <Pressable
            hitSlop={12}
            onPress={() => {
              void saveEdit();
            }}
            disabled={editBusy}
            accessibilityRole="button"
            accessibilityLabel="Save changes"
            style={({ pressed }) => [
              pressed && !editBusy && { opacity: 0.7 },
              editBusy && { opacity: 0.5 },
            ]}
          >
            {editBusy ? (
              <ActivityIndicator color={colors.brand} size="small" />
            ) : (
              <Ionicons name="save-outline" size={24} color={colors.brand} />
            )}
          </Pressable>
        </View>
      </CinemaSheet>

      <CinemaSheet
        visible={clipOpen}
        onClose={() => setClipOpen(false)}
        dismissEnabled={!shareBusy}
      >
        <View style={styles.sheetHead}>
          <View style={styles.sheetTitleRow}>
            <Ionicons name="cut-outline" size={22} color={colors.brand} />
            <Text style={styles.sheetTitle}>Instant clip</Text>
          </View>
          <Pressable hitSlop={12} onPress={() => setClipOpen(false)}>
            <Ionicons name="close" size={24} color={colors.textMuted} />
          </Pressable>
        </View>
        <Text style={styles.sheetBody}>
          Share a time window without re-encoding. The player seeks in and
          stops at the end.
        </Text>
        <Field
          label="Start (seconds)"
          value={clipStart}
          onChangeText={setClipStart}
          keyboardType="decimal-pad"
        />
        <Field
          label="End (seconds)"
          value={clipEnd}
          onChangeText={setClipEnd}
          keyboardType="decimal-pad"
          hint="Leave empty to play through the rest"
        />
        {(chaptersQuery.data ?? []).length > 0 ? (
          <>
            <Text style={styles.sheetLabel}>Use chapter</Text>
            {(chaptersQuery.data ?? []).slice(0, 8).map((ch, i) => (
              <Pressable
                key={`${ch.start}-${i}`}
                onPress={() => {
                  setClipStart(String(Math.floor(ch.start)));
                  setClipEnd(
                    ch.end != null ? String(Math.ceil(ch.end)) : ""
                  );
                }}
                style={styles.preset}
              >
                <Text style={styles.presetText}>
                  {ch.title} · {formatChapterTime(ch.start)}
                </Text>
              </Pressable>
            ))}
          </>
        ) : null}
        <Button
          label="Preview start"
          onPress={() => {
            const s = Number(clipStart);
            if (!Number.isFinite(s)) return;
            void ensurePlaybackUrl().then(() =>
              playerRef.current?.seekTo(s)
            );
          }}
        />
        <Button
          label="Create clip share link"
          loading={shareBusy}
          onPress={() => {
            const start = Number(clipStart);
            const end = clipEnd.trim() ? Number(clipEnd) : undefined;
            if (!id || !Number.isFinite(start)) return;
            setShareBusy(true);
            void createShareLink({
              videoId: id,
              expiresInSeconds: expirySeconds,
              clipStart: start,
              clipEnd: Number.isFinite(end as number) ? end : undefined,
            })
              .then(async (res) => {
                const browser =
                  res.data.watch_url || res.data.share_url || null;
                setCreatedWatchUrl(browser);
                setCreatedAppUrl(res.data.app_url || null);
                setClipOpen(false);
                setShareOpen(true);
                if (browser) await Clipboard.setStringAsync(browser);
                setNote("Clip share link created.");
              })
              .catch((e) => {
                setActionError(
                  e instanceof ApiError ? e.message : "Clip share failed"
                );
              })
              .finally(() => setShareBusy(false));
          }}
        />
      </CinemaSheet>

      <CinemaSheet
        visible={playlistOpen}
        onClose={() => setPlaylistOpen(false)}
      >
        <View style={styles.sheetHead}>
          <View style={styles.sheetTitleRow}>
            <Ionicons name="list" size={22} color={colors.brand} />
            <Text style={styles.sheetTitle}>Add to playlist</Text>
          </View>
          <Pressable hitSlop={12} onPress={() => setPlaylistOpen(false)}>
            <Ionicons name="close" size={24} color={colors.textMuted} />
          </Pressable>
        </View>
        {(playlistsQuery.data ?? []).length === 0 ? (
          <Text style={styles.sheetBody}>
            No playlists yet. Create one from Library → Playlists.
          </Text>
        ) : (
          (playlistsQuery.data as Playlist[]).map((p) => (
            <Pressable
              key={p.id}
              onPress={() => {
                if (!id) return;
                void addVideoToPlaylist(p.id, id, 0)
                  .then(() => {
                    void qc.invalidateQueries({
                      queryKey: playlistKeys.videos(p.id),
                    });
                    void qc.invalidateQueries({
                      queryKey: playlistKeys.list(),
                    });
                    setPlaylistOpen(false);
                    setNote(`Added to ${p.name}.`);
                  })
                  .catch((e) => {
                    setActionError(
                      e instanceof ApiError ? e.message : "Add failed"
                    );
                  });
              }}
              style={styles.shareRow}
            >
              <Text style={styles.shareId}>{p.name}</Text>
              <Ionicons name="add" size={20} color={colors.brand} />
            </Pressable>
          ))
        )}
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
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
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
    flex: 1,
  },
  resumeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  clearResume: {
    color: colors.danger,
    fontFamily: "DMSans_700Bold",
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
  editActions: {
    marginTop: 4,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
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
  sheetLabel: {
    color: colors.textDim,
    fontFamily: "DMSans_700Bold",
    fontSize: 11,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginTop: 8,
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
  chapterList: { gap: 8 },
  chapterRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  chapterTime: {
    color: colors.brand,
    fontFamily: "DMSans_700Bold",
    fontSize: 13,
    minWidth: 40,
  },
  chapterTitle: {
    flex: 1,
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
  },
});

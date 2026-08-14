import * as Linking from "expo-linking";
import { Stack, useFocusEffect, useLocalSearchParams, useRouter, type Href } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import React, { useCallback, useRef, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { queryErrorText, userFacingError } from "@/api/client";
import { createLiveToken, deleteLiveStream } from "@/api/live";
import { Button } from "@/components/Button";
import { CopyRow } from "@/components/CopyRow";
import { DetailSkeleton } from "@/components/DetailSkeleton";
import { HlsPlayer, type HlsPlayerHandle } from "@/components/HlsPlayer";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { PC_DEMO_ORIGIN, whepWatchUrl } from "@/lib/labOrigins";
import { toast } from "@/lib/toast";
import { liveKeys, videoKeys } from "@/query/keys";
import { useLiveHealthQuery, useLiveStreamQuery } from "@/query/live";
import { scrollPhysics } from "@/theme/scroll";
import { colors, spacing } from "@/theme/tokens";

export default function LiveDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [playbackToken, setPlaybackToken] = useState<string | null>(null);
  const [llMode, setLlMode] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [focused, setFocused] = useState(true);
  const playerRef = useRef<HlsPlayerHandle>(null);

  const {
    data: stream,
    isPending,
    isError,
    error,
    refetch: refetchStream,
  } = useLiveStreamQuery(id, { focused });

  const {
    data: health,
    refetch: refetchHealth,
  } = useLiveHealthQuery(id, { focused });

  useFocusEffect(
    useCallback(() => {
      setFocused(true);
      refetchStream();
      refetchHealth();
      return () => setFocused(false);
    }, [refetchStream, refetchHealth])
  );

  const ended = String(stream?.status || "").toLowerCase() === "ended";
  const cold = isPending && !stream;
  const loadError = queryErrorText(Boolean(isError && !stream), error);
  const llAvailable = Boolean(stream?.ll_hls && stream?.ll_playback_url);

  return (
    <Screen>
      <Stack.Screen
        options={{
          title: stream?.title || "Live",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
        }}
      />

      {cold ? (
        <DetailSkeleton variant="live" />
      ) : loadError ? (
        <View style={styles.content}>
          <Text style={styles.error}>{loadError}</Text>
          <Button
            label="Retry"
            onPress={() => {
              void refetchStream();
              void refetchHealth();
            }}
          />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.content} {...scrollPhysics}>
          {stream ? (
            <View style={styles.meta}>
              <StatusPill status={stream.status} />
              <Text style={styles.id}>{stream.stream_id}</Text>
            </View>
          ) : null}

          {ended ? (
            <Text style={styles.endedNote}>
              Stream revoked. Live playlist requests return 404. If a replay
              was saved, Watch replay opens it in Library like any VOD.
            </Text>
          ) : llMode ? (
            <Text style={styles.endedNote}>
              Playing LL-HLS: a sliding live edge (~2–4s), not the DVR
              archive. There is no timeline to scrub. Sub-second remains WHEP.
            </Text>
          ) : (
            <Text style={styles.endedNote}>
              HLS is DVR: join at the live edge, then scrub the timeline.
              Jump to live returns to the edge.
              {llAvailable
                ? " LL-HLS is a separate playlist (no scrub)."
                : ""}{" "}
              WHEP stays sub-second.
            </Text>
          )}

          <HlsPlayer
            ref={playerRef}
            uri={ended ? null : playbackUrl}
            title={stream?.title}
            liveEdge
          />

          {playbackUrl && !ended && !llMode ? (
            <Button
              label="Jump to live"
              variant="ghost"
              onPress={() => playerRef.current?.jumpToLive()}
            />
          ) : null}

          {health ? (
            <View style={styles.healthBox}>
              <Text style={styles.section}>Health</Text>
              <Text style={styles.healthLine}>
                Status {health.status}
                {" · "}
                Playlist {health.playlist_present ? "present" : "missing"}
                {health.playlist_age_seconds != null
                  ? ` · age ${health.playlist_age_seconds.toFixed(1)}s`
                  : ""}
                {health.is_stale ? " · STALE" : ""}
              </Text>
              {health.dvr ? (
                <Text style={styles.healthLine}>
                  DVR {Math.floor(health.dvr_duration_seconds || 0)}s available
                  {health.archive_running ? " · recording" : ""}
                </Text>
              ) : null}
              {health.ll_hls ? (
                <Text style={styles.healthLine}>
                  LL-HLS {health.ll_playlist_present ? "playlist ready" : "waiting"}
                </Text>
              ) : null}
            </View>
          ) : null}

          <Button
            label="Issue live playback token"
            disabled={ended}
            onPress={async () => {
              if (!id || ended) return;
              try {
                const res = await createLiveToken(id);
                setLlMode(false);
                setPlaybackUrl(res.data.playback_url);
                setPlaybackToken(res.data.token);
              } catch (e) {
                toast.error(userFacingError(e, "Token failed"));
              }
            }}
          />
          {playbackToken && !ended && llAvailable ? (
            <Button
              label="Play LL-HLS (no scrub)"
              variant="ghost"
              disabled={ended}
              onPress={async () => {
                if (!id || ended) return;
                try {
                  const res = await createLiveToken(id);
                  const url = res.data.ll_playback_url;
                  if (!url) {
                    toast.error("LL-HLS is not enabled on this API.");
                    return;
                  }
                  setLlMode(true);
                  setPlaybackUrl(url);
                  setPlaybackToken(res.data.token);
                } catch (e) {
                  toast.error(userFacingError(e, "LL token failed"));
                }
              }}
            />
          ) : null}
          <Button
            label="Refresh health"
            variant="ghost"
            onPress={() => {
              refetchStream();
              refetchHealth();
            }}
          />
          {!ended ? (
            <Button
              label="Revoke stream"
              variant="danger"
              loading={revoking}
              onPress={async () => {
                if (!id) return;
                setRevoking(true);
                try {
                  const res = await deleteLiveStream(id);
                  qc.setQueryData(liveKeys.detail(id), res.data);
                  await qc.invalidateQueries({ queryKey: liveKeys.list() });
                  await qc.invalidateQueries({
                    queryKey: liveKeys.health(id),
                  });
                  await qc.invalidateQueries({ queryKey: videoKeys.list() });
                  setPlaybackUrl(null);
                  setPlaybackToken(null);
                  setLlMode(false);
                  toast.success(
                    res.data.archived_upload_id
                      ? "Stream revoked. Replay is in Library."
                      : "Stream revoked. Playback through OnStream is ended."
                  );
                } catch (e) {
                  toast.error(userFacingError(e, "Delete failed"));
                } finally {
                  setRevoking(false);
                }
              }}
            />
          ) : (
            <>
              {stream?.archived_upload_id ? (
                <Button
                  label="Watch replay"
                  onPress={() =>
                    router.push(`/video/${stream.archived_upload_id}` as Href)
                  }
                />
              ) : null}
              <Button
                label="Back to live list"
                variant="ghost"
                onPress={() => router.back()}
              />
            </>
          )}

          {playbackUrl && !ended ? (
            <CopyRow
              label={llMode ? "LL-HLS playback" : "Playback URL"}
              value={playbackUrl}
            />
          ) : null}
          {playbackToken && id && !ended ? (
            <>
              <CopyRow
                label="PC WHEP watch (localhost)"
                value={whepWatchUrl(id, playbackToken, PC_DEMO_ORIGIN)}
              />
              <CopyRow
                label="Phone WHEP (HTTPS)"
                value={whepWatchUrl(id, playbackToken)}
              />
              <Button
                label="Watch live (low latency)"
                variant="ghost"
                onPress={async () => {
                  const url = whepWatchUrl(id, playbackToken);
                  try {
                    await Linking.openURL(url);
                  } catch {
                    toast.error("Could not open WHEP player");
                  }
                }}
              />
            </>
          ) : null}
          {stream?.playback_url ? (
            <CopyRow label="Public DVR playback" value={stream.playback_url} />
          ) : null}
          {stream?.ll_playback_url ? (
            <CopyRow label="Public LL-HLS" value={stream.ll_playback_url} />
          ) : null}
          {stream?.webrtc_base ? (
            <CopyRow label="WebRTC base" value={stream.webrtc_base} />
          ) : null}
        </ScrollView>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.lg, gap: 14, paddingBottom: 40 },
  meta: { flexDirection: "row", alignItems: "center", gap: 12 },
  id: { color: colors.textDim, fontFamily: "DMSans_400Regular", fontSize: 13 },
  healthBox: { gap: 6 },
  section: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 16,
  },
  healthLine: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
  },
  endedNote: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
    lineHeight: 20,
  },
  error: { color: colors.danger, fontFamily: "DMSans_500Medium" },
});

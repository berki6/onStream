import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";

import { ApiError } from "@/api/client";
import {
  createLiveToken,
  deleteLiveStream,
  getLiveHealth,
  getLiveStream,
  LiveHealth,
  LiveStream,
} from "@/api/live";
import { Button } from "@/components/Button";
import { CopyRow } from "@/components/CopyRow";
import { HlsPlayer } from "@/components/HlsPlayer";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { colors, spacing } from "@/theme/tokens";

export default function LiveDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [stream, setStream] = useState<LiveStream | null>(null);
  const [health, setHealth] = useState<LiveHealth | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [revoking, setRevoking] = useState(false);

  const ended = String(stream?.status || "").toLowerCase() === "ended";

  const load = useCallback(async () => {
    if (!id) return;
    setError(null);
    try {
      const [s, h] = await Promise.all([getLiveStream(id), getLiveHealth(id)]);
      setStream(s.data);
      setHealth(h.data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load stream");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

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
      {loading ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          {stream ? (
            <View style={styles.meta}>
              <StatusPill status={stream.status} />
              <Text style={styles.id}>{stream.stream_id}</Text>
            </View>
          ) : null}

          {ended ? (
            <Text style={styles.endedNote}>
              Stream revoked. New playlist requests return 404. Buffered
              seconds may finish, then the player stalls. The encoder may keep
              publishing until kicked or stopped.
            </Text>
          ) : null}

          <HlsPlayer
            uri={ended ? null : playbackUrl}
            title={stream?.title}
          />

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
            </View>
          ) : null}

          {note ? <Text style={styles.note}>{note}</Text> : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Button
            label="Issue live playback token"
            disabled={ended}
            onPress={async () => {
              if (!id || ended) return;
              try {
                const res = await createLiveToken(id);
                setPlaybackUrl(res.data.playback_url);
                setNote(null);
              } catch (e) {
                setError(e instanceof ApiError ? e.message : "Token failed");
              }
            }}
          />
          <Button label="Refresh health" variant="ghost" onPress={load} />
          {!ended ? (
            <Button
              label="Revoke stream"
              variant="danger"
              loading={revoking}
              onPress={async () => {
                if (!id) return;
                setRevoking(true);
                setError(null);
                try {
                  const res = await deleteLiveStream(id);
                  setStream(res.data);
                  setPlaybackUrl(null);
                  setNote(
                    "Revoked. Playback through OnStream is ended; refresh health if needed."
                  );
                  try {
                    const h = await getLiveHealth(id);
                    setHealth(h.data);
                  } catch {
                    /* health optional after revoke */
                  }
                } catch (e) {
                  setError(e instanceof ApiError ? e.message : "Delete failed");
                } finally {
                  setRevoking(false);
                }
              }}
            />
          ) : (
            <Button
              label="Back to live list"
              variant="ghost"
              onPress={() => router.back()}
            />
          )}

          {playbackUrl && !ended ? (
            <CopyRow label="Playback URL" value={playbackUrl} />
          ) : null}
          {stream?.playback_url ? (
            <CopyRow label="Public playback" value={stream.playback_url} />
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
  note: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
  error: { color: colors.danger, fontFamily: "DMSans_500Medium" },
});

import { Stack, useLocalSearchParams } from "expo-router";
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

export default function VideoDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [video, setVideo] = useState<Video | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tokenLoading, setTokenLoading] = useState(false);

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
      load();
    }, [load])
  );

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

          <HlsPlayer uri={playbackUrl} title={video?.title} />

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Button
            label="Issue playback token"
            loading={tokenLoading}
            onPress={async () => {
              if (!id) return;
              setTokenLoading(true);
              setError(null);
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
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
  },
});

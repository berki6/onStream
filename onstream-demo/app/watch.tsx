import { Stack, useLocalSearchParams } from "expo-router";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { ApiError } from "@/api/client";
import { exchangeShareLink } from "@/api/shareLinks";
import { HlsPlayer } from "@/components/HlsPlayer";
import { Screen } from "@/components/Screen";
import { colors, spacing } from "@/theme/tokens";

/**
 * Deep-link / shared watch surface: onstream://watch?s=&t=
 * or Expo route /watch?s=&t=
 */
export default function WatchShareScreen() {
  const { s, t } = useLocalSearchParams<{ s?: string; t?: string }>();
  const [title, setTitle] = useState("Shared watch");
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!s || !t) {
        setError("Missing share id or token.");
        setLoading(false);
        return;
      }
      try {
        const res = await exchangeShareLink(s, t);
        if (cancelled) return;
        setPlaybackUrl(res.data.playback_url);
        setTitle(res.data.title);
        setExpiresAt(res.data.expires_at);
      } catch (e) {
        if (cancelled) return;
        const code = e instanceof ApiError ? e.code : null;
        if (code === "SHARE_EXPIRED") setError("This share link has expired.");
        else if (code === "SHARE_REVOKED")
          setError("This share link was revoked.");
        else if (code === "SHARE_VIEW_LIMIT")
          setError("This share reached its view limit.");
        else
          setError(e instanceof Error ? e.message : "Could not open share.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [s, t]);

  return (
    <Screen>
      <Stack.Screen
        options={{
          headerShown: true,
          title: "Shared video",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
        }}
      />
      <View style={styles.body}>
        {loading ? (
          <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
        ) : null}
        {error ? (
          <View style={styles.errBox}>
            <Text style={styles.errTitle}>Unavailable</Text>
            <Text style={styles.errBody}>{error}</Text>
          </View>
        ) : (
          <>
            <Text style={styles.title}>{title}</Text>
            {expiresAt ? (
              <Text style={styles.meta}>
                Link expires {new Date(expiresAt).toLocaleString()}
              </Text>
            ) : null}
            <HlsPlayer uri={playbackUrl} title={title} />
          </>
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: {
    padding: spacing.lg,
    gap: 12,
  },
  title: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 24,
  },
  meta: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
  },
  errBox: {
    marginTop: 32,
    gap: 8,
  },
  errTitle: {
    color: colors.danger,
    fontFamily: "Syne_700Bold",
    fontSize: 22,
  },
  errBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
  },
});

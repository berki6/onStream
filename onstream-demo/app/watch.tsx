import { Ionicons } from "@expo/vector-icons";
import * as Linking from "expo-linking";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "@/api/client";
import { exchangeShareLink } from "@/api/shareLinks";
import { Button } from "@/components/Button";
import { HlsPlayer, type HlsPlayerHandle } from "@/components/HlsPlayer";
import { Screen } from "@/components/Screen";
import { StoryboardStrip } from "@/components/StoryboardStrip";
import { colors, radii, spacing } from "@/theme/tokens";

/**
 * Shared watch surface — works signed-in or out.
 * Accepts:
 *   /watch?s=&t=
 *   onstream://watch?s=&t=
 *   …/demo/watch/?s=&t= (if the OS hands the https URL to the app)
 */

function firstParam(v: string | string[] | undefined): string | undefined {
  if (Array.isArray(v)) return v[0];
  return v;
}

function paramsFromUrl(url: string | null): { s?: string; t?: string } {
  if (!url) return {};
  try {
    const parsed = Linking.parse(url);
    const q = parsed.queryParams || {};
    const s = firstParam(q.s as string | string[] | undefined);
    const t = firstParam(q.t as string | string[] | undefined);
    if (s && t) return { s, t };
    // Fallback: raw query on path-style demo URLs
    const u = new URL(url.replace(/^onstream:/i, "https:"));
    return {
      s: u.searchParams.get("s") || undefined,
      t: u.searchParams.get("t") || undefined,
    };
  } catch {
    return {};
  }
}

export default function WatchShareScreen() {
  const router = useRouter();
  const playerRef = React.useRef<HlsPlayerHandle>(null);
  const routeParams = useLocalSearchParams<{
    s?: string | string[];
    t?: string | string[];
  }>();
  const [linkParams, setLinkParams] = useState<{ s?: string; t?: string }>({});
  const s = firstParam(routeParams.s) || linkParams.s;
  const t = firstParam(routeParams.t) || linkParams.t;

  const [title, setTitle] = useState("Shared watch");
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const [clipStart, setClipStart] = useState(0);
  const [clipEnd, setClipEnd] = useState<number | null>(null);
  const [storyboardVtt, setStoryboardVtt] = useState<string | null>(null);
  const [storyboardImg, setStoryboardImg] = useState<string | null>(null);

  const missing = useMemo(() => !s || !t, [s, t]);

  useEffect(() => {
    let alive = true;
    void Linking.getInitialURL().then((url) => {
      if (!alive || !url) return;
      const p = paramsFromUrl(url);
      if (p.s && p.t) setLinkParams(p);
    });
    const sub = Linking.addEventListener("url", ({ url }) => {
      const p = paramsFromUrl(url);
      if (p.s && p.t) setLinkParams(p);
    });
    return () => {
      alive = false;
      sub.remove();
    };
  }, []);

  const load = useCallback(async () => {
    if (!s || !t) {
      setError(
        "Missing share id or token. Open an onstream://watch?s=…&t=… link, or a /demo/watch/ URL."
      );
      setLoading(false);
      setPlaybackUrl(null);
      return;
    }
    setLoading(true);
    setError(null);
    setPlaybackUrl(null);
    try {
      const res = await exchangeShareLink(s, t);
      setPlaybackUrl(res.data.playback_url);
      setTitle(res.data.title);
      setExpiresAt(res.data.expires_at);
      setClipStart(res.data.clip_start || 0);
      setClipEnd(res.data.clip_end ?? null);
      setStoryboardVtt(res.data.storyboard_vtt_url || null);
      setStoryboardImg(res.data.storyboard_url || null);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : null;
      if (code === "SHARE_EXPIRED") setError("This share link has expired.");
      else if (code === "SHARE_REVOKED")
        setError("This share link was revoked.");
      else if (code === "SHARE_VIEW_LIMIT")
        setError("This share reached its view limit.");
      else if (code === "SHARE_NOT_FOUND")
        setError("Share link not found.");
      else
        setError(e instanceof Error ? e.message : "Could not open share.");
    } finally {
      setLoading(false);
    }
  }, [s, t]);

  useEffect(() => {
    void load();
  }, [load, retryTick]);

  return (
    <Screen>
      <Stack.Screen
        options={{
          headerShown: true,
          title: "Shared video",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
        }}
      />
      <View style={styles.body}>
        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator color={colors.brand} />
            <Text style={styles.loadingText}>Opening shared video…</Text>
          </View>
        ) : null}

        {!loading && error ? (
          <View style={styles.errBox}>
            <View style={styles.errIcon}>
              <Ionicons
                name={missing ? "link-outline" : "alert-circle"}
                size={28}
                color={colors.danger}
              />
            </View>
            <Text style={styles.errTitle}>
              {missing ? "No share link" : "Unavailable"}
            </Text>
            <Text style={styles.errBody}>{error}</Text>
            <View style={styles.errActions}>
              {!missing ? (
                <Button
                  label="Try again"
                  onPress={() => setRetryTick((n) => n + 1)}
                />
              ) : null}
              <Pressable
                onPress={() => {
                  if (router.canGoBack()) router.back();
                  else router.replace("/");
                }}
                style={({ pressed }) => [
                  styles.secondaryBtn,
                  pressed && { opacity: 0.8 },
                ]}
              >
                <Text style={styles.secondaryBtnText}>Back</Text>
              </Pressable>
            </View>
            <Text style={styles.hint}>
              App: onstream://watch?s=…&t=…{"\n"}
              Browser: /demo/watch/?s=…&t=…
            </Text>
          </View>
        ) : null}

        {!loading && !error ? (
          <>
            <Text style={styles.title}>{title}</Text>
            {expiresAt ? (
              <Text style={styles.meta}>
                Link expires {new Date(expiresAt).toLocaleString()}
              </Text>
            ) : null}
            <HlsPlayer
              ref={playerRef}
              uri={playbackUrl}
              title={title}
              initialPositionSeconds={clipStart}
              clipEndSeconds={clipEnd}
            />
            <StoryboardStrip
              vttUrl={storyboardVtt}
              imageUrl={storyboardImg}
              onSeek={(sec) => playerRef.current?.seekTo(sec)}
            />
            <Text style={styles.hint}>
              Shared playback — no account required for this screen.
            </Text>
          </>
        ) : null}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: {
    padding: spacing.lg,
    gap: 12,
    flex: 1,
  },
  center: {
    marginTop: 48,
    alignItems: "center",
    gap: 12,
  },
  loadingText: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
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
    marginTop: 24,
    gap: 10,
    alignItems: "flex-start",
  },
  errIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,107,107,0.12)",
    marginBottom: 4,
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
  errActions: {
    marginTop: 8,
    gap: 10,
    alignSelf: "stretch",
  },
  secondaryBtn: {
    alignItems: "center",
    paddingVertical: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
  },
  secondaryBtnText: {
    color: colors.text,
    fontFamily: "DMSans_700Bold",
    fontSize: 15,
  },
  hint: {
    marginTop: 8,
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    lineHeight: 18,
  },
});

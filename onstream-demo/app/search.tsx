import { Ionicons } from "@expo/vector-icons";
import { Stack, useRouter } from "expo-router";
import React, { useDeferredValue, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  searchCapabilities,
  searchVideos,
  type SearchCapabilities,
  type SearchResult,
} from "@/api/search";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { toast } from "@/lib/toast";
import { colors, radii, spacing } from "@/theme/tokens";

type Mode = "keyword" | "semantic";

function emptyCopy(mode: Mode, caps: SearchCapabilities | null, reason?: string | null) {
  if (mode === "semantic") {
    if (reason === "incompatible_index") {
      return "Index was built with a different embeddings model. Re-run captions/embeddings jobs.";
    }
    if (reason === "no_index" || (caps && caps.indexed_videos === 0)) {
      return "No transcripts indexed yet. Semantic search needs an embeddings job on READY videos.";
    }
    return "No semantic matches for this query.";
  }
  return "Try another title keyword. Search uses Postgres full-text ranking on your catalog.";
}

export default function SearchScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [q, setQ] = useState("");
  const deferredQ = useDeferredValue(q.trim());
  const [mode, setMode] = useState<Mode>("keyword");
  const [caps, setCaps] = useState<SearchCapabilities | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [reason, setReason] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void searchCapabilities()
      .then((res) => {
        if (!cancelled) setCaps(res.data);
      })
      .catch(() => {
        /* keyword search still works */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (deferredQ.length < 1) {
      setResults([]);
      setError(null);
      setReason(null);
      return;
    }
    let cancelled = false;
    const t = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await searchVideos(deferredQ, mode);
        if (!cancelled) {
          setResults(res.data.results || []);
          setReason(res.data.reason || null);
          setProvider(res.data.provider || null);
          if (res.data.semantic_available != null) {
            setCaps((prev) => ({
              semantic_available: res.data.semantic_available,
              provider: res.data.provider || prev?.provider || "mock",
              indexed_videos: res.data.indexed_videos ?? prev?.indexed_videos ?? 0,
              reason: res.data.reason,
            }));
          }
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Search failed");
          setResults([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 280);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [deferredQ, mode]);

  const selectMode = (next: Mode) => {
    if (next === "semantic" && caps && !caps.semantic_available) {
      toast.error("Semantic search is disabled on this engine.");
      return;
    }
    setMode(next);
  };

  return (
    <Screen>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={[styles.top, { paddingTop: insets.top + spacing.md }]}>
        <Pressable
          onPress={() => router.back()}
          hitSlop={12}
          style={styles.back}
        >
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </Pressable>
        <View style={styles.fieldWrap}>
          <Ionicons name="search" size={18} color={colors.textDim} />
          <TextInput
            autoFocus
            value={q}
            onChangeText={setQ}
            placeholder="Search your library"
            placeholderTextColor={colors.textDim}
            style={styles.input}
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="search"
          />
          {q ? (
            <Pressable onPress={() => setQ("")} hitSlop={8}>
              <Ionicons name="close-circle" size={18} color={colors.textDim} />
            </Pressable>
          ) : null}
        </View>
      </View>

      <View style={styles.modes}>
        {(["keyword", "semantic"] as const).map((id) => {
          const on = mode === id;
          const disabled = id === "semantic" && caps?.semantic_available === false;
          return (
            <Pressable
              key={id}
              accessibilityRole="button"
              accessibilityState={{ selected: on, disabled }}
              onPress={() => selectMode(id)}
              style={[styles.chip, on && styles.chipOn, disabled && { opacity: 0.45 }]}
            >
              <Text style={[styles.chipText, on && styles.chipTextOn]}>
                {id === "keyword" ? "Keyword" : "Semantic"}
              </Text>
            </Pressable>
          );
        })}
      </View>
      {mode === "semantic" && provider ? (
        <Text style={styles.provider}>
          {provider === "mock"
            ? "Lab embeddings (deterministic mock)"
            : `Provider · ${provider}`}
          {caps?.indexed_videos != null
            ? ` · ${caps.indexed_videos} indexed`
            : ""}
        </Text>
      ) : null}

      <ScrollView
        contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + 40 }]}
        keyboardShouldPersistTaps="handled"
      >
        {loading ? (
          <ActivityIndicator color={colors.brand} style={{ marginTop: 24 }} />
        ) : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {!loading && deferredQ && results.length === 0 && !error ? (
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>No matches</Text>
            <Text style={styles.emptyBody}>
              {emptyCopy(mode, caps, reason)}
            </Text>
          </View>
        ) : null}
        {results.map((item) => (
          <Pressable
            key={item.upload_id}
            onPress={() => router.push(`/video/${item.upload_id}`)}
            style={({ pressed }) => [styles.row, pressed && { opacity: 0.9 }]}
          >
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={styles.rowTitle} numberOfLines={1}>
                {item.title}
              </Text>
              <Text style={styles.rowMeta}>
                {item.upload_id}
                {item.score != null ? ` · rank ${item.score.toFixed(3)}` : ""}
              </Text>
            </View>
            <StatusPill status={item.status} />
          </Pressable>
        ))}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  top: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  back: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  fieldWrap: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.bgSoft,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.lg,
    paddingHorizontal: 14,
    height: 48,
  },
  input: {
    flex: 1,
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 16,
  },
  modes: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: spacing.lg,
    marginBottom: 6,
  },
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: radii.xl,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  chipOn: {
    borderColor: "rgba(46, 230, 166, 0.45)",
    backgroundColor: colors.brandSoft,
  },
  chipText: {
    color: colors.textMuted,
    fontFamily: "DMSans_700Bold",
    fontSize: 12,
    letterSpacing: 0.4,
  },
  chipTextOn: { color: colors.brand },
  provider: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 11,
    paddingHorizontal: spacing.lg,
    marginBottom: 8,
  },
  body: {
    paddingHorizontal: spacing.lg,
    gap: 10,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 14,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  rowTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 16,
  },
  rowMeta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  empty: { paddingTop: 40, gap: 8 },
  emptyTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 20,
  },
  emptyBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
    lineHeight: 20,
  },
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
    marginTop: 12,
  },
});

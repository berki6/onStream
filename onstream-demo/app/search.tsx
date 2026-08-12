import { Ionicons } from "@expo/vector-icons";
import { Stack, useRouter } from "expo-router";
import React, { useDeferredValue, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { searchVideos, type SearchResult } from "@/api/search";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { colors, radii, spacing } from "@/theme/tokens";

export default function SearchScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [q, setQ] = useState("");
  const deferredQ = useDeferredValue(q.trim());
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (deferredQ.length < 1) {
      setResults([]);
      setError(null);
      return;
    }
    let cancelled = false;
    const t = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await searchVideos(deferredQ, "keyword");
        if (!cancelled) setResults(res.data.results || []);
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
  }, [deferredQ]);

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

      <View style={styles.body}>
        {loading ? (
          <ActivityIndicator color={colors.brand} style={{ marginTop: 24 }} />
        ) : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {!loading && deferredQ && results.length === 0 && !error ? (
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>No matches</Text>
            <Text style={styles.emptyBody}>
              Try another title keyword. Search uses Postgres full-text ranking
              on your catalog.
            </Text>
          </View>
        ) : null}
        {results.map((item) => (
          <Pressable
            key={item.upload_id}
            onPress={() => router.push(`/video/${item.upload_id}`)}
            style={({ pressed }) => [
              styles.row,
              pressed && { opacity: 0.9 },
            ]}
          >
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={styles.rowTitle} numberOfLines={1}>
                {item.title}
              </Text>
              <Text style={styles.rowMeta}>
                {item.upload_id}
                {item.score != null
                  ? ` · rank ${item.score.toFixed(3)}`
                  : ""}
              </Text>
            </View>
            <StatusPill status={item.status} />
          </Pressable>
        ))}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  top: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
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
  body: {
    paddingHorizontal: spacing.lg,
    gap: 10,
    paddingBottom: 40,
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

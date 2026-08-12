import { Ionicons } from "@expo/vector-icons";
import { useRouter, type Href } from "expo-router";
import React from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import type { ContinueItem } from "@/api/watch";
import type { Video } from "@/api/videos";
import { colors, radii, spacing } from "@/theme/tokens";

function formatRemain(pos: number, dur?: number | null) {
  if (!dur || dur <= 0) return "";
  const left = Math.max(0, Math.round(dur - pos));
  const m = Math.floor(left / 60);
  const s = left % 60;
  return `${m}:${s.toString().padStart(2, "0")} left`;
}

type Props = {
  continueItems: ContinueItem[];
  savedItems: Video[];
};

function SectionHead({
  title,
  href,
}: {
  title: string;
  href: Href;
}) {
  const router = useRouter();
  return (
    <View style={styles.headRow}>
      <Text style={styles.heading}>{title}</Text>
      <Pressable
        hitSlop={8}
        onPress={() => router.push(href)}
        style={({ pressed }) => [styles.seeAll, pressed && { opacity: 0.75 }]}
      >
        <Text style={styles.seeAllText}>See all</Text>
        <Ionicons name="chevron-forward" size={14} color={colors.brand} />
      </Pressable>
    </View>
  );
}

/**
 * Horizontal shelves — only render when the shelf has items (no empty states).
 */
export function LibraryShelves({ continueItems, savedItems }: Props) {
  const router = useRouter();
  if (continueItems.length === 0 && savedItems.length === 0) return null;

  return (
    <View style={styles.wrap}>
      {continueItems.length > 0 ? (
        <View style={styles.section}>
          <SectionHead title="Continue watching" href={"/library/continue" as Href} />
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.row}
          >
            {continueItems.map((item) => (
              <Pressable
                key={item.upload_id}
                onPress={() =>
                  router.push(`/video/${item.upload_id}?play=1` as Href)
                }
                style={({ pressed }) => [
                  styles.tile,
                  pressed && { opacity: 0.88 },
                ]}
              >
                <View style={styles.poster}>
                  <Ionicons name="play" size={28} color={colors.brand} />
                  <View style={styles.progressTrack}>
                    <View
                      style={[
                        styles.progressFill,
                        {
                          width: `${Math.round(
                            Math.min(1, item.progress_ratio) * 100
                          )}%`,
                        },
                      ]}
                    />
                  </View>
                </View>
                <Text style={styles.tileTitle} numberOfLines={2}>
                  {item.title}
                </Text>
                <Text style={styles.tileMeta}>
                  {formatRemain(item.position_seconds, item.duration_seconds) ||
                    "Resume"}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      ) : null}

      {savedItems.length > 0 ? (
        <View style={styles.section}>
          <SectionHead title="Saved" href={"/library/saved" as Href} />
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.row}
          >
            {savedItems.map((item) => (
              <Pressable
                key={item.upload_id}
                onPress={() => router.push(`/video/${item.upload_id}`)}
                style={({ pressed }) => [
                  styles.tile,
                  pressed && { opacity: 0.88 },
                ]}
              >
                <View style={[styles.poster, styles.savedPoster]}>
                  <Ionicons name="heart" size={26} color={colors.live} />
                </View>
                <Text style={styles.tileTitle} numberOfLines={2}>
                  {item.title}
                </Text>
                <Text style={styles.tileMeta}>Saved</Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing.lg,
    marginBottom: spacing.md,
  },
  section: { gap: spacing.sm },
  headRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 2,
  },
  heading: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
    letterSpacing: -0.3,
  },
  seeAll: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
  },
  seeAllText: {
    color: colors.brand,
    fontFamily: "DMSans_700Bold",
    fontSize: 13,
  },
  row: {
    gap: 12,
    paddingRight: spacing.md,
  },
  tile: {
    width: 148,
    gap: 6,
  },
  poster: {
    height: 84,
    borderRadius: radii.md,
    backgroundColor: colors.bgSoft,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  savedPoster: {
    backgroundColor: "rgba(255,77,106,0.08)",
    borderColor: "rgba(255,77,106,0.25)",
  },
  progressTrack: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 3,
    backgroundColor: "rgba(255,255,255,0.12)",
  },
  progressFill: {
    height: "100%",
    backgroundColor: colors.brand,
  },
  tileTitle: {
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
    lineHeight: 17,
  },
  tileMeta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 11,
  },
});

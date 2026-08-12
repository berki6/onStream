import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors, radii } from "../theme/tokens";

const MAP: Record<string, string> = {
  READY: colors.ready,
  PROCESSING: colors.processing,
  PENDING: colors.processing,
  LIVE: colors.live,
  IDLE: colors.textMuted,
  ENDED: colors.textDim,
  ERROR: colors.error,
  DELETED: colors.textDim,
  QUARANTINED: colors.warning,
  // webhook delivery
  SUCCESS: colors.ready,
  FAILED: colors.error,
};

export function StatusPill({ status }: { status: string }) {
  const tone = MAP[status?.toUpperCase()] || colors.textMuted;
  return (
    <View style={[styles.pill, { borderColor: tone }]}>
      <View style={[styles.dot, { backgroundColor: tone }]} />
      <Text style={[styles.text, { color: tone }]}>{status}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radii.xl,
    borderWidth: 1,
    backgroundColor: "rgba(0,0,0,0.25)",
  },
  dot: { width: 6, height: 6, borderRadius: 99 },
  text: {
    fontFamily: "DMSans_700Bold",
    fontSize: 11,
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
});

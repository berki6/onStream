import * as Clipboard from "expo-clipboard";
import * as Haptics from "expo-haptics";
import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radii } from "../theme/tokens";

export function CopyRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <Pressable
      onPress={async () => {
        await Clipboard.setStringAsync(value);
        setCopied(true);
        try {
          await Haptics.notificationAsync(
            Haptics.NotificationFeedbackType.Success
          );
        } catch {
          /* ignore */
        }
        setTimeout(() => setCopied(false), 1400);
      }}
      style={styles.row}
    >
      <View style={styles.meta}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.value} numberOfLines={2}>
          {value}
        </Text>
      </View>
      <Text style={styles.action}>{copied ? "Copied" : "Copy"}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    gap: 12,
    alignItems: "center",
    padding: 14,
    borderRadius: radii.md,
    backgroundColor: colors.bgSoft,
    borderWidth: 1,
    borderColor: colors.line,
  },
  meta: { flex: 1, gap: 4 },
  label: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  value: {
    color: colors.text,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
    lineHeight: 18,
  },
  action: {
    color: colors.brand,
    fontFamily: "DMSans_700Bold",
    fontSize: 12,
  },
});

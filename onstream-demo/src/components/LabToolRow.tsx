import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import React, { type ComponentProps } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radii, spacing } from "@/theme/tokens";

type IconName = ComponentProps<typeof Ionicons>["name"];

type Props = {
  icon: IconName;
  title: string;
  subtitle: string;
  onPress: () => void | Promise<void>;
  trailing?: "chevron" | "open";
  tone?: "brand" | "warn" | "danger";
};

const TONE = {
  brand: { icon: colors.brand, well: colors.brandSoft },
  warn: { icon: colors.warning, well: "rgba(240,194,75,0.14)" },
  danger: { icon: colors.danger, well: "rgba(255,107,107,0.14)" },
} as const;

/** Cinema-style lab tool row with icon well + press scale. */
export function LabToolRow({
  icon,
  title,
  subtitle,
  onPress,
  trailing = "chevron",
  tone = "brand",
}: Props) {
  const t = TONE[tone];
  return (
    <Pressable
      accessibilityRole="button"
      onPress={async () => {
        try {
          await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        } catch {
          /* noop */
        }
        await onPress();
      }}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <View style={[styles.well, { backgroundColor: t.well }]}>
        <Ionicons name={icon} size={20} color={t.icon} />
      </View>
      <View style={styles.copy}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.sub} numberOfLines={2}>
          {subtitle}
        </Text>
      </View>
      <Ionicons
        name={trailing === "open" ? "open-outline" : "chevron-forward"}
        size={18}
        color={colors.textDim}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  pressed: { opacity: 0.9, transform: [{ scale: 0.985 }] },
  well: {
    width: 44,
    height: 44,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  copy: { flex: 1, gap: 2 },
  title: {
    color: colors.text,
    fontFamily: "DMSans_700Bold",
    fontSize: 15,
  },
  sub: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    lineHeight: 16,
  },
});

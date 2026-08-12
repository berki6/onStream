import * as Haptics from "expo-haptics";
import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  ViewStyle,
} from "react-native";

import { colors, radii } from "../theme/tokens";

type Props = {
  label: string;
  onPress: () => void | Promise<void>;
  variant?: "primary" | "ghost" | "danger";
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
};

export function Button({
  label,
  onPress,
  variant = "primary",
  loading,
  disabled,
  style,
}: Props) {
  const isDisabled = disabled || loading;

  return (
    <Pressable
      accessibilityRole="button"
      disabled={isDisabled}
      onPress={async () => {
        try {
          await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        } catch {
          /* web / unsupported */
        }
        await onPress();
      }}
      style={({ pressed }) => [
        styles.base,
        variant === "primary" && styles.primary,
        variant === "ghost" && styles.ghost,
        variant === "danger" && styles.danger,
        pressed && !isDisabled && styles.pressed,
        isDisabled && styles.disabled,
        style,
      ]}
    >
      {loading ? (
        <>
          <ActivityIndicator
            color={variant === "ghost" ? colors.brand : colors.bg}
          />
          {label ? (
            <Text
              style={[
                styles.label,
                styles.loadingLabel,
                variant === "ghost" && styles.ghostLabel,
                variant === "danger" && styles.dangerLabel,
              ]}
              numberOfLines={1}
            >
              {label}
            </Text>
          ) : null}
        </>
      ) : (
        <Text
          style={[
            styles.label,
            variant === "ghost" && styles.ghostLabel,
            variant === "danger" && styles.dangerLabel,
          ]}
        >
          {label}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 52,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 18,
    flexDirection: "row",
    gap: 8,
  },
  primary: {
    backgroundColor: colors.brand,
  },
  ghost: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: colors.line,
  },
  danger: {
    backgroundColor: "rgba(255, 107, 107, 0.16)",
    borderWidth: 1,
    borderColor: "rgba(255, 107, 107, 0.45)",
  },
  pressed: { opacity: 0.88, transform: [{ scale: 0.985 }] },
  disabled: { opacity: 0.45 },
  label: {
    color: colors.bg,
    fontFamily: "DMSans_700Bold",
    fontSize: 16,
    letterSpacing: 0.2,
  },
  loadingLabel: {
    fontSize: 14,
  },
  ghostLabel: { color: colors.text },
  dangerLabel: { color: colors.danger },
});

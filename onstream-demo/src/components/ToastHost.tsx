import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import React, { useEffect, useRef, useState, useSyncExternalStore } from "react";
import {
  AccessibilityInfo,
  Pressable,
  StyleSheet,
  Text,
} from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  dismissToast,
  getToast,
  subscribeToast,
  type ToastMessage,
  type ToastTone,
} from "@/lib/toast";
import { colors, radii } from "@/theme/tokens";

const ICONS: Record<ToastTone, keyof typeof Ionicons.glyphMap> = {
  success: "checkmark-circle",
  error: "alert-circle",
  info: "information-circle",
};

async function ping(tone: ToastTone) {
  try {
    if (tone === "error") {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      return;
    }
    if (tone === "success") {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      return;
    }
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  } catch {
    /* haptics unavailable */
  }
}

/**
 * YouTube-style snackbar over the whole app (above sheets).
 * One toast at a time; a new call replaces the previous.
 */
export function ToastHost() {
  const insets = useSafeAreaInsets();
  const toast = useSyncExternalStore(subscribeToast, getToast, getToast);
  const [display, setDisplay] = useState<ToastMessage | null>(null);
  const opacity = useSharedValue(0);
  const translateY = useSharedValue(16);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (hideTimer.current) {
      clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
    if (unmountTimer.current) {
      clearTimeout(unmountTimer.current);
      unmountTimer.current = null;
    }
    if (!toast) {
      opacity.value = withTiming(0, { duration: 180 });
      translateY.value = withTiming(12, { duration: 180 });
      unmountTimer.current = setTimeout(() => setDisplay(null), 200);
      return;
    }
    setDisplay(toast);
    opacity.value = withTiming(1, {
      duration: 200,
      easing: Easing.out(Easing.cubic),
    });
    translateY.value = withTiming(0, {
      duration: 200,
      easing: Easing.out(Easing.cubic),
    });
    try {
      AccessibilityInfo.announceForAccessibility(toast.text);
    } catch {
      /* ignore */
    }
    void ping(toast.tone);
    hideTimer.current = setTimeout(() => dismissToast(), toast.durationMs);
    return () => {
      if (hideTimer.current) clearTimeout(hideTimer.current);
      if (unmountTimer.current) clearTimeout(unmountTimer.current);
    };
  }, [toast, opacity, translateY]);

  const slide = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }],
  }));

  if (!display) return null;

  const tone = display.tone;
  const iconColor =
    tone === "success"
      ? colors.brand
      : tone === "error"
        ? colors.danger
        : colors.text;

  return (
    <Animated.View
      pointerEvents="box-none"
      style={[
        styles.wrap,
        { bottom: Math.max(insets.bottom, 12) + 16 },
        slide,
      ]}
    >
      <Pressable
        accessibilityRole="alert"
        accessibilityLiveRegion="polite"
        onPress={() => dismissToast()}
        style={[
          styles.card,
          tone === "success" && styles.cardOk,
          tone === "error" && styles.cardBad,
        ]}
      >
        <Ionicons name={ICONS[tone]} size={18} color={iconColor} />
        <Text style={styles.text} numberOfLines={3}>
          {display.text}
        </Text>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: 16,
    right: 16,
    zIndex: 1200,
    elevation: 1200,
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: radii.md,
    backgroundColor: colors.bgElevated,
    borderWidth: 1,
    borderColor: colors.line,
  },
  cardOk: {
    borderColor: "rgba(46, 230, 166, 0.35)",
    backgroundColor: "#0F2E24",
  },
  cardBad: {
    borderColor: "rgba(255, 107, 107, 0.4)",
    backgroundColor: "#3A1418",
  },
  text: {
    flex: 1,
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
    lineHeight: 19,
  },
});

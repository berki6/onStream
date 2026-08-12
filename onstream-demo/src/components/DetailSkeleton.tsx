import { LinearGradient } from "expo-linear-gradient";
import React, { useEffect } from "react";
import { StyleSheet, View, type DimensionValue, type ViewStyle } from "react-native";
import Animated, {
  Easing,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";

import { colors, radii, spacing } from "@/theme/tokens";

type BoneProps = {
  height: number;
  width?: DimensionValue;
  radius?: number | "round";
  style?: ViewStyle;
};

/**
 * Lightweight shimmer bone — Moti's `moti/skeleton` entry is broken under
 * Metro/Expo 54 (missing resolve for `./skeleton-new`), so we own this locally
 * with Reanimated + expo-linear-gradient we already ship.
 */
function Bone({ height, width = "100%", radius = radii.md, style }: BoneProps) {
  const t = useSharedValue(0);

  useEffect(() => {
    t.value = withRepeat(
      withTiming(1, { duration: 1200, easing: Easing.inOut(Easing.quad) }),
      -1,
      true
    );
  }, [t]);

  const shimmerStyle = useAnimatedStyle(() => ({
    opacity: interpolate(t.value, [0, 1], [0.35, 0.85]),
    transform: [{ translateX: interpolate(t.value, [0, 1], [-40, 40]) }],
  }));

  const borderRadius = radius === "round" ? 999 : radius;

  return (
    <View style={[{ height, width, borderRadius, overflow: "hidden" }, styles.bone, style]}>
      <Animated.View style={[StyleSheet.absoluteFill, shimmerStyle]}>
        <LinearGradient
          colors={[
            "rgba(46,230,166,0.02)",
            "rgba(46,230,166,0.12)",
            "rgba(46,230,166,0.02)",
          ]}
          start={{ x: 0, y: 0.5 }}
          end={{ x: 1, y: 0.5 }}
          style={StyleSheet.absoluteFill}
        />
      </Animated.View>
    </View>
  );
}

type Props = {
  variant?: "video" | "live";
};

/** Cold-open placeholder mirroring detail chrome. */
export function DetailSkeleton({ variant = "video" }: Props) {
  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        <Bone height={28} width={88} radius="round" />
        <Bone height={14} width="42%" radius={6} />
      </View>
      <Bone height={52} />
      {variant === "video" ? (
        <Bone height={48} />
      ) : (
        <Bone height={36} width="70%" />
      )}
      <Bone height={200} radius={radii.lg} />
      <View style={styles.gap} />
      <Bone height={48} />
      <Bone height={48} />
      <Bone height={48} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    padding: spacing.lg,
    gap: 14,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  gap: { height: 4 },
  bone: {
    backgroundColor: colors.bgSoft,
    borderWidth: 1,
    borderColor: colors.line,
  },
});

import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { StyleSheet, View } from "react-native";

import { colors, radii } from "@/theme/tokens";

type Size = "sm" | "md" | "lg";

const SPEC: Record<
  Size,
  { box: number; icon: number; offset: number; radius: number; badge: number }
> = {
  sm: { box: 52, icon: 20, offset: 3, radius: 10, badge: 16 },
  md: { box: 84, icon: 28, offset: 5, radius: 14, badge: 20 },
  lg: { box: 128, icon: 40, offset: 8, radius: 20, badge: 24 },
};

/**
 * Stacked-cover placeholder — YouTube / Spotify playlist artwork
 * without needing real thumbnails on the list payload.
 */
export function PlaylistArt({
  size = "sm",
  isPublic = false,
}: {
  size?: Size;
  isPublic?: boolean;
}) {
  const s = SPEC[size];
  const pad = s.offset * 2;
  return (
    <View style={{ width: s.box + pad, height: s.box + pad }}>
      <View
        style={[
          styles.layer,
          {
            width: s.box,
            height: s.box,
            borderRadius: s.radius,
            top: 0,
            left: pad,
            opacity: 0.35,
            backgroundColor: colors.bgSoft,
          },
        ]}
      />
      <View
        style={[
          styles.layer,
          {
            width: s.box,
            height: s.box,
            borderRadius: s.radius,
            top: s.offset,
            left: s.offset,
            opacity: 0.65,
            backgroundColor: colors.bgElevated,
          },
        ]}
      />
      <View
        style={[
          styles.layer,
          styles.front,
          {
            width: s.box,
            height: s.box,
            borderRadius: s.radius,
            top: pad,
            left: 0,
          },
        ]}
      >
        <Ionicons name="albums" size={s.icon} color={colors.brand} />
        <View
          style={[
            styles.badge,
            {
              width: s.badge,
              height: s.badge,
              borderRadius: s.badge / 2,
            },
          ]}
        >
          <Ionicons
            name={isPublic ? "globe-outline" : "lock-closed"}
            size={size === "lg" ? 12 : 9}
            color={isPublic ? colors.brand : colors.textMuted}
          />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  layer: {
    position: "absolute",
    borderWidth: 1,
    borderColor: colors.line,
  },
  front: {
    backgroundColor: colors.brandSoft,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  badge: {
    position: "absolute",
    right: 4,
    bottom: 4,
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
  },
});

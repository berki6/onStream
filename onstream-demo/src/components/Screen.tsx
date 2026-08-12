import { LinearGradient } from "expo-linear-gradient";
import React from "react";
import { StyleSheet, View, ViewProps } from "react-native";

import { colors } from "../theme/tokens";

export function Screen({ children, style, ...rest }: ViewProps) {
  return (
    <View style={[styles.root, style]} {...rest}>
      <LinearGradient
        colors={["#0F1C18", "#0B1210", "#0A1014"]}
        start={{ x: 0.1, y: 0 }}
        end={{ x: 0.9, y: 1 }}
        style={StyleSheet.absoluteFill}
      />
      <View pointerEvents="none" style={styles.glow} />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  glow: {
    position: "absolute",
    top: -80,
    right: -40,
    width: 220,
    height: 220,
    borderRadius: 220,
    backgroundColor: "rgba(46, 230, 166, 0.08)",
  },
});

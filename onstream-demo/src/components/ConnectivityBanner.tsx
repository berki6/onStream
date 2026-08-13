import { Ionicons } from "@expo/vector-icons";
import NetInfo from "@react-native-community/netinfo";
import { onlineManager } from "@tanstack/react-query";
import React, { useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  setDeviceOnline,
  useConnectivity,
} from "@/lib/connectivity";
import { colors } from "@/theme/tokens";

function applyDeviceOnline(online: boolean) {
  setDeviceOnline(online);
  onlineManager.setOnline(online);
}

/**
 * YouTube-style connectivity strip: red while down, green flash when restored.
 * Wired to NetInfo + TanStack Query so lists refetch when the radio comes back.
 */
export function ConnectivityHost() {
  useEffect(() => {
    const unsub = NetInfo.addEventListener((state) => {
      applyDeviceOnline(state.isConnected !== false);
    });
    void NetInfo.fetch().then((state) => {
      applyDeviceOnline(state.isConnected !== false);
    });
    return () => unsub();
  }, []);

  return <ConnectivityBanner />;
}

function ConnectivityBanner() {
  const insets = useSafeAreaInsets();
  const { deviceOnline, apiReachable } = useConnectivity();
  const [restored, setRestored] = useState(false);
  const prevOnline = useRef(deviceOnline);

  useEffect(() => {
    if (!prevOnline.current && deviceOnline) {
      setRestored(true);
      const t = setTimeout(() => setRestored(false), 2400);
      prevOnline.current = true;
      return () => clearTimeout(t);
    }
    prevOnline.current = deviceOnline;
    if (!deviceOnline) setRestored(false);
  }, [deviceOnline]);

  const offline = !deviceOnline;
  const unreachable = deviceOnline && apiReachable === false && !restored;

  if (!offline && !unreachable && !restored) return null;

  const ok = restored;
  const label = ok
    ? "Back online"
    : offline
      ? "No internet connection"
      : "Can't reach OnStream";
  const icon = ok
    ? "wifi"
    : offline
      ? "cloud-offline-outline"
      : "alert-circle-outline";

  return (
    <View
      pointerEvents="none"
      style={[
        styles.wrap,
        { paddingTop: Math.max(insets.top, 8) },
        ok ? styles.ok : styles.bad,
      ]}
    >
      <View style={styles.row}>
        <Ionicons name={icon} size={16} color={ok ? colors.brand : "#FFD2D2"} />
        <Text style={[styles.label, ok ? styles.labelOk : styles.labelBad]}>
          {label}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 1100,
    elevation: 1100,
    paddingBottom: 8,
    paddingHorizontal: 16,
  },
  ok: {
    backgroundColor: "#0F2E24",
  },
  bad: {
    backgroundColor: "#3A1418",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    minHeight: 28,
  },
  label: {
    fontFamily: "DMSans_700Bold",
    fontSize: 13,
  },
  labelOk: {
    color: colors.brand,
  },
  labelBad: {
    color: "#FFD2D2",
  },
});

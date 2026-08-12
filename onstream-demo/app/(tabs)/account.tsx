import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import * as Linking from "expo-linking";
import { useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { getApiBase, pingHealthLabel, setApiBase } from "@/api/client";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { useAuth } from "@/context/AuthContext";
import { colors, radii, spacing } from "@/theme/tokens";

export default function AccountScreen() {
  const insets = useSafeAreaInsets();
  const { username, signOut } = useAuth();
  const [apiBase, setApiBaseLocal] = useState(getApiBase());
  const [health, setHealth] = useState<string>("—");
  const [saved, setSaved] = useState(false);
  const [healthBusy, setHealthBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);

  useFocusEffect(
    useCallback(() => {
      setApiBaseLocal(getApiBase());
      setSaved(false);
    }, [])
  );

  return (
    <Screen>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <View style={{ flex: 1 }}>
          <Text style={styles.kicker}>Account</Text>
          <Text
            style={styles.title}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.75}
          >
            You
          </Text>
        </View>
      </View>

      <FormScroll
        contentContainerStyle={[
          styles.content,
          { paddingBottom: insets.bottom + 40 },
        ]}
      >
        <Text style={styles.body}>
          Session and engine connection for this device.
        </Text>

        <View style={styles.profile}>
          <View style={styles.avatar}>
            <Ionicons name="person" size={28} color={colors.brand} />
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.profileLabel}>Signed in</Text>
            <Text style={styles.profileName} numberOfLines={1}>
              {username || "—"}
            </Text>
          </View>
        </View>

        <View style={styles.block}>
          <View style={styles.sectionRow}>
            <Text style={styles.section}>Connection</Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Check API health"
              disabled={healthBusy}
              onPress={async () => {
                setHealthBusy(true);
                try {
                  await setApiBase(apiBase);
                  setHealth(await pingHealthLabel());
                } finally {
                  setHealthBusy(false);
                }
              }}
              style={({ pressed }) => [
                styles.iconBtn,
                pressed && !healthBusy && { opacity: 0.85 },
                healthBusy && { opacity: 0.5 },
              ]}
            >
              {healthBusy ? (
                <ActivityIndicator color={colors.brand} size="small" />
              ) : (
                <Ionicons name="pulse-outline" size={22} color={colors.text} />
              )}
            </Pressable>
          </View>
          <View style={styles.urlRow}>
            <View style={styles.urlField}>
              <Field
                label="API base URL"
                value={apiBase}
                onChangeText={(v) => {
                  setApiBaseLocal(v);
                  setSaved(false);
                }}
                autoCapitalize="none"
                autoCorrect={false}
                hint="Use your LAN IP for a physical phone (Expo Go)."
              />
            </View>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={saved ? "API URL saved" : "Save API URL"}
              disabled={saveBusy}
              onPress={async () => {
                setSaveBusy(true);
                try {
                  await setApiBase(apiBase);
                  setSaved(true);
                  try {
                    await Haptics.notificationAsync(
                      Haptics.NotificationFeedbackType.Success
                    );
                  } catch {
                    /* noop */
                  }
                } finally {
                  setSaveBusy(false);
                }
              }}
              style={({ pressed }) => [
                styles.saveBeside,
                pressed && !saveBusy && { opacity: 0.85 },
                saveBusy && { opacity: 0.5 },
              ]}
            >
              {saveBusy ? (
                <ActivityIndicator color={colors.brand} size="small" />
              ) : (
                <Ionicons
                  name={saved ? "checkmark-circle" : "save-outline"}
                  size={22}
                  color={saved ? colors.brand : colors.text}
                />
              )}
            </Pressable>
          </View>
          <Text style={styles.mono}>{health}</Text>

          <Pressable
            onPress={async () => {
              await Linking.openURL(`${getApiBase()}/scalar`);
            }}
            style={({ pressed }) => [
              styles.linkRow,
              pressed && styles.linkPressed,
            ]}
          >
            <View style={styles.iconWell}>
              <Ionicons name="book-outline" size={18} color={colors.brand} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.linkTitle}>Scalar API docs</Text>
              <Text style={styles.linkSub}>Open interactive reference</Text>
            </View>
            <Ionicons name="open-outline" size={16} color={colors.textDim} />
          </Pressable>
        </View>

        <Button label="Sign out" variant="danger" onPress={signOut} />
      </FormScroll>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  iconBtn: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  kicker: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  title: {
    color: colors.brand,
    fontFamily: "Syne_800ExtraBold",
    fontSize: 32,
    letterSpacing: -0.8,
  },
  content: {
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
  },
  body: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
  },
  profile: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    padding: 14,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    marginTop: 4,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandSoft,
  },
  profileLabel: {
    color: colors.textDim,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
  },
  profileName: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
  },
  block: { gap: 12, marginTop: 8 },
  sectionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  section: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
    flex: 1,
  },
  urlRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  urlField: {
    flex: 1,
    minWidth: 0,
  },
  saveBeside: {
    width: 44,
    height: 52,
    marginTop: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  mono: {
    color: colors.brandDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  linkPressed: { opacity: 0.88, transform: [{ scale: 0.985 }] },
  iconWell: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandSoft,
  },
  linkTitle: {
    color: colors.text,
    fontFamily: "DMSans_700Bold",
    fontSize: 14,
  },
  linkSub: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    marginTop: 1,
  },
});

import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import * as Linking from "expo-linking";
import { useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
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

  useFocusEffect(
    useCallback(() => {
      setApiBaseLocal(getApiBase());
      setSaved(false);
    }, [])
  );

  return (
    <Screen>
      <FormScroll
        contentContainerStyle={[
          styles.content,
          {
            paddingTop: insets.top + spacing.lg,
            paddingBottom: insets.bottom + 40,
          },
        ]}
      >
        <Text style={styles.kicker}>Account</Text>
        <Text
          style={styles.title}
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.75}
        >
          You
        </Text>
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
          <Text style={styles.section}>Connection</Text>
          <Field
            label="API base URL"
            value={apiBase}
            onChangeText={(v) => {
              setApiBaseLocal(v);
              setSaved(false);
            }}
            autoCapitalize="none"
            hint="Use your LAN IP for a physical phone (Expo Go)."
          />
          <Button
            label={saved ? "Saved" : "Save API URL"}
            onPress={async () => {
              await setApiBase(apiBase);
              setSaved(true);
              try {
                await Haptics.notificationAsync(
                  Haptics.NotificationFeedbackType.Success
                );
              } catch {
                /* noop */
              }
            }}
          />
          <Button
            label="Check /health"
            variant="ghost"
            onPress={async () => {
              await setApiBase(apiBase);
              setHealth(await pingHealthLabel());
            }}
          />
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
  content: {
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
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
    fontSize: 40,
    letterSpacing: -1,
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
  section: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
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

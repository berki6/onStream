import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { checkHealth, getApiBase, setApiBase } from "@/api/client";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing } from "@/theme/tokens";

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();
  const { username, signOut } = useAuth();
  const [apiBase, setApiBaseLocal] = useState(getApiBase());
  const [health, setHealth] = useState<string>("—");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setApiBaseLocal(getApiBase());
  }, []);

  return (
    <Screen>
      <FormScroll
        contentContainerStyle={[
          styles.content,
          { paddingTop: insets.top + spacing.lg, paddingBottom: insets.bottom + 32 },
        ]}
      >
        <Text style={styles.kicker}>Lab</Text>
        <Text
          style={styles.title}
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.75}
        >
          OnStream
        </Text>
        <Text style={styles.body}>
          Signed in as {username || "—"}. Point this demo at your engine, then
          exercise VOD upload, signed HLS, live create, and health.
        </Text>

        <View style={styles.block}>
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
            }}
          />
          <Button
            label="Check /health"
            variant="ghost"
            onPress={async () => {
              await setApiBase(apiBase);
              const h = await checkHealth();
              setHealth(h ? JSON.stringify(h) : "unreachable");
            }}
          />
          <Text style={styles.mono}>{health}</Text>
        </View>

        <View style={styles.block}>
          <Text style={styles.section}>How to run</Text>
          <Text style={styles.body}>
            1. Start API on your machine{"\n"}
            2. Set API URL to http://&lt;LAN-IP&gt;:8000{"\n"}
            3. Scan Expo Go QR from `npm start`{"\n"}
            4. Upload / create live / play HLS
          </Text>
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
});

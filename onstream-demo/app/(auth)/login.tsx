import { Link } from "expo-router";
import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError, getApiBase, pingHealthLabel, setApiBase } from "@/api/client";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing } from "@/theme/tokens";

export default function LoginScreen() {
  const insets = useSafeAreaInsets();
  const { signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [apiBase, setApiBaseLocal] = useState(getApiBase());
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <Screen>
      <FormScroll
        contentContainerStyle={[
          styles.content,
          { paddingTop: insets.top + spacing.xl, paddingBottom: insets.bottom + 24 },
        ]}
      >
        <View style={styles.hero}>
          <Text
            style={styles.brand}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.75}
          >
            OnStream
          </Text>
          <Text style={styles.tag}>Demo lab for VOD, live HLS, and tokens</Text>
        </View>

        <View style={styles.form}>
          <Field
            label="API base URL"
            value={apiBase}
            onChangeText={setApiBaseLocal}
            autoCapitalize="none"
            autoCorrect={false}
            hint="Phone must reach your PC IP, not localhost (e.g. http://192.168.x.x:8000)"
          />
          <Field
            label="Username"
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <Field
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}
          {health ? <Text style={styles.health}>{health}</Text> : null}

          <Button
            label="Sign in"
            loading={loading}
            onPress={async () => {
              setLoading(true);
              setError(null);
              try {
                await setApiBase(apiBase);
                await signIn(username.trim(), password);
              } catch (e) {
                setError(e instanceof ApiError ? e.message : "Sign in failed");
              } finally {
                setLoading(false);
              }
            }}
          />

          <Button
            label="Ping API health"
            variant="ghost"
            onPress={async () => {
              await setApiBase(apiBase);
              setHealth(await pingHealthLabel());
            }}
          />

          <Link href={"/(auth)/forgot" as import("expo-router").Href} style={styles.link}>
            Forgot password?
          </Link>
          <Link href="/(auth)/register" style={styles.link}>
            Create an account
          </Link>
        </View>
      </FormScroll>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: spacing.lg,
    gap: spacing.xl,
  },
  hero: { gap: 10 },
  brand: {
    color: colors.brand,
    fontFamily: "Syne_800ExtraBold",
    fontSize: 40,
    letterSpacing: -1,
  },
  tag: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 16,
    lineHeight: 24,
    maxWidth: 320,
  },
  form: { gap: 14 },
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
  },
  health: {
    color: colors.brandDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  link: {
    color: colors.text,
    textAlign: "center",
    fontFamily: "DMSans_500Medium",
    fontSize: 15,
    marginTop: 8,
  },
});

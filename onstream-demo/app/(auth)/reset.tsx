import { Link, useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError } from "@/api/client";
import { confirmPasswordReset } from "@/api/auth";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { colors, spacing } from "@/theme/tokens";

function firstParam(v: string | string[] | undefined): string {
  if (Array.isArray(v)) return v[0] || "";
  return v || "";
}

export default function ResetPasswordScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const params = useLocalSearchParams<{ token?: string | string[] }>();
  const linkToken = useMemo(() => firstParam(params.token), [params.token]);

  const [token, setToken] = useState(linkToken);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (linkToken) setToken(linkToken);
  }, [linkToken]);

  return (
    <Screen>
      <FormScroll
        contentContainerStyle={[
          styles.content,
          {
            paddingTop: insets.top + spacing.xl,
            paddingBottom: insets.bottom + 24,
          },
        ]}
      >
        <View style={styles.hero}>
          <Text style={styles.brand}>Choose a new password</Text>
          <Text style={styles.tag}>
            Paste the token from email / API logs, or open the deep link
            onstream://reset?token=…
          </Text>
        </View>

        <View style={styles.form}>
          <Field
            label="Reset token"
            value={token}
            onChangeText={setToken}
            autoCapitalize="none"
            autoCorrect={false}
            multiline
          />
          <Field
            label="New password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
          <Field
            label="Confirm password"
            value={confirm}
            onChangeText={setConfirm}
            secureTextEntry
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}
          {ok ? (
            <Text style={styles.ok}>Password updated. You can sign in.</Text>
          ) : null}

          <Button
            label="Update password"
            loading={loading}
            onPress={async () => {
              setError(null);
              if (password.length < 8) {
                setError("Password must be at least 8 characters");
                return;
              }
              if (password !== confirm) {
                setError("Passwords do not match");
                return;
              }
              if (!token.trim()) {
                setError("Reset token is required");
                return;
              }
              setLoading(true);
              try {
                await confirmPasswordReset(token.trim(), password);
                setOk(true);
                setTimeout(() => router.replace("/(auth)/login"), 800);
              } catch (e) {
                setError(
                  e instanceof ApiError ? e.message : "Reset failed"
                );
              } finally {
                setLoading(false);
              }
            }}
          />

          <Link href="/(auth)/login" style={styles.link}>
            Back to sign in
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
    fontSize: 28,
    letterSpacing: -1,
  },
  tag: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
  },
  form: { gap: 14 },
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
  },
  ok: {
    color: colors.ready,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
  },
  link: {
    color: colors.text,
    textAlign: "center",
    fontFamily: "DMSans_500Medium",
    fontSize: 15,
    marginTop: 8,
  },
});

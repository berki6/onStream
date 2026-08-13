import { Link, useRouter, type Href } from "expo-router";
import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError } from "@/api/client";
import { requestPasswordReset } from "@/api/auth";
import { toast } from "@/lib/toast";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { colors, spacing } from "@/theme/tokens";

/**
 * Request a reset email. Local/lab: EMAIL_PROVIDER=log → token in API logs;
 * non-prod API also returns reset_token so Expo can jump straight to confirm.
 */
export default function ForgotPasswordScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
          <Text style={styles.brand}>Reset password</Text>
          <Text style={styles.tag}>
            We email a link (and log it when EMAIL_PROVIDER=log). In non-prod the
            token is also returned so you can continue here without SMTP.
          </Text>
        </View>

        <View style={styles.form}>
          <Field
            label="Account email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
          />
          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Button
            label="Send reset"
            loading={loading}
            onPress={async () => {
              setLoading(true);
              setError(null);
              try {
                const res = await requestPasswordReset(email.trim());
                const token = res.data?.reset_token;
                if (token) {
                  router.push(
                    `/(auth)/reset?token=${encodeURIComponent(token)}` as Href
                  );
                  return;
                }
                toast.info(
                  "If that email exists, a reset was sent. Check SMTP inbox or API logs (EMAIL_PROVIDER=log)."
                );
              } catch (e) {
                setError(
                  e instanceof ApiError ? e.message : "Request failed"
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
    fontSize: 32,
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
  link: {
    color: colors.text,
    textAlign: "center",
    fontFamily: "DMSans_500Medium",
    fontSize: 15,
    marginTop: 8,
  },
});

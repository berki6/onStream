import { Link } from "expo-router";
import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { userFacingError } from "@/api/client";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing } from "@/theme/tokens";

export default function RegisterScreen() {
  const insets = useSafeAreaInsets();
  const { signUp } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
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
          <Text style={styles.brand}>Join</Text>
          <Text style={styles.tag}>
            Password needs upper, lower, number, and a special character.
          </Text>
        </View>

        <View style={styles.form}>
          <Field
            label="Username"
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
          />
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
          />
          <Field
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Button
            label="Create account"
            loading={loading}
            onPress={async () => {
              setLoading(true);
              setError(null);
              try {
                await signUp({
                  username: username.trim(),
                  email: email.trim(),
                  password,
                });
              } catch (e) {
                setError(userFacingError(e, "Register failed"));
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
  content: { paddingHorizontal: spacing.lg, gap: spacing.xl },
  hero: { gap: 10 },
  brand: {
    color: colors.text,
    fontFamily: "Syne_800ExtraBold",
    fontSize: 44,
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
    color: colors.brand,
    textAlign: "center",
    fontFamily: "DMSans_500Medium",
    fontSize: 15,
    marginTop: 8,
  },
});

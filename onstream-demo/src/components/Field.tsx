import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
} from "react-native";

import { colors, radii } from "../theme/tokens";

type Props = TextInputProps & {
  label: string;
  hint?: string;
};

export function Field({ label, hint, style, secureTextEntry, ...rest }: Props) {
  const [visible, setVisible] = useState(false);
  const isPassword = secureTextEntry === true;

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.inputRow}>
        <TextInput
          placeholderTextColor={colors.textDim}
          style={[styles.input, isPassword && styles.inputWithIcon, style]}
          secureTextEntry={isPassword ? !visible : false}
          {...rest}
        />
        {isPassword ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={visible ? "Hide password" : "Show password"}
            hitSlop={10}
            onPress={() => setVisible((v) => !v)}
            style={styles.eye}
          >
            <Ionicons
              name={visible ? "eye-off-outline" : "eye-outline"}
              size={22}
              color={colors.textMuted}
            />
          </Pressable>
        ) : null}
      </View>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  label: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  inputRow: {
    position: "relative",
    justifyContent: "center",
  },
  input: {
    minHeight: 52,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    color: colors.text,
    paddingHorizontal: 14,
    fontFamily: "DMSans_400Regular",
    fontSize: 16,
  },
  inputWithIcon: {
    paddingRight: 48,
  },
  eye: {
    position: "absolute",
    right: 12,
    height: 52,
    justifyContent: "center",
    alignItems: "center",
  },
  hint: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
});

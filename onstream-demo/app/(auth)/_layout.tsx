import { Stack } from "expo-router";

import { colors } from "@/theme/tokens";

/** Guest-only group — parent Stack.Protected already enforces !signedIn. */
export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.bg },
        animation: "none",
      }}
    />
  );
}

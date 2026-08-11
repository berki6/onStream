import { Redirect, Stack } from "expo-router";

import { useAuth } from "@/context/AuthContext";
import { colors } from "@/theme/tokens";

export default function AuthLayout() {
  const { ready, signedIn } = useAuth();

  // Already signed in — never paint login/register.
  if (ready && signedIn) {
    return <Redirect href="/(tabs)/videos" />;
  }

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

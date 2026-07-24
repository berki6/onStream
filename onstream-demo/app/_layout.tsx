import {
  DMSans_400Regular,
  DMSans_500Medium,
  DMSans_700Bold,
} from "@expo-google-fonts/dm-sans";
import { Syne_700Bold, Syne_800ExtraBold } from "@expo-google-fonts/syne";
import { useFonts } from "expo-font";
import { Stack, useRouter, useSegments } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import React, { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";

import { AuthProvider, useAuth } from "@/context/AuthContext";
import { colors } from "@/theme/tokens";

SplashScreen.preventAutoHideAsync().catch(() => undefined);

function AuthGate({ children }: { children: React.ReactNode }) {
  const { ready, signedIn } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    const inAuth = segments[0] === "(auth)";
    if (!signedIn && !inAuth) {
      router.replace("/(auth)/login");
    } else if (signedIn && inAuth) {
      router.replace("/(tabs)/videos");
    }
  }, [ready, signedIn, segments, router]);

  if (!ready) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: colors.bg,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <ActivityIndicator color={colors.brand} />
      </View>
    );
  }

  return <>{children}</>;
}

export default function RootLayout() {
  const [loaded] = useFonts({
    DMSans_400Regular,
    DMSans_500Medium,
    DMSans_700Bold,
    Syne_700Bold,
    Syne_800ExtraBold,
  });

  useEffect(() => {
    if (loaded) SplashScreen.hideAsync().catch(() => undefined);
  }, [loaded]);

  if (!loaded) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <AuthProvider>
        <StatusBar style="light" />
        <AuthGate>
          <Stack
            screenOptions={{
              headerShown: false,
              contentStyle: { backgroundColor: colors.bg },
              animation: "fade",
            }}
          >
            <Stack.Screen name="(auth)" />
            <Stack.Screen name="(tabs)" />
            <Stack.Screen
              name="video/[id]"
              options={{ headerShown: true, title: "Playback", animation: "slide_from_right" }}
            />
            <Stack.Screen
              name="live/[id]"
              options={{ headerShown: true, title: "Live", animation: "slide_from_right" }}
            />
            <Stack.Screen
              name="live/create"
              options={{
                headerShown: true,
                title: "New live",
                presentation: "modal",
              }}
            />
          </Stack>
        </AuthGate>
      </AuthProvider>
    </GestureHandlerRootView>
  );
}

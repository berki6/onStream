import {
  DMSans_400Regular,
  DMSans_500Medium,
  DMSans_700Bold,
} from "@expo-google-fonts/dm-sans";
import { Syne_700Bold, Syne_800ExtraBold } from "@expo-google-fonts/syne";
import {
  DarkTheme,
  ThemeProvider,
  type Theme,
} from "@react-navigation/native";
import { QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import React, { useEffect } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { AuthProvider, useAuth } from "@/context/AuthContext";
import { queryClient } from "@/query/client";
import { colors } from "@/theme/tokens";

SplashScreen.preventAutoHideAsync().catch(() => undefined);

const navTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: colors.brand,
    background: colors.bg,
    card: colors.bgElevated,
    text: colors.text,
    border: colors.line,
    notification: colors.live,
  },
};

/**
 * Keep the native splash until fonts + atomic session hydrate finish.
 * Matches Expo Router auth guide (SplashScreenController pattern).
 */
function SplashController({ fontsLoaded }: { fontsLoaded: boolean }) {
  const { ready } = useAuth();

  useEffect(() => {
    if (fontsLoaded && ready) {
      SplashScreen.hideAsync().catch(() => undefined);
    }
  }, [fontsLoaded, ready]);

  return null;
}

/**
 * Single auth policy via Stack.Protected (Expo Router SDK 53+).
 * No useEffect redirects — unavailable groups never mount.
 */
function RootNavigator({ fontsLoaded }: { fontsLoaded: boolean }) {
  const { ready, signedIn } = useAuth();

  // Do not mount the stack until session is known — prevents a false
  // guard={false} frame that would flash login for a stored session.
  if (!fontsLoaded || !ready) {
    return null;
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.bg },
        headerStyle: { backgroundColor: colors.bgElevated },
        headerTintColor: colors.text,
        headerShadowVisible: false,
        animation: "slide_from_right",
      }}
    >
      <Stack.Protected guard={signedIn}>
        <Stack.Screen name="index" options={{ animation: "none" }} />
        <Stack.Screen name="(tabs)" options={{ animation: "none" }} />
        <Stack.Screen
          name="video/[id]"
          options={{ headerShown: true, title: "Playback" }}
        />
        <Stack.Screen
          name="live/[id]"
          options={{ headerShown: true, title: "Live" }}
        />
        <Stack.Screen
          name="live/create"
          options={{
            headerShown: true,
            title: "New live",
            presentation: "modal",
            animation: "slide_from_bottom",
          }}
        />
        <Stack.Screen
          name="moderation"
          options={{
            headerShown: true,
            title: "Moderation",
          }}
        />
      </Stack.Protected>

      <Stack.Protected guard={!signedIn}>
        <Stack.Screen name="(auth)" options={{ animation: "none" }} />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    DMSans_400Regular,
    DMSans_500Medium,
    DMSans_700Bold,
    Syne_700Bold,
    Syne_800ExtraBold,
  });

  useEffect(() => {
    SystemUI.setBackgroundColorAsync(colors.bg).catch(() => undefined);
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.bg }}>
      <KeyboardProvider>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider value={navTheme}>
            <AuthProvider>
              <SplashController fontsLoaded={fontsLoaded} />
              <StatusBar style="light" />
              <RootNavigator fontsLoaded={fontsLoaded} />
            </AuthProvider>
          </ThemeProvider>
        </QueryClientProvider>
      </KeyboardProvider>
    </GestureHandlerRootView>
  );
}

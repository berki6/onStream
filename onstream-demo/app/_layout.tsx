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
import { useFonts } from "expo-font";
import { Stack, useRouter, useSegments } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import React, { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { AuthProvider, useAuth } from "@/context/AuthContext";
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
    SystemUI.setBackgroundColorAsync(colors.bg).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (loaded) SplashScreen.hideAsync().catch(() => undefined);
  }, [loaded]);

  if (!loaded) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }} />
    );
  }

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.bg }}>
      <KeyboardProvider>
        <ThemeProvider value={navTheme}>
          <AuthProvider>
            <StatusBar style="light" />
            <AuthGate>
              <Stack
                screenOptions={{
                  headerShown: false,
                  contentStyle: { backgroundColor: colors.bg },
                  headerStyle: { backgroundColor: colors.bgElevated },
                  headerTintColor: colors.text,
                  headerShadowVisible: false,
                  // Avoid root "fade" — it crossfades through the default
                  // white scene backdrop and strobes on back.
                  animation: "slide_from_right",
                }}
              >
                <Stack.Screen name="(auth)" />
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
              </Stack>
            </AuthGate>
          </AuthProvider>
        </ThemeProvider>
      </KeyboardProvider>
    </GestureHandlerRootView>
  );
}

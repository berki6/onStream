import { Redirect } from "expo-router";

import { useAuth } from "@/context/AuthContext";

/**
 * Entry route. Pick destination from hydrated session so cold start never
 * lands on login just because Stack defaulted somewhere wrong.
 */
export default function Index() {
  const { ready, signedIn } = useAuth();

  if (!ready) return null;

  return (
    <Redirect href={signedIn ? "/(tabs)/videos" : "/(auth)/login"} />
  );
}

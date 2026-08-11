import { Redirect } from "expo-router";

/** Authenticated entry — only mounted when Stack.Protected guard={signedIn}. */
export default function Index() {
  return <Redirect href="/(tabs)/videos" />;
}

import { Stack, useRouter } from "expo-router";
import React, { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { ApiError } from "@/api/client";
import { createLiveStream, LiveStream } from "@/api/live";
import { Button } from "@/components/Button";
import { CopyRow } from "@/components/CopyRow";
import { Field } from "@/components/Field";
import { Screen } from "@/components/Screen";
import { colors, spacing } from "@/theme/tokens";

export default function CreateLiveScreen() {
  const router = useRouter();
  const [title, setTitle] = useState("Mobile lab stream");
  const [created, setCreated] = useState<LiveStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <Screen>
      <Stack.Screen
        options={{
          title: "New live",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
        }}
      />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.lead}>
          Stream key, WHIP, and WHEP are shown once. Copy them before leaving.
        </Text>

        {!created ? (
          <View style={styles.form}>
            <Field label="Title" value={title} onChangeText={setTitle} />
            {error ? <Text style={styles.error}>{error}</Text> : null}
            <Button
              label="Create stream"
              loading={loading}
              onPress={async () => {
                setLoading(true);
                setError(null);
                try {
                  const res = await createLiveStream(title.trim() || "Live");
                  setCreated(res.data);
                } catch (e) {
                  setError(e instanceof ApiError ? e.message : "Create failed");
                } finally {
                  setLoading(false);
                }
              }}
            />
          </View>
        ) : (
          <View style={styles.form}>
            <Text style={styles.ok}>Created · {created.stream_id}</Text>
            {created.stream_key ? (
              <CopyRow label="Stream key (once)" value={created.stream_key} />
            ) : null}
            {created.rtmp_url ? (
              <CopyRow label="RTMP URL" value={created.rtmp_url} />
            ) : null}
            {created.whip_url ? (
              <CopyRow label="WHIP URL" value={created.whip_url} />
            ) : null}
            {created.whep_url ? (
              <CopyRow label="WHEP URL" value={created.whep_url} />
            ) : null}
            {created.playback_url ? (
              <CopyRow label="HLS playback" value={created.playback_url} />
            ) : null}
            <Button
              label="Open stream"
              onPress={() => router.replace(`/live/${created.stream_id}`)}
            />
            <Button
              label="Done"
              variant="ghost"
              onPress={() => router.back()}
            />
          </View>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.lg, gap: 16, paddingBottom: 40 },
  lead: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
  },
  form: { gap: 12 },
  error: { color: colors.danger, fontFamily: "DMSans_500Medium" },
  ok: {
    color: colors.brand,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
  },
});

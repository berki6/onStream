import * as Linking from "expo-linking";
import { Stack, useRouter } from "expo-router";
import { useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, getApiBase } from "@/api/client";
import { createLiveStream, LiveStream } from "@/api/live";
import { Button } from "@/components/Button";
import { CopyRow } from "@/components/CopyRow";
import { Field } from "@/components/Field";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { liveKeys } from "@/query/keys";
import { colors, spacing } from "@/theme/tokens";

function whipPublisherUrl(whipUrl: string, host = ""): string {
  const base = (host || getApiBase()).replace(/\/$/, "");
  let whip = whipUrl;
  if (host.includes("127.0.0.1")) {
    try {
      const u = new URL(whipUrl);
      u.hostname = "127.0.0.1";
      whip = u.href;
    } catch {
      /* keep original */
    }
  }
  return `${base}/demo/whip/?whip=${encodeURIComponent(whip)}`;
}

export default function CreateLiveScreen() {
  const router = useRouter();
  const qc = useQueryClient();
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
      <FormScroll contentContainerStyle={styles.content}>
        <Text style={styles.lead}>
          Stream key, WHIP, and WHEP are shown once. Copy them before leaving.
          The in-app Go Live button opens a phone browser on http://LAN-IP —
          Chrome blocks the camera there. Use the PC localhost link for webcam.
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
                  qc.setQueryData(liveKeys.detail(res.data.stream_id), res.data);
                  await qc.invalidateQueries({ queryKey: liveKeys.list() });
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

            {created.whip_url ? (
              <>
                <CopyRow
                  label="PC camera link (localhost)"
                  value={whipPublisherUrl(
                    created.whip_url,
                    "http://127.0.0.1:8000"
                  )}
                />
                <Button
                  label="Go Live (WHIP in browser)"
                  onPress={async () => {
                    const url = whipPublisherUrl(created.whip_url!);
                    try {
                      await Linking.openURL(url);
                    } catch {
                      setError("Could not open WHIP publisher");
                    }
                  }}
                />
              </>
            ) : null}

            <Button
              label="Open stream"
              variant="ghost"
              onPress={() => router.replace(`/live/${created.stream_id}`)}
            />
            <Button
              label="Done"
              variant="ghost"
              onPress={() => router.back()}
            />
            {error ? <Text style={styles.error}>{error}</Text> : null}
          </View>
        )}
      </FormScroll>
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

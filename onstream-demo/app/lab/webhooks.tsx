import { Ionicons } from "@expo/vector-icons";
import { Stack, useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError } from "@/api/client";
import {
  createWebhookEndpoint,
  deleteWebhookEndpoint,
  LAB_EVENTS,
  listWebhookDeliveries,
  listWebhookEndpoints,
  type WebhookDelivery,
  type WebhookEndpoint,
} from "@/api/webhooks";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { colors, radii, spacing } from "@/theme/tokens";

export default function LabWebhooksScreen() {
  const insets = useSafeAreaInsets();
  const [hookUrl, setHookUrl] = useState("https://webhook.site/");
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [hooksLoading, setHooksLoading] = useState(true);
  const [hookBusy, setHookBusy] = useState(false);
  const [hookError, setHookError] = useState<string | null>(null);
  const [hookNote, setHookNote] = useState<string | null>(null);
  const [secretOnce, setSecretOnce] = useState<string | null>(null);

  const loadHooks = useCallback(async () => {
    setHookError(null);
    try {
      const [eps, dels] = await Promise.all([
        listWebhookEndpoints(),
        listWebhookDeliveries(40),
      ]);
      setEndpoints(eps.data || []);
      setDeliveries(dels.data || []);
    } catch (e) {
      setHookError(
        e instanceof ApiError ? e.message : "Failed to load webhooks"
      );
    } finally {
      setHooksLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      setHooksLoading(true);
      void loadHooks();
    }, [loadHooks])
  );

  return (
    <Screen>
      <Stack.Screen
        options={{
          headerShown: true,
          title: "Webhooks",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
          headerShadowVisible: false,
        }}
      />
      <FormScroll
        contentContainerStyle={[
          styles.content,
          { paddingBottom: insets.bottom + 36 },
        ]}
      >
        <View style={styles.intro}>
          <View style={styles.introIcon}>
            <Ionicons name="flash" size={22} color={colors.brand} />
          </View>
          <Text style={styles.introBody}>
            Subscribe to see live.* and VOD events. Point the URL at
            webhook.site or any HTTPS catcher.
          </Text>
        </View>

        <Field
          label="Endpoint URL"
          value={hookUrl}
          onChangeText={setHookUrl}
          autoCapitalize="none"
          hint={`Subscribes to: ${LAB_EVENTS.filter((e) => e.startsWith("live.")).join(", ")} + core VOD events`}
        />
        <Button
          label={hookBusy ? "Subscribing…" : "Subscribe"}
          loading={hookBusy}
          onPress={async () => {
            setHookBusy(true);
            setHookError(null);
            setHookNote(null);
            setSecretOnce(null);
            try {
              const res = await createWebhookEndpoint({ url: hookUrl.trim() });
              if (res.data?.secret) {
                setSecretOnce(res.data.secret);
              }
              setHookNote(
                `Registered #${res.data.id} — create/revoke a live stream to enqueue live.* deliveries.`
              );
              await loadHooks();
            } catch (e) {
              setHookError(
                e instanceof ApiError ? e.message : "Subscribe failed"
              );
            } finally {
              setHookBusy(false);
            }
          }}
        />
        {secretOnce ? (
          <Text style={styles.secretNote}>
            Signing secret (shown once): {secretOnce}
          </Text>
        ) : null}
        {hookNote ? <Text style={styles.note}>{hookNote}</Text> : null}
        {hookError ? <Text style={styles.error}>{hookError}</Text> : null}

        <Text style={styles.subhead}>Endpoints</Text>
        {hooksLoading ? (
          <ActivityIndicator color={colors.brand} />
        ) : endpoints.length === 0 ? (
          <Text style={styles.emptyHint}>No endpoints yet.</Text>
        ) : (
          endpoints.map((ep) => (
            <View key={ep.id} style={styles.epCard}>
              <View style={styles.epTop}>
                <Ionicons
                  name="link-outline"
                  size={16}
                  color={colors.textMuted}
                />
                <Text style={styles.epUrl} numberOfLines={2}>
                  {ep.url}
                </Text>
                <Pressable
                  hitSlop={8}
                  onPress={async () => {
                    try {
                      await deleteWebhookEndpoint(ep.id);
                      await loadHooks();
                    } catch (e) {
                      setHookError(
                        e instanceof ApiError ? e.message : "Delete failed"
                      );
                    }
                  }}
                >
                  <Ionicons
                    name="trash-outline"
                    size={18}
                    color={colors.danger}
                  />
                </Pressable>
              </View>
              <Text style={styles.epMeta}>
                #{ep.id} · {(ep.events || []).join(", ")}
              </Text>
            </View>
          ))
        )}

        <View style={styles.logHead}>
          <Text style={styles.subhead}>Delivery log</Text>
          <Pressable onPress={() => void loadHooks()} hitSlop={8}>
            <Ionicons name="refresh" size={18} color={colors.brand} />
          </Pressable>
        </View>
        {deliveries.length === 0 ? (
          <Text style={styles.emptyHint}>
            Empty until an event fires (e.g. create or revoke a live stream).
          </Text>
        ) : (
          deliveries.map((d) => (
            <View key={d.id} style={styles.delCard}>
              <View style={styles.delTop}>
                <Text style={styles.delEvent}>{d.event}</Text>
                <StatusPill status={d.status} />
              </View>
              <Text style={styles.epMeta}>
                #{d.id} · endpoint {d.endpoint_id} · attempts {d.attempts}
                {d.created_at ? ` · ${d.created_at}` : ""}
              </Text>
              {d.last_error ? (
                <Text style={styles.delErr} numberOfLines={2}>
                  {d.last_error}
                </Text>
              ) : null}
              {d.payload_preview ? (
                <Text style={styles.payload} numberOfLines={3}>
                  {d.payload_preview}
                </Text>
              ) : null}
            </View>
          ))
        )}
      </FormScroll>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    gap: 12,
  },
  intro: {
    flexDirection: "row",
    gap: 12,
    alignItems: "flex-start",
    marginBottom: 4,
  },
  introIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandSoft,
  },
  introBody: {
    flex: 1,
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
    lineHeight: 20,
  },
  subhead: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 15,
    marginTop: 4,
  },
  epCard: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    padding: 12,
    gap: 6,
  },
  epTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  epUrl: {
    flex: 1,
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
  epMeta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 11,
  },
  logHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 4,
  },
  delCard: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 12,
    gap: 6,
  },
  delTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  delEvent: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 14,
    flex: 1,
  },
  delErr: {
    color: colors.danger,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  payload: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 11,
    lineHeight: 15,
  },
  emptyHint: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
  },
  note: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
  secretNote: {
    color: colors.warning,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
});

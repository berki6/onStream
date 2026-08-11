import { Ionicons } from "@expo/vector-icons";
import * as Linking from "expo-linking";
import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  ApiError,
  getApiBase,
  pingHealthLabel,
  setApiBase,
} from "@/api/client";
import {
  createWebhookEndpoint,
  deleteWebhookEndpoint,
  LAB_EVENTS,
  listWebhookDeliveries,
  listWebhookEndpoints,
  WebhookDelivery,
  WebhookEndpoint,
} from "@/api/webhooks";
import { Button } from "@/components/Button";
import { Field } from "@/components/Field";
import { FormScroll } from "@/components/FormScroll";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { useAuth } from "@/context/AuthContext";
import { colors, radii, spacing } from "@/theme/tokens";

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();
  const { username, signOut } = useAuth();
  const [apiBase, setApiBaseLocal] = useState(getApiBase());
  const [health, setHealth] = useState<string>("—");
  const [saved, setSaved] = useState(false);

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
      setApiBaseLocal(getApiBase());
      setHooksLoading(true);
      loadHooks();
    }, [loadHooks])
  );

  return (
    <Screen>
      <FormScroll
        contentContainerStyle={[
          styles.content,
          {
            paddingTop: insets.top + spacing.lg,
            paddingBottom: insets.bottom + 32,
          },
        ]}
      >
        <Text style={styles.kicker}>Lab</Text>
        <Text
          style={styles.title}
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.75}
        >
          OnStream
        </Text>
        <Text style={styles.body}>
          Signed in as {username || "—"}. Point this demo at your engine, then
          exercise VOD, live, and webhook delivery.
        </Text>

        <View style={styles.block}>
          <Field
            label="API base URL"
            value={apiBase}
            onChangeText={(v) => {
              setApiBaseLocal(v);
              setSaved(false);
            }}
            autoCapitalize="none"
            hint="Use your LAN IP for a physical phone (Expo Go)."
          />
          <Button
            label={saved ? "Saved" : "Save API URL"}
            onPress={async () => {
              await setApiBase(apiBase);
              setSaved(true);
            }}
          />
          <Button
            label="Check /health"
            variant="ghost"
            onPress={async () => {
              await setApiBase(apiBase);
              setHealth(await pingHealthLabel());
            }}
          />
          <Text style={styles.mono}>{health}</Text>
          <Pressable
            onPress={async () => {
              const url = `${getApiBase()}/scalar`;
              await Linking.openURL(url);
            }}
            style={({ pressed }) => [
              styles.linkRow,
              pressed && { opacity: 0.85 },
            ]}
          >
            <Ionicons name="book-outline" size={18} color={colors.brand} />
            <Text style={styles.linkText}>Open Scalar API docs</Text>
            <Ionicons
              name="open-outline"
              size={16}
              color={colors.textDim}
            />
          </Pressable>
        </View>

        <View style={styles.block}>
          <View style={styles.sectionHead}>
            <Ionicons name="flash" size={18} color={colors.brand} />
            <Text style={styles.section}>Webhooks</Text>
          </View>
          <Text style={styles.body}>
            Subscribe to see live.created / started / idle / ended (and VOD
            events) in the delivery log below. Point the URL at webhook.site
            or any HTTPS catcher.
          </Text>
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
                          e instanceof ApiError
                            ? e.message
                            : "Delete failed"
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
            <Pressable onPress={loadHooks} hitSlop={8}>
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
        </View>

        <View style={styles.block}>
          <Text style={styles.section}>How to run</Text>
          <Text style={styles.body}>
            1. Start API on your machine{"\n"}
            2. Set API URL to http://&lt;LAN-IP&gt;:8000{"\n"}
            3. Scan Expo Go QR from `npm start`{"\n"}
            4. Upload / create live / play HLS{"\n"}
            5. Subscribe webhooks → revoke live → refresh delivery log
          </Text>
        </View>

        <Button label="Sign out" variant="danger" onPress={signOut} />
      </FormScroll>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
  },
  kicker: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  title: {
    color: colors.brand,
    fontFamily: "Syne_800ExtraBold",
    fontSize: 40,
    letterSpacing: -1,
  },
  body: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
  },
  block: { gap: 12, marginTop: 8 },
  sectionHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  section: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
  },
  subhead: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 15,
    marginTop: 4,
  },
  mono: {
    color: colors.brandDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  linkText: {
    flex: 1,
    color: colors.brand,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
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

import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";
import { Stack } from "expo-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { queryErrorText, userFacingError } from "@/api/client";
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  type ApiKey,
} from "@/api/apiKeys";
import { Button } from "@/components/Button";
import { CinemaSheet } from "@/components/CinemaSheet";
import { ElasticRefreshFlatList } from "@/components/ElasticRefreshFlatList";
import { Field } from "@/components/Field";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { toast } from "@/lib/toast";
import { apiKeyKeys } from "@/query/keys";
import { colors, radii, spacing } from "@/theme/tokens";

const SCOPE_OPTIONS = ["read", "upload", "write", "webhooks"] as const;
const DEFAULT_SCOPES = new Set(["read", "upload", "webhooks"]);

function formatWhen(iso?: string | null): string {
  if (!iso) return "never";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export default function ApiKeysScreen() {
  const qc = useQueryClient();
  const { data: items = [], isPending, isError, error, refetch } = useQuery({
    queryKey: apiKeyKeys.list(),
    queryFn: async () => (await listApiKeys()).data || [],
  });
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<Set<string>>(() => new Set(DEFAULT_SCOPES));
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [secretOnce, setSecretOnce] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const listError = queryErrorText(isError, error, items.length > 0);
  const scopeStr = useMemo(
    () => SCOPE_OPTIONS.filter((s) => scopes.has(s)).join(","),
    [scopes]
  );

  const closeSheet = () => {
    if (busy) return;
    setOpen(false);
    setFormError(null);
  };

  const toggleScope = (id: string) => {
    setScopes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const create = async () => {
    const n = name.trim();
    if (n.length < 1) {
      setFormError("Name is required.");
      return;
    }
    if (scopes.size === 0) {
      setFormError("Pick at least one scope.");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      const res = await createApiKey(n, scopeStr);
      setOpen(false);
      setName("");
      setScopes(new Set(DEFAULT_SCOPES));
      const raw = res.data.api_key;
      if (raw) {
        setSecretOnce(raw);
        await Clipboard.setStringAsync(raw);
        toast.success("API key copied — it will not be shown again.");
      }
      await qc.invalidateQueries({ queryKey: apiKeyKeys.list() });
    } catch (e) {
      setFormError(userFacingError(e, "Could not create API key"));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (key: ApiKey) => {
    setBusyId(key.id);
    try {
      await revokeApiKey(key.id);
      await qc.invalidateQueries({ queryKey: apiKeyKeys.list() });
      toast.success("API key revoked.");
    } catch (e) {
      toast.error(userFacingError(e, "Revoke failed"));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Screen>
      <Stack.Screen
        options={{
          headerShown: true,
          title: "API keys",
          headerStyle: { backgroundColor: colors.bgElevated },
          headerTintColor: colors.text,
          headerTitleStyle: { fontFamily: "Syne_700Bold" },
          headerShadowVisible: false,
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="New API key"
              onPress={() => setOpen(true)}
              hitSlop={8}
              style={{ marginRight: 8 }}
            >
              <Ionicons name="add" size={24} color={colors.brand} />
            </Pressable>
          ),
        }}
      />
      {isPending && items.length === 0 ? (
        <ActivityIndicator color={colors.brand} style={{ marginTop: 40 }} />
      ) : (
        <ElasticRefreshFlatList
          data={items}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={[
            styles.list,
            items.length === 0 && styles.listEmpty,
          ]}
          onRefresh={async () => {
            await refetch();
          }}
          ListHeaderComponent={
            <View style={styles.headerBlock}>
              <Text style={styles.lead}>
                Machine auth via X-API-Key. Scopes are enforced: read, upload,
                write, webhooks. Keys cannot create or revoke other keys — use
                this signed-in session. The secret is shown once.
              </Text>
              {secretOnce ? (
                <Pressable
                  onPress={async () => {
                    await Clipboard.setStringAsync(secretOnce);
                    toast.success("Copied.");
                  }}
                  style={styles.secretBox}
                >
                  <Text style={styles.secretLabel}>Secret (shown once)</Text>
                  <Text style={styles.secretValue}>{secretOnce}</Text>
                </Pressable>
              ) : null}
              {listError ? <Text style={styles.error}>{listError}</Text> : null}
            </View>
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <Ionicons name="key-outline" size={32} color={colors.brand} />
              </View>
              <Text style={styles.emptyTitle}>No API keys</Text>
              <Text style={styles.emptyBody}>
                Create a least-privilege key for CI or scripts. Default scopes
                upload, read, and webhooks — not write.
              </Text>
            </View>
          }
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>{item.name}</Text>
              <Text style={styles.meta}>
                {item.key_prefix}… · {item.scopes || "—"}
              </Text>
              <Text style={styles.meta}>
                last used {formatWhen(item.last_used_at)}
              </Text>
              <View style={styles.row}>
                <StatusPill status={item.is_active ? "active" : "revoked"} />
                {item.is_active ? (
                  <Button
                    label="Revoke"
                    variant="danger"
                    loading={busyId === item.id}
                    style={styles.btn}
                    onPress={() => void revoke(item)}
                  />
                ) : null}
              </View>
            </View>
          )}
        />
      )}
      <CinemaSheet visible={open} onClose={closeSheet} dismissEnabled={!busy}>
        <Text style={styles.sheetTitle}>New API key</Text>
        <Field
          label="Name"
          value={name}
          onChangeText={setName}
          autoCapitalize="none"
          maxLength={100}
        />
        <Text style={styles.scopeLabel}>Scopes</Text>
        <View style={styles.filters}>
          {SCOPE_OPTIONS.map((id) => {
            const on = scopes.has(id);
            return (
              <Pressable
                key={id}
                onPress={() => toggleScope(id)}
                style={[styles.chip, on && styles.chipOn]}
              >
                <Text style={[styles.chipText, on && styles.chipTextOn]}>
                  {id}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.hint}>
          write covers deletes, live control, playlists, and share-link create.
          Playback tokens only need read.
        </Text>
        {formError ? <Text style={styles.error}>{formError}</Text> : null}
        <Button label="Create" loading={busy} onPress={() => void create()} />
      </CinemaSheet>
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.lg, gap: 10, paddingBottom: 40 },
  listEmpty: { flexGrow: 1 },
  headerBlock: { gap: 12, marginBottom: 4 },
  lead: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
  },
  secretBox: {
    padding: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "rgba(46, 230, 166, 0.35)",
    backgroundColor: colors.brandSoft,
    gap: 4,
  },
  secretLabel: {
    color: colors.brand,
    fontFamily: "DMSans_700Bold",
    fontSize: 11,
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  secretValue: {
    color: colors.text,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
  },
  card: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    padding: 14,
    gap: 8,
  },
  cardTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 16,
  },
  meta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 4 },
  btn: { flex: 1, minWidth: 88 },
  error: { color: colors.danger, fontFamily: "DMSans_500Medium", fontSize: 13 },
  empty: { alignItems: "center", gap: 10, paddingHorizontal: spacing.xl, paddingTop: 24 },
  emptyIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandSoft,
  },
  emptyTitle: { color: colors.text, fontFamily: "Syne_700Bold", fontSize: 22 },
  emptyBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
    textAlign: "center",
  },
  sheetTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 20,
    marginBottom: 8,
  },
  scopeLabel: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 4,
  },
  filters: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: radii.xl,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  chipOn: {
    borderColor: "rgba(46, 230, 166, 0.45)",
    backgroundColor: colors.brandSoft,
  },
  chipText: {
    color: colors.textMuted,
    fontFamily: "DMSans_700Bold",
    fontSize: 12,
  },
  chipTextOn: { color: colors.brand },
  hint: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    lineHeight: 16,
  },
});

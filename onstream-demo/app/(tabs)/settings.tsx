import { Ionicons } from "@expo/vector-icons";
import * as Linking from "expo-linking";
import { useRouter, type Href } from "expo-router";
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { getApiBase } from "@/api/client";
import { FormScroll } from "@/components/FormScroll";
import { LabToolRow } from "@/components/LabToolRow";
import { Screen } from "@/components/Screen";
import { colors, spacing } from "@/theme/tokens";

/**
 * Lab hub — operator tools only. Connection + sign-out live on Account.
 */
export default function LabScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  return (
    <Screen>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <View style={{ flex: 1 }}>
          <Text style={styles.kicker}>Lab</Text>
          <Text
            style={styles.title}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.75}
          >
            Tools
          </Text>
        </View>
        <View style={styles.heroIcon}>
          <Ionicons name="flask" size={22} color={colors.brand} />
        </View>
      </View>

      <FormScroll
        contentContainerStyle={[
          styles.content,
          { paddingBottom: insets.bottom + 40 },
        ]}
      >
        <Text style={styles.body}>
          Operator surfaces for moderation, webhooks, and browser helpers.
          Connection settings are under Account.
        </Text>

        <Text style={styles.group}>Review</Text>
        <View style={styles.stack}>
          <LabToolRow
            icon="shield-checkmark"
            title="Moderation queue"
            subtitle="Review quarantined uploads"
            onPress={() => router.push("/moderation" as Href)}
          />
        </View>

        <Text style={styles.group}>Events</Text>
        <View style={styles.stack}>
          <LabToolRow
            icon="flash"
            title="Webhooks"
            subtitle="Endpoints and delivery log"
            onPress={() => router.push("/lab/webhooks" as Href)}
          />
        </View>

        <Text style={styles.group}>Browser</Text>
        <View style={styles.stack}>
          <LabToolRow
            icon="cloud-upload"
            title="Direct upload"
            subtitle="Open /demo/upload on this API"
            trailing="open"
            onPress={async () => {
              await Linking.openURL(`${getApiBase()}/demo/upload/`);
            }}
          />
          <LabToolRow
            icon="videocam"
            title="WHIP publisher"
            subtitle="Camera publish via /demo/whip"
            trailing="open"
            onPress={async () => {
              await Linking.openURL(`${getApiBase()}/demo/whip/`);
            }}
          />
        </View>

        <Text style={styles.group}>Guide</Text>
        <View style={styles.guide}>
          <Text style={styles.guideLine}>1. Set API URL on Account</Text>
          <Text style={styles.guideLine}>
            2. Upload or go live from Library / Live
          </Text>
          <Text style={styles.guideLine}>3. Subscribe webhooks → fire an event</Text>
          <Text style={styles.guideLine}>4. Refresh delivery log</Text>
        </View>
      </FormScroll>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  heroIcon: {
    width: 44,
    height: 44,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandSoft,
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
    fontSize: 32,
    letterSpacing: -0.8,
  },
  content: {
    paddingHorizontal: spacing.lg,
    gap: 10,
  },
  body: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 15,
    lineHeight: 22,
    marginBottom: 8,
  },
  group: {
    color: colors.textDim,
    fontFamily: "DMSans_700Bold",
    fontSize: 11,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginTop: 14,
    marginBottom: 2,
  },
  stack: { gap: 10 },
  guide: {
    gap: 6,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: "rgba(0,0,0,0.18)",
    marginTop: 4,
  },
  guideLine: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
    lineHeight: 18,
  },
});

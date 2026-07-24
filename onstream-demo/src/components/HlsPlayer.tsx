import { useVideoPlayer, VideoView } from "expo-video";
import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radii } from "../theme/tokens";

type Props = {
  uri: string | null;
  title?: string;
};

export function HlsPlayer({ uri, title }: Props) {
  const [playing, setPlaying] = useState(false);
  const player = useVideoPlayer(null, (p) => {
    p.loop = false;
  });

  useEffect(() => {
    if (!uri) {
      player.pause();
      setPlaying(false);
      return;
    }
    player.replace({ uri, contentType: "hls" as const });
    player.play();
    setPlaying(true);
  }, [uri, player]);

  if (!uri) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>No stream URL</Text>
        <Text style={styles.emptyBody}>
          Issue a playback token once the asset is READY or the live playlist is
          present.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <VideoView
        style={styles.video}
        player={player}
        allowsFullscreen
        allowsPictureInPicture
        contentFit="contain"
        nativeControls
      />
      <View style={styles.bar}>
        <Text style={styles.title} numberOfLines={1}>
          {title || "Playback"}
        </Text>
        <Pressable
          onPress={() => {
            if (playing) {
              player.pause();
              setPlaying(false);
            } else {
              player.play();
              setPlaying(true);
            }
          }}
          style={styles.chip}
        >
          <Text style={styles.chipText}>{playing ? "Pause" : "Play"}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderRadius: radii.lg,
    overflow: "hidden",
    backgroundColor: "#000",
    borderWidth: 1,
    borderColor: colors.line,
  },
  video: {
    width: "100%",
    aspectRatio: 16 / 9,
    backgroundColor: "#000",
  },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: colors.bgElevated,
  },
  title: {
    flex: 1,
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radii.xl,
    backgroundColor: colors.brandSoft,
  },
  chipText: {
    color: colors.brand,
    fontFamily: "DMSans_700Bold",
    fontSize: 12,
  },
  empty: {
    minHeight: 180,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
    padding: 20,
    justifyContent: "center",
    gap: 8,
  },
  emptyTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
  },
  emptyBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
    lineHeight: 20,
  },
});

import React, { useEffect, useState } from "react";
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { colors, radii, spacing } from "@/theme/tokens";

export type StoryboardCue = {
  start: number;
  end: number;
  x: number;
  y: number;
  w: number;
  h: number;
};

function parseVtt(text: string): StoryboardCue[] {
  const cues: StoryboardCue[] = [];
  const blocks = text.replace(/\r/g, "").split("\n\n");
  const ts =
    /(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})/;
  const xywh = /#xywh=(\d+),(\d+),(\d+),(\d+)/;
  const toSec = (h: string, m: string, s: string, ms: string) =>
    Number(h) * 3600 + Number(m) * 60 + Number(s) + Number(ms) / 1000;
  for (const block of blocks) {
    const lines = block.split("\n").filter(Boolean);
    if (lines[0] === "WEBVTT") continue;
    const timeLine = lines.find((l) => l.includes("-->"));
    const uriLine = lines.find((l) => l.includes("#xywh="));
    if (!timeLine || !uriLine) continue;
    const tm = timeLine.match(ts);
    const xy = uriLine.match(xywh);
    if (!tm || !xy) continue;
    cues.push({
      start: toSec(tm[1], tm[2], tm[3], tm[4]),
      end: toSec(tm[5], tm[6], tm[7], tm[8]),
      x: Number(xy[1]),
      y: Number(xy[2]),
      w: Number(xy[3]),
      h: Number(xy[4]),
    });
  }
  return cues;
}

type Props = {
  vttUrl?: string | null;
  imageUrl?: string | null;
  onSeek?: (seconds: number) => void;
};

export function StoryboardStrip({ vttUrl, imageUrl, onSeek }: Props) {
  const [cues, setCues] = useState<StoryboardCue[]>([]);

  useEffect(() => {
    if (!vttUrl) {
      setCues([]);
      return;
    }
    let alive = true;
    void fetch(vttUrl)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error("vtt"))))
      .then((text) => {
        if (alive) setCues(parseVtt(text));
      })
      .catch(() => {
        if (alive) setCues([]);
      });
    return () => {
      alive = false;
    };
  }, [vttUrl]);

  if (!imageUrl || cues.length === 0) return null;

  const spriteW = Math.max(...cues.map((c) => c.x + c.w), 1);
  const spriteH = Math.max(...cues.map((c) => c.y + c.h), 1);
  const tileW = 72;
  const tileH = 40;

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>Scrub preview</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.row}
      >
        {cues.map((cue) => {
          const sx = tileW / Math.max(cue.w, 1);
          const sy = tileH / Math.max(cue.h, 1);
          return (
            <Pressable
              key={`${cue.start}-${cue.x}-${cue.y}`}
              onPress={() => onSeek?.(cue.start)}
              style={({ pressed }) => [styles.tile, pressed && { opacity: 0.8 }]}
            >
              <View style={styles.crop}>
                <Image
                  source={{ uri: imageUrl }}
                  style={{
                    width: spriteW * sx,
                    height: spriteH * sy,
                    marginLeft: -cue.x * sx,
                    marginTop: -cue.y * sy,
                  }}
                />
              </View>
              <Text style={styles.time}>
                {Math.floor(cue.start / 60)}:
                {String(Math.floor(cue.start % 60)).padStart(2, "0")}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  label: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    paddingHorizontal: 2,
  },
  row: { gap: spacing.sm, paddingRight: spacing.md },
  tile: { width: 72, gap: 4 },
  crop: {
    width: 72,
    height: 40,
    overflow: "hidden",
    borderRadius: 6,
    backgroundColor: "#000",
  },
  time: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 10,
  },
});

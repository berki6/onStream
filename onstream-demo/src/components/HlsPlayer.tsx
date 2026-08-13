import { useVideoPlayer, VideoView } from "expo-video";
import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radii } from "../theme/tokens";

type Props = {
  uri: string | null;
  title?: string;
  initialPositionSeconds?: number;
  clipEndSeconds?: number | null;
  onProgress?: (positionSeconds: number, durationSeconds: number) => void;
  onEnded?: () => void;
};

export type HlsPlayerHandle = {
  seekTo: (seconds: number) => void;
};

export const HlsPlayer = forwardRef<HlsPlayerHandle, Props>(function HlsPlayer(
  { uri, title, initialPositionSeconds = 0, clipEndSeconds, onProgress, onEnded },
  ref
) {
  const [playing, setPlaying] = useState(false);
  const seekDone = useRef(false);
  const lastSent = useRef(0);
  const lastPos = useRef(0);
  const lastDur = useRef(0);
  const resumeTarget = useRef(initialPositionSeconds);
  const loadedUri = useRef<string | null>(null);
  const onProgressRef = useRef(onProgress);
  onProgressRef.current = onProgress;
  const onEndedRef = useRef(onEnded);
  onEndedRef.current = onEnded;
  const clipEndRef = useRef(clipEndSeconds);
  clipEndRef.current = clipEndSeconds;
  const endedOnce = useRef(false);

  const player = useVideoPlayer(null, (p) => {
    p.loop = false;
  });

  useImperativeHandle(
    ref,
    () => ({
      seekTo(seconds: number) {
        const t = Math.max(0, seconds);
        resumeTarget.current = t;
        seekDone.current = false;
        try {
          player.currentTime = t;
        } catch {
          /* retry via progress loop */
        }
        player.play();
        setPlaying(true);
      },
    }),
    [player]
  );

  // Capture resume target once per uri — do not re-seek when progress query updates.
  if (uri !== loadedUri.current) {
    loadedUri.current = uri;
    resumeTarget.current = initialPositionSeconds;
    seekDone.current = false;
    endedOnce.current = false;
  }

  useEffect(() => {
    let cancelled = false;
    seekDone.current = false;
    (async () => {
      if (!uri) {
        player.pause();
        setPlaying(false);
        return;
      }
      await player.replaceAsync({ uri, contentType: "hls" as const });
      if (cancelled) return;
      const target = resumeTarget.current;
      if (target > 2) {
        try {
          player.currentTime = target;
        } catch {
          /* seek may fail until buffered — retry in progress loop */
        }
      } else {
        seekDone.current = true;
      }
      player.play();
      setPlaying(true);
    })();
    return () => {
      cancelled = true;
    };
    // Intentionally omit initialPositionSeconds — frozen per uri via resumeTarget.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uri, player]);

  useEffect(() => {
    if (!uri) return;
    const id = setInterval(() => {
      const pos = Number(player.currentTime) || 0;
      const dur = Number(player.duration) || 0;
      if (pos > 0) {
        lastPos.current = pos;
        lastDur.current = dur > 0 ? dur : pos;
      }

      const target = resumeTarget.current;
      if (!seekDone.current && target > 2) {
        if (pos < target - 1.5) {
          try {
            player.currentTime = target;
          } catch {
            /* ignore */
          }
          return;
        }
        // Seek stuck near target (or past it) — allow progress saves.
        seekDone.current = true;
      }

      if (!seekDone.current) return;
      const clipEnd = clipEndRef.current;
      if (
        clipEnd != null &&
        clipEnd > 0 &&
        pos >= clipEnd - 0.25 &&
        !endedOnce.current
      ) {
        endedOnce.current = true;
        try {
          player.pause();
          setPlaying(false);
        } catch {
          /* ignore */
        }
        onEndedRef.current?.();
        return;
      }
      if (dur > 0 && pos >= dur - 0.35 && !endedOnce.current) {
        endedOnce.current = true;
        onEndedRef.current?.();
      }
      if (pos <= 0) return;
      // Don't overwrite resume with a pre-seek near-zero sample.
      if (target > 2 && pos < Math.min(5, target * 0.5)) return;

      const now = Date.now();
      if (now - lastSent.current < 4500) return;
      lastSent.current = now;
      onProgressRef.current?.(pos, dur > 0 ? dur : pos);
    }, 2000);
    return () => {
      clearInterval(id);
    };
  }, [uri, player]);

  // Flush progress only on true unmount (not when uri deps churn).
  useEffect(() => {
    return () => {
      const pos = lastPos.current;
      const dur = lastDur.current;
      if (pos > 0 && seekDone.current) {
        onProgressRef.current?.(pos, dur > 0 ? dur : pos);
      }
    };
  }, []);

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
        fullscreenOptions={{ enable: true }}
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
              const pos = Number(player.currentTime) || 0;
              const dur = Number(player.duration) || 0;
              if (pos > 0 && seekDone.current) {
                onProgressRef.current?.(pos, dur > 0 ? dur : pos);
              }
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
});

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

import { Ionicons } from "@expo/vector-icons";
import * as DocumentPicker from "expo-document-picker";
import * as Haptics from "expo-haptics";
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Gesture, GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { scheduleOnRN } from "react-native-worklets";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError } from "@/api/client";
import { uploadVideoDirect } from "@/api/uploads";
import { uploadVideoMultipart } from "@/api/videos";
import { Field } from "@/components/Field";
import { colors, radii, spacing } from "@/theme/tokens";

export type UploadMethod = "direct" | "multipart";

type Picked = {
  uri: string;
  name: string;
  mimeType: string;
  size: number | null;
};

type Phase = "idle" | "ready" | "uploading" | "done" | "error";

type Props = {
  visible: boolean;
  onClose: () => void;
  onFinished: () => void | Promise<void>;
};

const DIRECT_THRESHOLD = 4 * 1024 * 1024; // 4 MiB — Mux-style prefer resumable for larger
const OPEN_MS = 300;
const CLOSE_MS = 240;
const DISMISS_DRAG_PX = 110;
const DISMISS_VELOCITY = 900;
const SHEET_HEIGHT_FALLBACK = 420;

function formatBytes(n: number | null): string {
  if (n == null || n <= 0) return "Size unknown";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function defaultMethod(size: number | null): UploadMethod {
  if (size != null && size >= DIRECT_THRESHOLD) return "direct";
  return "multipart";
}

/**
 * Mux / YouTube Studio–inspired upload sheet:
 * pick → metadata → method → progress bar → done.
 *
 * Scrim + sheet fade/slide on the same progress value so the dimmer does not
 * linger after the sheet (native Modal `slide` caused that stagger).
 */
export function VideoUploadComposer({ visible, onClose, onFinished }: Props) {
  const insets = useSafeAreaInsets();
  const [phase, setPhase] = useState<Phase>("idle");
  const [picked, setPicked] = useState<Picked | null>(null);
  const [title, setTitle] = useState("");
  const [method, setMethod] = useState<UploadMethod>("direct");
  const [pct, setPct] = useState(0);
  const [error, setError] = useState<string | null>(null);
  /** Keep Modal mounted until exit animation finishes. */
  const [presented, setPresented] = useState(false);

  const progress = useSharedValue(0);
  const dragY = useSharedValue(0);
  const sheetHeight = useSharedValue(SHEET_HEIGHT_FALLBACK);

  const stageLabel = useMemo(() => {
    if (phase === "uploading") {
      return method === "direct"
        ? `Uploading chunks · ${pct}%`
        : "Uploading file…";
    }
    if (phase === "done") return "Queued for processing";
    if (phase === "error") return "Upload failed";
    if (phase === "ready") return "Ready to send";
    return "Pick a video from your library";
  }, [phase, method, pct]);

  function reset() {
    setPhase("idle");
    setPicked(null);
    setTitle("");
    setMethod("direct");
    setPct(0);
    setError(null);
  }

  function finishExit() {
    // Unmount first — resetting drag/progress while still mounted caused a
    // one-frame pop/flash at the end of the close.
    setPresented(false);
    requestAnimationFrame(() => {
      progress.value = 0;
      dragY.value = 0;
      reset();
    });
  }

  // Mount Modal first at progress=0; never start the open timing while unmounted
  // (that finished off-screen and made open feel instant).
  useEffect(() => {
    if (visible) {
      progress.value = 0;
      dragY.value = 0;
      setPresented(true);
      return;
    }
    if (!presented) return;
    progress.value = withTiming(
      0,
      { duration: CLOSE_MS, easing: Easing.in(Easing.cubic) },
      (finished) => {
        if (finished) scheduleOnRN(finishExit);
      }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- drive only from `visible`
  }, [visible]);

  useEffect(() => {
    if (!visible || !presented) return;
    const id = requestAnimationFrame(() => {
      progress.value = withTiming(1, {
        duration: OPEN_MS,
        easing: Easing.out(Easing.cubic),
      });
    });
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, presented]);

  function handleClose() {
    if (phase === "uploading") return;
    onClose();
  }

  const handleCloseRef = useRef(handleClose);
  handleCloseRef.current = handleClose;

  function dismissFromDrag() {
    handleCloseRef.current();
  }

  const panGesture = useMemo(
    () =>
      Gesture.Pan()
        .enabled(phase !== "uploading")
        .activeOffsetY(8)
        .failOffsetX([-20, 20])
        .onUpdate((e) => {
          dragY.value = Math.max(0, e.translationY);
        })
        .onEnd((e) => {
          const shouldDismiss =
            dragY.value > DISMISS_DRAG_PX || e.velocityY > DISMISS_VELOCITY;
          if (shouldDismiss) {
            scheduleOnRN(dismissFromDrag);
          } else {
            dragY.value = withTiming(0, {
              duration: 180,
              easing: Easing.out(Easing.cubic),
            });
          }
        }),
    [phase]
  );

  const backdropStyle = useAnimatedStyle(() => {
    const h = Math.max(sheetHeight.value, SHEET_HEIGHT_FALLBACK);
    const dragFade = Math.min(dragY.value / (h * 0.55), 0.9);
    return { opacity: progress.value * (1 - dragFade) };
  });

  // Slide the full sheet height (iOS-style). Do not fade the sheet itself —
  // opacity→0 at the end of a short slide was the close flash.
  const sheetStyle = useAnimatedStyle(() => {
    const h = Math.max(sheetHeight.value, SHEET_HEIGHT_FALLBACK);
    return {
      transform: [
        {
          translateY: (1 - progress.value) * h + dragY.value,
        },
      ],
    };
  });

  async function pickFile() {
    setError(null);
    const result = await DocumentPicker.getDocumentAsync({
      type: "video/*",
      copyToCacheDirectory: true,
    });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    const next: Picked = {
      uri: asset.uri,
      name: asset.name || "upload.mp4",
      mimeType: asset.mimeType || "video/mp4",
      size: typeof asset.size === "number" ? asset.size : null,
    };
    setPicked(next);
    setTitle(next.name.replace(/\.[^.]+$/, "") || "Mobile upload");
    setMethod(defaultMethod(next.size));
    setPhase("ready");
    setPct(0);
    try {
      await Haptics.selectionAsync();
    } catch {
      /* noop */
    }
  }

  async function startUpload() {
    if (!picked || phase === "uploading") return;
    setPhase("uploading");
    setError(null);
    setPct(method === "direct" ? 0 : 5);
    try {
      if (method === "direct") {
        await uploadVideoDirect({
          uri: picked.uri,
          name: picked.name,
          mimeType: picked.mimeType,
          title: title.trim() || "Direct upload",
          onProgress: (p) => setPct(p.pct),
        });
      } else {
        setPct(35);
        await uploadVideoMultipart({
          uri: picked.uri,
          name: picked.name,
          mimeType: picked.mimeType,
          title: title.trim() || "Mobile upload",
        });
        setPct(100);
      }
      setPhase("done");
      try {
        await Haptics.notificationAsync(
          Haptics.NotificationFeedbackType.Success
        );
      } catch {
        /* noop */
      }
      await onFinished();
      setTimeout(() => {
        onClose();
      }, 900);
    } catch (e) {
      setPhase("error");
      setError(e instanceof ApiError ? e.message : "Upload failed");
      try {
        await Haptics.notificationAsync(
          Haptics.NotificationFeedbackType.Error
        );
      } catch {
        /* noop */
      }
    }
  }

  return (
    <Modal
      visible={presented}
      animationType="none"
      transparent
      onRequestClose={handleClose}
      statusBarTranslucent
    >
      <GestureHandlerRootView style={styles.modalRoot}>
        <Animated.View
          pointerEvents="box-none"
          style={[styles.backdrop, backdropStyle]}
        >
          <Pressable style={StyleSheet.absoluteFill} onPress={handleClose} />
        </Animated.View>
        <Animated.View
          style={[
            styles.sheet,
            { paddingBottom: Math.max(insets.bottom, 16) + 8 },
            sheetStyle,
          ]}
          onLayout={(e) => {
            const h = e.nativeEvent.layout.height;
            if (h > 0) sheetHeight.value = h;
          }}
        >
          <GestureDetector gesture={panGesture}>
            <Animated.View
              style={styles.handleHit}
              accessibilityRole="adjustable"
              accessibilityLabel="Drag down to dismiss"
              accessibilityHint="Swipe down to close"
            >
              <View style={styles.handle} />
            </Animated.View>
          </GestureDetector>
          <View style={styles.sheetHead}>
            <View style={styles.sheetTitleRow}>
              <Ionicons name="cloud-upload" size={22} color={colors.brand} />
              <Text style={styles.sheetTitle}>Add video</Text>
            </View>
            <Pressable
              hitSlop={12}
              onPress={handleClose}
              disabled={phase === "uploading"}
              accessibilityRole="button"
              accessibilityLabel="Close"
            >
              <Ionicons
                name="close"
                size={24}
                color={
                  phase === "uploading" ? colors.textDim : colors.textMuted
                }
              />
            </Pressable>
          </View>
          <Text style={styles.sheetSub}>{stageLabel}</Text>

          {phase === "idle" ? (
            <Pressable
              onPress={pickFile}
              style={({ pressed }) => [
                styles.dropzone,
                pressed && { opacity: 0.9 },
              ]}
            >
              <View style={styles.dropIcon}>
                <Ionicons name="film-outline" size={28} color={colors.brand} />
              </View>
              <Text style={styles.dropTitle}>Choose a video</Text>
              <Text style={styles.dropBody}>
                MP4 / MOV from Files or Photos — pick, title, send.
              </Text>
              <View style={styles.dropCta}>
                <Ionicons
                  name="folder-open-outline"
                  size={18}
                  color={colors.bg}
                />
                <Text style={styles.dropCtaText}>Browse</Text>
              </View>
            </Pressable>
          ) : null}

          {picked && phase !== "idle" ? (
            <View style={styles.fileCard}>
              <View style={styles.fileIcon}>
                <Ionicons name="videocam" size={20} color={colors.brand} />
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={styles.fileName} numberOfLines={1}>
                  {picked.name}
                </Text>
                <Text style={styles.fileMeta}>{formatBytes(picked.size)}</Text>
              </View>
              {phase === "ready" || phase === "error" ? (
                <Pressable onPress={pickFile} hitSlop={8}>
                  <Text style={styles.change}>Change</Text>
                </Pressable>
              ) : null}
              {phase === "done" ? (
                <Ionicons
                  name="checkmark-circle"
                  size={22}
                  color={colors.ready}
                />
              ) : null}
            </View>
          ) : null}

          {picked && (phase === "ready" || phase === "error") ? (
            <>
              <Field
                label="Title"
                value={title}
                onChangeText={setTitle}
                autoCapitalize="sentences"
              />
              <Text style={styles.methodLabel}>Transfer</Text>
              <View style={styles.methodRow}>
                <MethodCard
                  active={method === "multipart"}
                  icon="flash-outline"
                  title="Quick"
                  body="One-shot multipart — fine for short lab clips"
                  onPress={() => setMethod("multipart")}
                />
                <MethodCard
                  active={method === "direct"}
                  icon="layers-outline"
                  title="Resumable"
                  body="Chunked /v1/uploads — better for larger files"
                  onPress={() => setMethod("direct")}
                />
              </View>
            </>
          ) : null}

          {(phase === "uploading" || phase === "done") && picked ? (
            <View style={styles.progressCard}>
              <View style={styles.progressTop}>
                <Text style={styles.progressPct}>
                  {phase === "done" ? "100%" : `${pct}%`}
                </Text>
                <Text style={styles.progressHint}>
                  {phase === "done"
                    ? "Worker will transcode → READY"
                    : method === "direct"
                      ? "Content-Range chunks"
                      : "Multipart body"}
                </Text>
              </View>
              <View style={styles.track}>
                <View
                  style={[
                    styles.fill,
                    {
                      width: `${Math.min(100, phase === "done" ? 100 : pct)}%`,
                    },
                  ]}
                />
              </View>
              <View style={styles.steps}>
                <Step
                  done={pct > 0 || phase === "done"}
                  label="Send"
                  icon="arrow-up-circle-outline"
                />
                <Step
                  done={phase === "done"}
                  label="Queue"
                  icon="git-commit-outline"
                />
                <Step done={false} label="ABR" icon="git-branch-outline" />
              </View>
            </View>
          ) : null}

          {error ? <Text style={styles.error}>{error}</Text> : null}

          {phase === "ready" || phase === "error" ? (
            <Pressable
              onPress={startUpload}
              style={({ pressed }) => [
                styles.primaryBtn,
                pressed && { opacity: 0.9 },
              ]}
            >
              <Ionicons
                name="cloud-upload-outline"
                size={20}
                color={colors.bg}
              />
              <Text style={styles.primaryBtnText}>
                {phase === "error" ? "Retry upload" : "Start upload"}
              </Text>
            </Pressable>
          ) : null}

          {phase === "idle" ? (
            <Text style={styles.footnote}>
              Tip: files over ~4 MB default to Resumable (direct upload session).
            </Text>
          ) : null}
        </Animated.View>
      </GestureHandlerRootView>
    </Modal>
  );
}

function MethodCard({
  active,
  icon,
  title,
  body,
  onPress,
}: {
  active: boolean;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  body: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.methodCard,
        active && styles.methodCardActive,
        pressed && { opacity: 0.92 },
      ]}
    >
      <Ionicons
        name={icon}
        size={20}
        color={active ? colors.brand : colors.textMuted}
      />
      <Text style={[styles.methodTitle, active && { color: colors.brand }]}>
        {title}
      </Text>
      <Text style={styles.methodBody}>{body}</Text>
    </Pressable>
  );
}

function Step({
  done,
  label,
  icon,
}: {
  done: boolean;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
}) {
  return (
    <View style={styles.step}>
      <Ionicons
        name={done ? "checkmark-circle" : icon}
        size={16}
        color={done ? colors.brand : colors.textDim}
      />
      <Text style={[styles.stepLabel, done && { color: colors.brand }]}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  modalRoot: {
    flex: 1,
    justifyContent: "flex-end",
    overflow: "hidden",
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.32)",
  },
  sheet: {
    backgroundColor: colors.bgElevated,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: 10,
    gap: 12,
    borderTopWidth: 1,
    borderColor: colors.line,
  },
  handleHit: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    marginHorizontal: -spacing.lg,
    paddingHorizontal: spacing.lg,
  },
  handle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.line,
  },
  sheetHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sheetTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  sheetTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 20,
  },
  sheetSub: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 14,
    lineHeight: 20,
    marginTop: -4,
  },
  dropzone: {
    borderWidth: 1.5,
    borderStyle: "dashed",
    borderColor: colors.brandDim,
    backgroundColor: colors.brandSoft,
    borderRadius: radii.lg,
    padding: spacing.lg,
    alignItems: "center",
    gap: 10,
  },
  dropIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.bgSoft,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
  },
  dropTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 18,
  },
  dropBody: {
    color: colors.textMuted,
    fontFamily: "DMSans_400Regular",
    fontSize: 13,
    lineHeight: 19,
    textAlign: "center",
  },
  dropCta: {
    marginTop: 4,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.brand,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: radii.md,
  },
  dropCtaText: {
    color: colors.bg,
    fontFamily: "DMSans_700Bold",
    fontSize: 15,
  },
  fileCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  fileIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: colors.brandSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  fileName: {
    color: colors.text,
    fontFamily: "DMSans_500Medium",
    fontSize: 14,
  },
  fileMeta: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  change: {
    color: colors.brand,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
  methodLabel: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  methodRow: { flexDirection: "row", gap: 10 },
  methodCard: {
    flex: 1,
    gap: 6,
    padding: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  methodCardActive: {
    borderColor: colors.brandDim,
    backgroundColor: colors.brandSoft,
  },
  methodTitle: {
    color: colors.text,
    fontFamily: "Syne_700Bold",
    fontSize: 15,
  },
  methodBody: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 11,
    lineHeight: 15,
  },
  progressCard: {
    gap: 12,
    padding: 14,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgSoft,
  },
  progressTop: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
  },
  progressPct: {
    color: colors.brand,
    fontFamily: "Syne_800ExtraBold",
    fontSize: 28,
    letterSpacing: -0.5,
  },
  progressHint: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
  },
  track: {
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.line,
    overflow: "hidden",
  },
  fill: {
    height: "100%",
    borderRadius: 4,
    backgroundColor: colors.brand,
  },
  steps: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  step: { flexDirection: "row", alignItems: "center", gap: 4 },
  stepLabel: {
    color: colors.textDim,
    fontFamily: "DMSans_500Medium",
    fontSize: 11,
  },
  primaryBtn: {
    marginTop: 4,
    minHeight: 52,
    borderRadius: radii.md,
    backgroundColor: colors.brand,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  primaryBtnText: {
    color: colors.bg,
    fontFamily: "DMSans_700Bold",
    fontSize: 16,
  },
  footnote: {
    color: colors.textDim,
    fontFamily: "DMSans_400Regular",
    fontSize: 12,
    lineHeight: 17,
    marginBottom: 4,
  },
  error: {
    color: colors.danger,
    fontFamily: "DMSans_500Medium",
    fontSize: 13,
  },
});

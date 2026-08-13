import React, { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  BackHandler,
  Pressable,
  StyleSheet,
  View,
  useWindowDimensions,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import { useReanimatedKeyboardAnimation } from "react-native-keyboard-controller";
import Animated, {
  Easing,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { scheduleOnRN } from "react-native-worklets";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useCinemaSheetHost } from "@/components/CinemaSheetHost";
import { scrollPhysics } from "@/theme/scroll";
import { colors, radii, spacing } from "@/theme/tokens";

const OPEN_MS = 300;
const CLOSE_MS = 240;
const DISMISS_DRAG_PX = 110;
const DISMISS_VELOCITY = 900;
const SHEET_HEIGHT_FALLBACK = 420;
const HANDLE_CHROME = 44;

type Props = {
  visible: boolean;
  onClose: () => void;
  children: React.ReactNode;
  /** Block backdrop tap + drag-to-dismiss (e.g. while uploading). */
  dismissEnabled?: boolean;
  /** Called after exit animation finishes and the overlay unmounts. */
  onExited?: () => void;
  sheetStyle?: StyleProp<ViewStyle>;
  fallbackHeight?: number;
};

/**
 * Bottom sheet overlaid at the app root (no RN Modal, no chrome hide).
 * Background pages stay put — only the sheet/scrim move.
 */
export function CinemaSheet({
  visible,
  onClose,
  children,
  dismissEnabled = true,
  onExited,
  sheetStyle,
  fallbackHeight = SHEET_HEIGHT_FALLBACK,
}: Props) {
  const host = useCinemaSheetHost();
  const sheetId = useId();
  const bus = useMemo(() => host.createBus(), [host]);
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const { height: kbHeight, progress: kbProgress } =
    useReanimatedKeyboardAnimation();
  const closedPad = Math.max(insets.bottom, 16) + 8;
  const [presented, setPresented] = useState(false);

  const progress = useSharedValue(0);
  const dragY = useSharedValue(0);
  const sheetHeight = useSharedValue(fallbackHeight);

  const onExitedRef = useRef(onExited);
  onExitedRef.current = onExited;
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const dismissEnabledRef = useRef(dismissEnabled);
  dismissEnabledRef.current = dismissEnabled;
  const exitPendingRef = useRef(false);
  /** Drag already animated out — skip the normal close withTiming (avoids flash). */
  const skipCloseAnimRef = useRef(false);

  function finishExit() {
    if (!exitPendingRef.current) return;
    setPresented(false);
  }

  /** After drag fling finishes off-screen: unmount without a second close anim. */
  function completeDragDismiss() {
    skipCloseAnimRef.current = true;
    exitPendingRef.current = true;
    onCloseRef.current();
    setPresented(false);
  }

  useEffect(() => {
    if (presented || visible) return;
    if (!exitPendingRef.current) return;
    exitPendingRef.current = false;
    skipCloseAnimRef.current = false;
    // Unpublish before resetting shared values — otherwise drag-dismiss
    // (sheet at translateY=h) snaps back to 0 for one frame and flashes.
    bus.publish(null);
    host.detach(sheetId);
    progress.value = 0;
    dragY.value = 0;
    onExitedRef.current?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presented, visible]);

  useEffect(() => {
    if (visible) {
      exitPendingRef.current = false;
      skipCloseAnimRef.current = false;
      progress.value = 0;
      dragY.value = 0;
      setPresented(true);
      return;
    }
    if (!presented) return;
    if (skipCloseAnimRef.current) {
      // Already off-screen from drag; presented may already be false.
      exitPendingRef.current = true;
      setPresented(false);
      return;
    }
    exitPendingRef.current = true;
    dragY.value = 0;
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

  useEffect(() => {
    if (!presented) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (!dismissEnabledRef.current) return true;
      onCloseRef.current();
      return true;
    });
    return () => sub.remove();
  }, [presented]);

  function handleClose() {
    if (!dismissEnabledRef.current) return;
    onCloseRef.current();
  }

  const panGesture = useMemo(
    () =>
      Gesture.Pan()
        .enabled(dismissEnabled)
        .activeOffsetY(8)
        .failOffsetX([-20, 20])
        .onUpdate((e) => {
          dragY.value = Math.max(0, e.translationY);
        })
        .onEnd((e) => {
          const h = Math.max(sheetHeight.value, fallbackHeight);
          const shouldDismiss =
            dragY.value > DISMISS_DRAG_PX || e.velocityY > DISMISS_VELOCITY;
          if (shouldDismiss) {
            // Fling sheet + scrim off together (do NOT snap dragY→0 — that
            // desynced the backdrop and flashed after close).
            const hideY = h - kbHeight.value;
            const dist = Math.max(24, hideY - dragY.value);
            const dur = Math.min(
              CLOSE_MS,
              Math.max(160, (dist / Math.max(e.velocityY, 900)) * 1000)
            );
            dragY.value = withTiming(
              hideY,
              { duration: dur, easing: Easing.in(Easing.cubic) },
              (finished) => {
                if (finished) scheduleOnRN(completeDragDismiss);
              }
            );
          } else {
            dragY.value = withTiming(0, {
              duration: 180,
              easing: Easing.out(Easing.cubic),
            });
          }
        }),
    [dismissEnabled, fallbackHeight]
  );

  // Scrim tracks progress and drag in one opacity so drag-dismiss fades with the sheet.
  const backdropStyle = useAnimatedStyle(() => {
    const h = Math.max(sheetHeight.value, fallbackHeight);
    const dragFade = Math.min(dragY.value / h, 1);
    return { opacity: progress.value * (1 - dragFade) };
  });

  const slideStyle = useAnimatedStyle(() => {
    const h = Math.max(sheetHeight.value, fallbackHeight);
    const kb = kbHeight.value;
    // kb is 0 closed, negative when open. Mix it with progress so close/drag
    // still travel fully off-screen.
    return {
      transform: [
        {
          translateY: (1 - progress.value) * (h - kb) + dragY.value + kb,
        },
      ],
      maxHeight: Math.max(160, windowHeight + kb),
      paddingBottom: interpolate(kbProgress.value, [0, 1], [closedPad, 8]),
    };
  });

  const bodyScrollStyle = useAnimatedStyle(() => {
    const pad = interpolate(kbProgress.value, [0, 1], [closedPad, 8]);
    return {
      maxHeight: Math.max(
        120,
        windowHeight + kbHeight.value - pad - HANDLE_CHROME
      ),
    };
  });

  useLayoutEffect(() => {
    if (!presented) return;
    host.attach(sheetId, bus);
  }, [presented, host, sheetId, bus]);

  useLayoutEffect(() => {
    if (!presented) return;

    bus.publish(
      <View style={styles.modalRoot} pointerEvents="box-none">
        <Animated.View
          pointerEvents="box-none"
          style={[styles.backdrop, backdropStyle]}
        >
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={handleClose}
            disabled={!dismissEnabled}
          />
        </Animated.View>
        <Animated.View
          style={[styles.sheet, sheetStyle, slideStyle]}
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
          <Animated.ScrollView
            keyboardShouldPersistTaps="handled"
            nestedScrollEnabled
            showsVerticalScrollIndicator={false}
            bounces={scrollPhysics.bounces}
            alwaysBounceVertical={scrollPhysics.alwaysBounceVertical}
            overScrollMode={scrollPhysics.overScrollMode}
            style={bodyScrollStyle}
            contentContainerStyle={styles.sheetBody}
          >
            {children}
          </Animated.ScrollView>
        </Animated.View>
      </View>
    );
    // Animated styles read shared values on the UI thread; omitting them
    // avoids republishing every render (which remounts the overlay tree).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presented, children, dismissEnabled, insets.bottom, sheetStyle, panGesture, bus]);

  useEffect(() => {
    return () => {
      bus.publish(null);
      host.detach(sheetId);
    };
  }, [bus, host, sheetId]);

  return null;
}

const styles = StyleSheet.create({
  modalRoot: {
    ...StyleSheet.absoluteFillObject,
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
    overflow: "hidden",
    width: "100%",
  },
  sheetBody: {
    gap: 12,
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
});

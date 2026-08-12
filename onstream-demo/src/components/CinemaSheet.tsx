import React, { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  BackHandler,
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { scheduleOnRN } from "react-native-worklets";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useCinemaSheetHost } from "@/components/CinemaSheetHost";
import { colors, radii, spacing } from "@/theme/tokens";

const OPEN_MS = 300;
const CLOSE_MS = 240;
const DISMISS_DRAG_PX = 110;
const DISMISS_VELOCITY = 900;
const SHEET_HEIGHT_FALLBACK = 420;

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

  function finishExit() {
    if (!exitPendingRef.current) return;
    setPresented(false);
  }

  useEffect(() => {
    if (presented || visible) return;
    if (!exitPendingRef.current) return;
    exitPendingRef.current = false;
    progress.value = 0;
    dragY.value = 0;
    bus.publish(null);
    host.detach(sheetId);
    onExitedRef.current?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presented, visible]);

  useEffect(() => {
    if (visible) {
      exitPendingRef.current = false;
      progress.value = 0;
      dragY.value = 0;
      setPresented(true);
      return;
    }
    if (!presented) return;
    exitPendingRef.current = true;
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

  function dismissFromDrag() {
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
          const shouldDismiss =
            dragY.value > DISMISS_DRAG_PX || e.velocityY > DISMISS_VELOCITY;
          if (shouldDismiss) {
            const h = Math.max(sheetHeight.value, fallbackHeight);
            const visual = Math.min(Math.max(0, dragY.value), h);
            dragY.value = 0;
            progress.value = Math.max(0, 1 - visual / h);
            scheduleOnRN(dismissFromDrag);
          } else {
            dragY.value = withTiming(0, {
              duration: 180,
              easing: Easing.out(Easing.cubic),
            });
          }
        }),
    [dismissEnabled, fallbackHeight]
  );

  const backdropStyle = useAnimatedStyle(() => {
    const h = Math.max(sheetHeight.value, fallbackHeight);
    const dragFade = Math.min(dragY.value / (h * 0.55), 0.9);
    return { opacity: progress.value * (1 - dragFade) };
  });

  const slideStyle = useAnimatedStyle(() => {
    const h = Math.max(sheetHeight.value, fallbackHeight);
    return {
      transform: [
        {
          translateY: (1 - progress.value) * h + dragY.value,
        },
      ],
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
          style={[
            styles.sheet,
            { paddingBottom: Math.max(insets.bottom, 16) + 8 },
            sheetStyle,
            slideStyle,
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
          {children}
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

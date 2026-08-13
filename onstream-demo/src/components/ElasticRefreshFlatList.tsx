import { Ionicons } from "@expo/vector-icons";
import { onlineManager } from "@tanstack/react-query";
import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  View,
  type FlatListProps,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  Extrapolation,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { scheduleOnRN } from "react-native-worklets";

import { scrollPhysics } from "@/theme/scroll";
import { colors } from "@/theme/tokens";

const PULL_THRESHOLD = 100;
const PULL_MAX = 150;
/** Touch must begin near the top — not mid/bottom of the list. */
const TOP_TOUCH_FRACTION = 0.28;
/** Finger travel before the pan claims the gesture (scroll wins below this). */
const ACTIVATE_DY = 18;
/**
 * Pull distance = finger * GAIN (then extra damp past threshold).
 * Gain &lt; 1 so a casual tug stays under threshold; ~160px finger ≈ release.
 */
const PULL_GAIN = 0.62;
/** Never leave the spinner up if a refetch hangs (offline / dead socket). */
const REFRESH_BUDGET_MS = 10_000;

function rubber(dy: number) {
  "worklet";
  const t = Math.max(0, dy) * PULL_GAIN;
  if (t <= PULL_THRESHOLD) return t;
  const over = t - PULL_THRESHOLD;
  return Math.min(PULL_MAX, PULL_THRESHOLD + over * 0.3);
}

type Props<ItemT> = Omit<FlatListProps<ItemT>, "refreshControl"> & {
  onRefresh: () => void | Promise<void>;
  refreshing?: boolean;
};

/**
 * FlatList with popular-app refresh UX:
 * rubber-band from the top → refresh only after a pull threshold.
 *
 * Native RefreshControl is unused: on short Android lists scrollY stays 0, so a
 * downward drag that starts at the bottom still fires refresh.
 *
 * Elastic idea akin to https://css-tricks.com/elastic-overflow-scrolling/
 * (CSS scroll-snap is web-only; RN uses a top-gated pan).
 */
export function ElasticRefreshFlatList<ItemT>({
  onRefresh,
  refreshing: refreshingProp,
  onScroll,
  ListHeaderComponent,
  style,
  ...rest
}: Props<ItemT>) {
  const [internalRefreshing, setInternalRefreshing] = useState(false);
  const refreshing = refreshingProp ?? internalRefreshing;

  const pull = useSharedValue(0);
  const atTop = useSharedValue(true);
  const listH = useSharedValue(1);
  const touchStartY = useSharedValue(0);
  const refreshingSV = useSharedValue(false);

  const runRefresh = useCallback(async () => {
    setInternalRefreshing(true);
    refreshingSV.value = true;
    try {
      if (!onlineManager.isOnline()) return;
      await Promise.race([
        Promise.resolve(onRefresh()),
        new Promise<void>((resolve) => {
          setTimeout(resolve, REFRESH_BUDGET_MS);
        }),
      ]);
    } catch {
      // Query / banner own the error. Always drop the spinner.
    } finally {
      setInternalRefreshing(false);
      refreshingSV.value = false;
      pull.value = withSpring(0, { damping: 18, stiffness: 180 });
    }
  }, [onRefresh, pull, refreshingSV]);

  const pan = Gesture.Pan()
    .manualActivation(true)
    .onTouchesDown((e) => {
      const t = e.allTouches[0];
      touchStartY.value = t?.y ?? 0;
    })
    .onTouchesMove((e, state) => {
      if (refreshingSV.value) {
        state.fail();
        return;
      }
      if (!atTop.value) {
        state.fail();
        return;
      }
      // Finger must start near the top of the list viewport.
      if (touchStartY.value > listH.value * TOP_TOUCH_FRACTION) {
        state.fail();
        return;
      }
      const t = e.allTouches[0];
      const dy = (t?.y ?? 0) - touchStartY.value;
      if (dy > ACTIVATE_DY) {
        state.activate();
      } else if (dy < -8) {
        state.fail();
      }
    })
    .onUpdate((e) => {
      if (e.translationY <= 0) {
        pull.value = 0;
        return;
      }
      pull.value = rubber(e.translationY);
    })
    .onEnd(() => {
      if (pull.value >= PULL_THRESHOLD) {
        pull.value = withTiming(56, { duration: 120 });
        scheduleOnRN(runRefresh);
      } else {
        pull.value = withSpring(0, { damping: 18, stiffness: 200 });
      }
    })
    .onFinalize((_e, success) => {
      if (!success && pull.value > 0 && !refreshingSV.value) {
        pull.value = withSpring(0, { damping: 18, stiffness: 200 });
      }
    });

  const handleScroll = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      atTop.value = e.nativeEvent.contentOffset.y <= 1;
      onScroll?.(e);
    },
    [atTop, onScroll]
  );

  const listShiftStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: pull.value }],
  }));

  const indicatorStyle = useAnimatedStyle(() => {
    const h = interpolate(
      pull.value,
      [0, PULL_THRESHOLD, PULL_MAX],
      [0, 56, 64],
      Extrapolation.CLAMP
    );
    const opacity = interpolate(
      pull.value,
      [0, 24, PULL_THRESHOLD],
      [0, 0.55, 1],
      Extrapolation.CLAMP
    );
    return { height: h, opacity };
  });

  const arrowStyle = useAnimatedStyle(() => ({
    transform: [
      {
        rotate: `${interpolate(
          pull.value,
          [0, PULL_THRESHOLD, PULL_MAX],
          [0, 360, 420],
          Extrapolation.CLAMP
        )}deg`,
      },
    ],
  }));

  const ringStyle = useAnimatedStyle(() => {
    const ready = pull.value >= PULL_THRESHOLD;
    return {
      borderColor: ready ? colors.brand : colors.brandDim,
      transform: [
        {
          scale: interpolate(
            pull.value,
            [0, 20, PULL_THRESHOLD],
            [0.7, 0.9, 1],
            Extrapolation.CLAMP
          ),
        },
      ],
    };
  });

  const pullLabelStyle = useAnimatedStyle(() => ({
    opacity: pull.value < PULL_THRESHOLD ? 1 : 0,
  }));

  const releaseLabelStyle = useAnimatedStyle(() => ({
    opacity: pull.value >= PULL_THRESHOLD ? 1 : 0,
  }));

  const header = (
    <View>
      <Animated.View style={[styles.indicatorWrap, indicatorStyle]}>
        {refreshing ? (
          <View style={styles.circle}>
            <ActivityIndicator color={colors.brand} />
          </View>
        ) : (
          <View style={styles.indicatorInner}>
            <Animated.View style={[styles.circle, ringStyle]}>
              <Animated.View style={arrowStyle}>
                <Ionicons name="refresh" size={20} color={colors.brand} />
              </Animated.View>
            </Animated.View>
            <View style={styles.labelStack}>
              <Animated.Text style={[styles.hint, pullLabelStyle]}>
                Pull to refresh
              </Animated.Text>
              <Animated.Text
                style={[styles.hint, styles.labelAbs, releaseLabelStyle]}
              >
                Release to refresh
              </Animated.Text>
            </View>
          </View>
        )}
      </Animated.View>
      {ListHeaderComponent != null &&
      typeof ListHeaderComponent !== "function" ? (
        ListHeaderComponent
      ) : null}
    </View>
  );

  return (
    <GestureDetector gesture={pan}>
      <Animated.View
        style={[styles.flex, listShiftStyle]}
        onLayout={(e) => {
          listH.value = e.nativeEvent.layout.height || 1;
        }}
      >
        <FlatList<ItemT>
          {...rest}
          {...scrollPhysics}
          style={[styles.flex, style]}
          onScroll={handleScroll}
          scrollEventThrottle={16}
          ListHeaderComponent={header}
        />
      </Animated.View>
    </GestureDetector>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  indicatorWrap: {
    alignItems: "center",
    justifyContent: "flex-end",
    overflow: "hidden",
    paddingBottom: 6,
  },
  indicatorInner: {
    alignItems: "center",
    gap: 6,
  },
  circle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 2,
    borderColor: colors.brandDim,
    backgroundColor: colors.brandSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  labelStack: {
    height: 16,
    justifyContent: "center",
    minWidth: 120,
    alignItems: "center",
  },
  labelAbs: {
    position: "absolute",
  },
  hint: {
    color: colors.textMuted,
    fontFamily: "DMSans_500Medium",
    fontSize: 12,
  },
});

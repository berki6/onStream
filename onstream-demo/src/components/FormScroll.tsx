import type { ReactNode } from "react";
import { StyleSheet, type StyleProp, type ViewStyle } from "react-native";
import {
  KeyboardAwareScrollView,
  type KeyboardAwareScrollViewProps,
} from "react-native-keyboard-controller";

import { scrollPhysics } from "@/theme/scroll";

type FormScrollProps = Omit<KeyboardAwareScrollViewProps, "children"> & {
  children: ReactNode;
  contentContainerStyle?: StyleProp<ViewStyle>;
  /** Vertically center content when keyboard is closed (auth-style screens). */
  centered?: boolean;
  /**
   * When true (default), stretch with flex:1 for full screens.
   * Set false in sheets — flex:1 + content-sized parent collapses to 0.
   */
  fill?: boolean;
};

/**
 * Canonical form scroll. Auto-scrolls the focused field above the keyboard
 * on iOS and Android. Prefer over RN KeyboardAvoidingView + ScrollView.
 */
export function FormScroll({
  children,
  centered = false,
  fill = true,
  bottomOffset = 24,
  contentContainerStyle,
  keyboardShouldPersistTaps = "handled",
  showsVerticalScrollIndicator = false,
  bounces = scrollPhysics.bounces,
  alwaysBounceVertical = scrollPhysics.alwaysBounceVertical,
  overScrollMode = scrollPhysics.overScrollMode,
  style,
  ...rest
}: FormScrollProps) {
  return (
    <KeyboardAwareScrollView
      style={[fill ? styles.fill : undefined, style]}
      bottomOffset={bottomOffset}
      keyboardShouldPersistTaps={keyboardShouldPersistTaps}
      showsVerticalScrollIndicator={showsVerticalScrollIndicator}
      bounces={bounces}
      alwaysBounceVertical={alwaysBounceVertical}
      overScrollMode={overScrollMode}
      contentContainerStyle={[
        centered ? styles.centered : undefined,
        contentContainerStyle,
      ]}
      {...rest}
    >
      {children}
    </KeyboardAwareScrollView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  centered: {
    flexGrow: 1,
    justifyContent: "center",
  },
});

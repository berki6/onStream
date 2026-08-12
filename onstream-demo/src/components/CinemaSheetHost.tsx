import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactElement,
  type ReactNode,
} from "react";
import { StyleSheet, View } from "react-native";

type SheetBus = {
  subscribe: (listener: () => void) => () => void;
  getVersion: () => number;
  getElement: () => ReactElement | null;
  publish: (element: ReactElement | null) => void;
};

function createSheetBus(): SheetBus {
  let version = 0;
  let element: ReactElement | null = null;
  const listeners = new Set<() => void>();
  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getVersion: () => version,
    getElement: () => element,
    publish(next) {
      element = next;
      version += 1;
      listeners.forEach((l) => l());
    },
  };
}

type HostApi = {
  attach: (id: string, bus: SheetBus) => void;
  detach: (id: string) => void;
  createBus: () => SheetBus;
};

const CinemaSheetHostContext = createContext<HostApi | null>(null);

function SheetOutlet({ bus }: { bus: SheetBus }) {
  const version = useSyncExternalStore(
    bus.subscribe,
    bus.getVersion,
    bus.getVersion
  );
  // version read forces re-render when publish() runs
  void version;
  return bus.getElement();
}

/**
 * Root host: sheets overlay the whole app window without RN Modal
 * (keeps Android nav bar) and without resizing tab/header chrome.
 */
export function CinemaSheetProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<string[]>([]);
  const busesRef = useRef(new Map<string, SheetBus>());

  const attach = useCallback((id: string, bus: SheetBus) => {
    busesRef.current.set(id, bus);
    setIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
  }, []);

  const detach = useCallback((id: string) => {
    busesRef.current.delete(id);
    setIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : prev));
  }, []);

  const api = useMemo<HostApi>(
    () => ({
      attach,
      detach,
      createBus: createSheetBus,
    }),
    [attach, detach]
  );

  return (
    <CinemaSheetHostContext.Provider value={api}>
      {children}
      {ids.length > 0 ? (
        <View pointerEvents="box-none" style={styles.host} collapsable={false}>
          {ids.map((id) => {
            const bus = busesRef.current.get(id);
            if (!bus) return null;
            return (
              <View
                key={id}
                pointerEvents="box-none"
                style={StyleSheet.absoluteFill}
                collapsable={false}
              >
                <SheetOutlet bus={bus} />
              </View>
            );
          })}
        </View>
      ) : null}
    </CinemaSheetHostContext.Provider>
  );
}

export function useCinemaSheetHost(): HostApi {
  const ctx = useContext(CinemaSheetHostContext);
  if (!ctx) {
    throw new Error("CinemaSheet must be used inside CinemaSheetProvider");
  }
  return ctx;
}

const styles = StyleSheet.create({
  host: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 1000,
    elevation: 1000,
  },
});

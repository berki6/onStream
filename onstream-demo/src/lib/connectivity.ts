import { useSyncExternalStore } from "react";

export type ConnectivitySnapshot = {
  deviceOnline: boolean;
  apiReachable: boolean | null;
};

let snap: ConnectivitySnapshot = {
  deviceOnline: true,
  apiReachable: null,
};

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((fn) => fn());
}

export function getConnectivity(): ConnectivitySnapshot {
  return snap;
}

export function subscribeConnectivity(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function setDeviceOnline(online: boolean) {
  if (snap.deviceOnline === online) return;
  snap = {
    deviceOnline: online,
    apiReachable: online ? null : false,
  };
  emit();
}

export function reportApiResult(ok: boolean) {
  if (ok) {
    if (snap.apiReachable === true) return;
    snap = { ...snap, apiReachable: true };
    emit();
    return;
  }
  if (!snap.deviceOnline) return;
  if (snap.apiReachable === false) return;
  snap = { ...snap, apiReachable: false };
  emit();
}

export function useConnectivity(): ConnectivitySnapshot {
  return useSyncExternalStore(
    subscribeConnectivity,
    getConnectivity,
    getConnectivity
  );
}

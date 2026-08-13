export type ToastTone = "success" | "error" | "info";

export type ToastMessage = {
  id: number;
  text: string;
  tone: ToastTone;
  durationMs: number;
};

const DURATION: Record<ToastTone, number> = {
  success: 2800,
  info: 4000,
  error: 4500,
};

let current: ToastMessage | null = null;
let seq = 0;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((fn) => fn());
}

export function getToast(): ToastMessage | null {
  return current;
}

export function subscribeToast(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function dismissToast() {
  if (!current) return;
  current = null;
  emit();
}

function show(tone: ToastTone, text: string, durationMs?: number) {
  const trimmed = text.trim();
  if (!trimmed) return;
  seq += 1;
  current = {
    id: seq,
    text: trimmed,
    tone,
    durationMs: durationMs ?? DURATION[tone],
  };
  emit();
}

export const toast = {
  success(text: string, durationMs?: number) {
    show("success", text, durationMs);
  },
  error(text: string, durationMs?: number) {
    show("error", text, durationMs);
  },
  info(text: string, durationMs?: number) {
    show("info", text, durationMs);
  },
  dismiss: dismissToast,
};

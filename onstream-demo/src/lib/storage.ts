import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const memory = new Map<string, string>();

async function setItem(key: string, value: string) {
  if (Platform.OS === "web") {
    memory.set(key, value);
    try {
      localStorage.setItem(key, value);
    } catch {
      /* ignore */
    }
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function getItem(key: string): Promise<string | null> {
  if (Platform.OS === "web") {
    try {
      return localStorage.getItem(key) ?? memory.get(key) ?? null;
    } catch {
      return memory.get(key) ?? null;
    }
  }
  return SecureStore.getItemAsync(key);
}

async function deleteItem(key: string) {
  if (Platform.OS === "web") {
    memory.delete(key);
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

const KEYS = {
  access: "onstream.access_token",
  refresh: "onstream.refresh_token",
  apiBase: "onstream.api_base",
  username: "onstream.username",
} as const;

export const storage = {
  setAccessToken: (v: string) => setItem(KEYS.access, v),
  getAccessToken: () => getItem(KEYS.access),
  setRefreshToken: (v: string) => setItem(KEYS.refresh, v),
  getRefreshToken: () => getItem(KEYS.refresh),
  setApiBase: (v: string) => setItem(KEYS.apiBase, v),
  getApiBase: () => getItem(KEYS.apiBase),
  setUsername: (v: string) => setItem(KEYS.username, v),
  getUsername: () => getItem(KEYS.username),
  clearSession: async () => {
    await Promise.all([
      deleteItem(KEYS.access),
      deleteItem(KEYS.refresh),
      deleteItem(KEYS.username),
    ]);
  },
};

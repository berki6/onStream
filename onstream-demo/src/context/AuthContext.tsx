import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { loginUser, logoutUser, registerUser } from "../api/auth";
import { initApiBase } from "../api/client";
import { storage } from "../lib/storage";

type AuthState = {
  ready: boolean;
  signedIn: boolean;
  username: string | null;
  signIn: (username: string, password: string) => Promise<void>;
  signUp: (input: {
    username: string;
    email: string;
    password: string;
  }) => Promise<void>;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Single atomic boot state so we never paint "ready && !signedIn" for a
  // stored session (that race flashes the login screen).
  const [ready, setReady] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [username, setUsername] = useState<string | null>(null);

  const refreshSession = useCallback(async () => {
    await initApiBase();
    const token = await storage.getAccessToken();
    const name = await storage.getUsername();
    setSignedIn(Boolean(token));
    setUsername(name);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refreshSession();
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshSession]);

  const signIn = useCallback(async (user: string, password: string) => {
    await loginUser(user, password);
    setSignedIn(true);
    setUsername(user);
  }, []);

  const signUp = useCallback(
    async (input: { username: string; email: string; password: string }) => {
      await registerUser(input);
      await loginUser(input.username, input.password);
      setSignedIn(true);
      setUsername(input.username);
    },
    []
  );

  const signOut = useCallback(async () => {
    await logoutUser();
    setSignedIn(false);
    setUsername(null);
  }, []);

  const value = useMemo(
    () => ({
      ready,
      signedIn,
      username,
      signIn,
      signUp,
      signOut,
      refreshSession,
    }),
    [ready, signedIn, username, signIn, signUp, signOut, refreshSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { loginUser, logoutUser, registerUser } from "../api/auth";
import { initApiBase, tryRefreshAccessToken } from "../api/client";
import { storage } from "../lib/storage";

type SessionSnapshot = {
  /** False until SecureStore (+ optional refresh) has finished once. */
  ready: boolean;
  signedIn: boolean;
  username: string | null;
};

type AuthState = SessionSnapshot & {
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

const BOOT: SessionSnapshot = {
  ready: false,
  signedIn: false,
  username: null,
};

async function readSessionFromStorage(): Promise<
  Omit<SessionSnapshot, "ready">
> {
  await initApiBase();
  let access = await storage.getAccessToken();
  const refresh = await storage.getRefreshToken();
  const username = await storage.getUsername();

  // Access missing but refresh present → one hydrate attempt (expired access).
  if (!access && refresh) {
    access = await tryRefreshAccessToken();
    if (!access) {
      await storage.clearSession();
      return { signedIn: false, username: null };
    }
  }

  if (!access) {
    return { signedIn: false, username: null };
  }

  return { signedIn: true, username };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionSnapshot>(BOOT);

  const refreshSession = useCallback(async () => {
    const next = await readSessionFromStorage();
    setSession({ ready: true, ...next });
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await readSessionFromStorage();
        if (!cancelled) setSession({ ready: true, ...next });
      } catch {
        if (!cancelled) {
          setSession({ ready: true, signedIn: false, username: null });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (user: string, password: string) => {
    await loginUser(user, password);
    setSession({ ready: true, signedIn: true, username: user });
  }, []);

  const signUp = useCallback(
    async (input: { username: string; email: string; password: string }) => {
      await registerUser(input);
      await loginUser(input.username, input.password);
      setSession({
        ready: true,
        signedIn: true,
        username: input.username,
      });
    },
    []
  );

  const signOut = useCallback(async () => {
    await logoutUser();
    setSession({ ready: true, signedIn: false, username: null });
  }, []);

  const value = useMemo(
    () => ({
      ready: session.ready,
      signedIn: session.signedIn,
      username: session.username,
      signIn,
      signUp,
      signOut,
      refreshSession,
    }),
    [session, signIn, signUp, signOut, refreshSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

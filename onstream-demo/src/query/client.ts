import { AppState, Platform } from "react-native";
import { focusManager, QueryClient } from "@tanstack/react-query";

import { ApiError, isNetworkError } from "@/api/client";

if (Platform.OS !== "web") {
  AppState.addEventListener("change", (status) => {
    focusManager.setFocused(status === "active");
  });
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      gcTime: 1000 * 60 * 30,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
      retry: (count, error) => {
        if (isNetworkError(error)) return count < 1;
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
          return false;
        }
        return count < 2;
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
    },
    mutations: {
      retry: 0,
    },
  },
});

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Dashboard from "./components/Dashboard";
import AuthPage from "./components/AuthPage";
import { AuthResponse, logout } from "./api/client";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchInterval: 30_000,
      refetchOnWindowFocus: false,
      refetchIntervalInBackground: false,
      retry: 1,
    },
  },
});

function storedUser() {
  try { return JSON.parse(localStorage.getItem("user") ?? "null"); } catch { return null; }
}

export default function App() {
  const [authed, setAuthed] = useState(() => !!localStorage.getItem("access_token"));
  const [user, setUser] = useState<AuthResponse["user"]>(() => storedUser());

  function handleAuth(res: AuthResponse) {
    localStorage.setItem("access_token", res.access_token);
    localStorage.setItem("refresh_token", res.refresh_token);
    if (res.user) localStorage.setItem("user", JSON.stringify(res.user));
    setUser(res.user ?? undefined);
    setAuthed(true);
  }

  async function handleLogout() {
    await logout();
    localStorage.removeItem("user");
    queryClient.clear();
    setUser(undefined);
    setAuthed(false);
  }

  return (
    <QueryClientProvider client={queryClient}>
      {authed ? (
        <Dashboard onLogout={handleLogout} user={user} />
      ) : (
        <AuthPage onAuth={handleAuth} />
      )}
    </QueryClientProvider>
  );
}

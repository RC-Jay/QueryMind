"use client";
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { User } from "./types";
import api from "./api";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ force_password_change: boolean }>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => ({ force_password_change: false }),
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Use raw axios (NOT the interceptor-enhanced `api`) so a 401 here
    // doesn't trigger the retry interceptor and cause an infinite loop.
    (async () => {
      try {
        const { data } = await axios.post(
          `${API_BASE}/api/auth/refresh`,
          {},
          { withCredentials: true }
        );
        sessionStorage.setItem("access_token", data.access_token);
        // Fetch full user profile using the enhanced client (token is now set)
        const userRes = await api.get("/api/auth/me");
        setUser(userRes.data);
      } catch {
        // No valid refresh token — user needs to log in. This is expected on
        // first visit or after session expiry. Just clear storage silently.
        sessionStorage.removeItem("access_token");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const login = async (email: string, password: string) => {
    const { data } = await api.post("/api/auth/login", { email, password });
    sessionStorage.setItem("access_token", data.access_token);
    setUser(data.user);
    return { force_password_change: data.user.force_password_change };
  };

  const logout = async () => {
    await api.post("/api/auth/logout").catch(() => {});
    sessionStorage.removeItem("access_token");
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

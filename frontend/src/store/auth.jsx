import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, TOKEN_KEY } from "@/services/api";

const AuthCtx = createContext(null);

const USER_KEY = "jurnalmap.user";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || null);
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(!!token && !user);

  // On mount, if we have a token, verify by fetching /auth/me
  useEffect(() => {
    let ignore = false;
    if (!token) {
      setLoading(false);
      return () => {};
    }
    setLoading(true);
    api
      .me()
      .then((u) => {
        if (ignore) return;
        setUser(u);
        localStorage.setItem(USER_KEY, JSON.stringify(u));
      })
      .catch(() => {
        if (ignore) return;
        // Token no longer valid — clear it. The api interceptor will redirect too.
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        setToken(null);
        setUser(null);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const persistLogin = useCallback((data) => {
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const login = useCallback(async (username, password) => {
    const data = await api.login(username, password);
    persistLogin(data);
    return data;
  }, [persistLogin]);

  const register = useCallback(async (payload) => {
    const data = await api.register(payload);
    persistLogin(data);
    return data;
  }, [persistLogin]);

  const forgotPassword = useCallback(async (payload) => {
    const data = await api.forgotPassword(payload);
    persistLogin(data);
    return data;
  }, [persistLogin]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthCtx.Provider value={{ token, user, loading, login, register, forgotPassword, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

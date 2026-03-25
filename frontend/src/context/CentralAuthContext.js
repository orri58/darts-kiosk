import { createContext, useContext, useState, useCallback } from "react";

const API = process.env.REACT_APP_BACKEND_URL;

const CentralAuthContext = createContext(null);

export function CentralAuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem("central_token"));

  const login = useCallback(async (username, password) => {
    const res = await fetch(`${API}/api/central/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login fehlgeschlagen");
    }
    const data = await res.json();
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem("central_token", data.access_token);
    return data;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("central_token");
  }, []);

  const centralFetch = useCallback(
    async (path, opts = {}) => {
      const res = await fetch(`${API}/api/central/${path.replace(/^\//, "")}`, {
        ...opts,
        headers: {
          ...(opts.headers || {}),
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.status === 401) {
        logout();
        throw new Error("Session abgelaufen");
      }
      return res;
    },
    [token, logout]
  );

  return (
    <CentralAuthContext.Provider
      value={{ user, token, login, logout, centralFetch, isAuthenticated: !!token }}
    >
      {children}
    </CentralAuthContext.Provider>
  );
}

export function useCentralAuth() {
  const ctx = useContext(CentralAuthContext);
  if (!ctx) throw new Error("useCentralAuth must be used within CentralAuthProvider");
  return ctx;
}

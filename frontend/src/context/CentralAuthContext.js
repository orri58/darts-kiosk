import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const API = process.env.REACT_APP_BACKEND_URL;
const TOKEN_KEY = 'central_token';
const SCOPE_KEY = 'central_scope';

const ROLE_LEVEL = {
  staff: 1,
  owner: 2,
  installer: 3,
  superadmin: 4,
};

const CentralAuthContext = createContext(null);

function normalizeUser(raw) {
  if (!raw) return null;
  const role = raw.role || 'staff';
  const isSuperadmin = role === 'superadmin' || !!raw.is_superadmin;
  return {
    id: raw.id,
    username: raw.username,
    display_name: raw.display_name || raw.username,
    role,
    is_superadmin: isSuperadmin,
    allowed_customer_ids: raw.allowed_customer_ids || [],
  };
}

function safeReadJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function CentralAuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => !!localStorage.getItem(TOKEN_KEY));
  const [scope, setScope] = useState(() => safeReadJson(SCOPE_KEY, { customerId: null, locationId: null, deviceId: null }));

  const apiBase = useMemo(() => `${API}/api`, []);
  const authHeaders = useMemo(() => token ? { Authorization: `Bearer ${token}` } : {}, [token]);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setLoading(false);
    localStorage.removeItem(TOKEN_KEY);
  }, []);

  const fetchMe = useCallback(async (activeToken) => {
    if (!activeToken) return null;
    const res = await fetch(`${apiBase}/auth/me`, {
      headers: { Authorization: `Bearer ${activeToken}` },
    });
    if (!res.ok) {
      throw new Error(res.status === 401 ? 'Session abgelaufen' : `HTTP ${res.status}`);
    }
    return normalizeUser(await res.json());
  }, [apiBase]);

  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setLoading(false);
      setUser(null);
      return;
    }
    setLoading(true);
    fetchMe(token)
      .then((nextUser) => {
        if (!cancelled) setUser(nextUser);
      })
      .catch(() => {
        if (!cancelled) logout();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [token, fetchMe, logout]);

  useEffect(() => {
    localStorage.setItem(SCOPE_KEY, JSON.stringify(scope));
  }, [scope]);

  const login = useCallback(async (username, password) => {
    const res = await fetch(`${apiBase}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const error = new Error(data.detail || 'Login fehlgeschlagen');
      error.response = { status: res.status, data };
      throw error;
    }
    const nextUser = normalizeUser(data.user);
    setToken(data.access_token);
    setUser(nextUser);
    setLoading(false);
    localStorage.setItem(TOKEN_KEY, data.access_token);
    return { ...data, user: nextUser };
  }, [apiBase]);

  const centralFetch = useCallback(async (path, opts = {}) => {
    const res = await fetch(`${apiBase}/${String(path).replace(/^\//, '')}`, {
      ...opts,
      headers: {
        ...(opts.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (res.status === 401) {
      logout();
      throw new Error('Session abgelaufen');
    }
    return res;
  }, [apiBase, token, logout]);

  const updateScope = useCallback((nextScope) => {
    setScope({
      customerId: nextScope.customerId || null,
      locationId: nextScope.locationId || null,
      deviceId: nextScope.deviceId || null,
    });
  }, []);

  const roleLevel = ROLE_LEVEL[user?.role] || 0;
  const isAuthenticated = !!token;
  const isSuperadmin = !!user?.is_superadmin;
  const canManage = roleLevel >= ROLE_LEVEL.owner;
  const canManageStaff = roleLevel >= ROLE_LEVEL.owner;
  const canReviewRemoteActions = roleLevel >= ROLE_LEVEL.installer;
  const roleLabel = user?.role ? user.role[0].toUpperCase() + user.role.slice(1) : 'Nicht angemeldet';

  return (
    <CentralAuthContext.Provider
      value={{
        user,
        token,
        loading,
        apiBase,
        authHeaders,
        scope,
        login,
        logout,
        fetchMe,
        centralFetch,
        updateScope,
        isAuthenticated,
        isSuperadmin,
        canManage,
        canManageStaff,
        canReviewRemoteActions,
        roleLabel,
      }}
    >
      {children}
    </CentralAuthContext.Provider>
  );
}

export function useCentralAuth() {
  const ctx = useContext(CentralAuthContext);
  if (!ctx) throw new Error('useCentralAuth must be used within CentralAuthProvider');
  return ctx;
}

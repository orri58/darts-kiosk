import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const CENTRAL_API = `${process.env.REACT_APP_BACKEND_URL}/api/central`;
const STORAGE_KEY = 'central_token';
const SCOPE_KEY = 'central_scope';

const CentralAuthContext = createContext(null);

const ROLE_LABELS = {
  superadmin: 'Super-Administrator',
  installer: 'Aufsteller / Installer',
  owner: 'Geschäftsinhaber',
  staff: 'Mitarbeiter',
};

export function CentralAuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem(STORAGE_KEY));
  const [loading, setLoading] = useState(true);
  // Scope state: { customerId, locationId, deviceId }
  const [scope, setScope] = useState(() => {
    try { return JSON.parse(localStorage.getItem(SCOPE_KEY)) || {}; } catch { return {}; }
  });

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    const verify = async () => {
      try {
        const res = await axios.get(`${CENTRAL_API}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setUser(res.data);
      } catch {
        localStorage.removeItem(STORAGE_KEY);
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    verify();
  }, [token]);

  const login = useCallback(async (username, password) => {
    const res = await axios.post(`${CENTRAL_API}/auth/login`, { username, password });
    const { access_token, user: u } = res.data;
    localStorage.setItem(STORAGE_KEY, access_token);
    setToken(access_token);
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(SCOPE_KEY);
    setToken(null);
    setUser(null);
    setScope({});
  }, []);

  const updateScope = useCallback((newScope) => {
    setScope(newScope);
    localStorage.setItem(SCOPE_KEY, JSON.stringify(newScope));
  }, []);

  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

  const isSuperadmin = user?.role === 'superadmin';
  const isInstaller = user?.role === 'installer';
  const isOwner = user?.role === 'owner';
  const isStaff = user?.role === 'staff';
  const canManage = isSuperadmin || isInstaller;
  const canManageStaff = isSuperadmin || isInstaller || isOwner;
  const roleLabel = ROLE_LABELS[user?.role] || user?.role;

  return (
    <CentralAuthContext.Provider value={{
      user, token, loading, login, logout,
      authHeaders, isSuperadmin, isInstaller, isOwner, isStaff,
      canManage, canManageStaff, roleLabel,
      isAuthenticated: !!user,
      apiBase: CENTRAL_API,
      scope, updateScope,
    }}>
      {children}
    </CentralAuthContext.Provider>
  );
}

export function useCentralAuth() {
  const ctx = useContext(CentralAuthContext);
  if (!ctx) throw new Error('useCentralAuth must be used within CentralAuthProvider');
  return ctx;
}

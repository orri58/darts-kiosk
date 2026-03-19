import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const CENTRAL_API = `${process.env.REACT_APP_BACKEND_URL}/api/central`;
const STORAGE_KEY = 'central_token';

const CentralAuthContext = createContext(null);

export function CentralAuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem(STORAGE_KEY));
  const [loading, setLoading] = useState(true);

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
    setToken(null);
    setUser(null);
  }, []);

  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};
  const isOperator = user?.role === 'operator';
  const isSuperadmin = user?.role === 'superadmin';

  return (
    <CentralAuthContext.Provider value={{
      user, token, loading, login, logout,
      authHeaders, isOperator, isSuperadmin,
      isAuthenticated: !!user,
      apiBase: CENTRAL_API,
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

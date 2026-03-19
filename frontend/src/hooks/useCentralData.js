import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useCentralAuth } from '../context/CentralAuthContext';

/**
 * Hook to fetch data from the central server with auth headers.
 * Returns { data, loading, error, refetch }.
 */
export function useCentralData(endpoint, deps = []) {
  const { apiBase, authHeaders, isAuthenticated } = useCentralAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${apiBase}/${endpoint}`, { headers: authHeaders });
      setData(res.data);
    } catch (err) {
      const status = err?.response?.status;
      if (status === 502) setError('Zentraler Server nicht erreichbar');
      else if (status === 504) setError('Zentraler Server Timeout');
      else if (status === 403) setError('Zugriff verweigert');
      else setError(err?.response?.data?.detail || 'Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, isAuthenticated, endpoint, ...deps]);

  useEffect(() => { fetch(); }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

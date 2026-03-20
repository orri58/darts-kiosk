import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useCentralAuth } from '../context/CentralAuthContext';

/**
 * Hook to fetch scoped data from the central server with auth headers.
 * Automatically appends scope query params (customer_id, location_id).
 * Pass skipScope=true to skip scope filtering (e.g. for scope/customers endpoint itself).
 */
export function useCentralData(endpoint, { deps = [], skipScope = false } = {}) {
  const { apiBase, authHeaders, isAuthenticated, scope } = useCentralAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      let url = `${apiBase}/${endpoint}`;
      // Append scope params if applicable
      if (!skipScope && (scope.customerId || scope.locationId)) {
        const sep = url.includes('?') ? '&' : '?';
        const params = [];
        if (scope.locationId) params.push(`location_id=${scope.locationId}`);
        else if (scope.customerId) params.push(`customer_id=${scope.customerId}`);
        if (params.length) url += sep + params.join('&');
      }
      const res = await axios.get(url, { headers: authHeaders });
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
  }, [apiBase, isAuthenticated, endpoint, scope.customerId, scope.locationId, ...deps]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

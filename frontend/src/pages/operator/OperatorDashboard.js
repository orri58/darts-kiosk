import { useState, useEffect, useCallback } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import {
  Wifi, WifiOff, Activity, DollarSign, Zap, AlertTriangle,
  Monitor, Clock, RefreshCw, TrendingUp, Gamepad2, CreditCard
} from 'lucide-react';

function formatCurrency(cents) {
  return new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(cents / 100);
}

function timeAgo(isoStr) {
  if (!isoStr) return 'Nie';
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60) return `vor ${Math.floor(diff)}s`;
  if (diff < 3600) return `vor ${Math.floor(diff / 60)} Min.`;
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)} Std.`;
  return `vor ${Math.floor(diff / 86400)} Tagen`;
}

export default function OperatorDashboard() {
  const { scope, apiBase, authHeaders, isAuthenticated } = useCentralAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboard = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      // Build query params from scope
      const params = new URLSearchParams();
      if (scope.deviceId) params.set('device_id', scope.deviceId);
      else if (scope.locationId) params.set('location_id', scope.locationId);
      else if (scope.customerId) params.set('customer_id', scope.customerId);

      const qs = params.toString() ? `?${params.toString()}` : '';
      const res = await fetch(`${apiBase}/telemetry/dashboard${qs}`, {
        headers: authHeaders,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
      setError(null);
    } catch (err) {
      setError(err.message || 'Laden fehlgeschlagen');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isAuthenticated, apiBase, authHeaders, scope]);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(fetchDashboard, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  const handleRefresh = () => { setRefreshing(true); fetchDashboard(); };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-red-400" data-testid="dashboard-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
        <p>{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const onlinePct = data.devices_total > 0 ? Math.round((data.devices_online / data.devices_total) * 100) : 0;

  return (
    <div className="space-y-5" data-testid="operator-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Betriebsübersicht</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {scope.customerId ? 'Gefilterter Scope' : 'Alle Standorte'} — Live-Daten
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors text-sm"
          data-testid="refresh-dashboard-btn"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          Aktualisieren
        </button>
      </div>

      {/* Top KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          icon={Monitor}
          label="Geräte online"
          value={`${data.devices_online} / ${data.devices_total}`}
          sub={`${onlinePct}% erreichbar`}
          color={data.devices_online > 0 ? 'emerald' : 'zinc'}
          tid="kpi-online"
        />
        <KpiCard
          icon={DollarSign}
          label="Umsatz heute"
          value={formatCurrency(data.revenue_today_cents)}
          sub={`7 Tage: ${formatCurrency(data.revenue_7d_cents)}`}
          color="amber"
          tid="kpi-revenue-today"
        />
        <KpiCard
          icon={Gamepad2}
          label="Sessions heute"
          value={data.sessions_today}
          sub={`7 Tage: ${data.sessions_7d}`}
          color="blue"
          tid="kpi-sessions"
        />
        <KpiCard
          icon={Zap}
          label="Spiele heute"
          value={data.games_today}
          sub={`7 Tage: ${data.games_7d}`}
          color="purple"
          tid="kpi-games"
        />
      </div>

      {/* Warnings */}
      {data.warnings?.length > 0 && (
        <div data-testid="warnings-section">
          <div className="flex items-center gap-2 mb-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-semibold text-white">Handlungsbedarf ({data.warnings.length})</h2>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
            {data.warnings.slice(0, 8).map((w, i) => (
              <div key={i} className={`rounded-lg border px-3.5 py-2.5 flex items-start gap-2.5 text-sm ${
                w.type === 'error' ? 'border-red-500/20 bg-red-500/5 text-red-400' :
                w.type === 'offline' ? 'border-amber-500/20 bg-amber-500/5 text-amber-400' :
                'border-zinc-700 bg-zinc-800/50 text-zinc-400'
              }`}>
                {w.type === 'error' ? <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" /> :
                 w.type === 'offline' ? <WifiOff className="w-4 h-4 flex-shrink-0 mt-0.5" /> :
                 <Clock className="w-4 h-4 flex-shrink-0 mt-0.5" />}
                <div>
                  <span className="font-medium">{w.device}</span>
                  <span className="opacity-70 ml-1.5">— {w.message}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Device Health Table */}
      {data.devices?.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-white mb-2.5">Geräte-Status</h2>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm" data-testid="device-health-table">
              <thead>
                <tr className="bg-zinc-900/50 text-zinc-500 text-left text-xs uppercase tracking-wider">
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Gerät</th>
                  <th className="px-4 py-2.5 font-medium">Version</th>
                  <th className="px-4 py-2.5 font-medium">Letzter Heartbeat</th>
                  <th className="px-4 py-2.5 font-medium">Letzte Aktivität</th>
                  <th className="px-4 py-2.5 font-medium">Letzter Sync</th>
                  <th className="px-4 py-2.5 font-medium">Fehler</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {data.devices.map(d => (
                  <tr key={d.id} className="text-zinc-300 hover:bg-zinc-900/30 transition-colors">
                    <td className="px-4 py-2.5">
                      {d.online
                        ? <span className="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-medium"><span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> Online</span>
                        : <span className="inline-flex items-center gap-1.5 text-zinc-500 text-xs font-medium"><span className="w-2 h-2 rounded-full bg-zinc-600" /> Offline</span>
                      }
                    </td>
                    <td className="px-4 py-2.5 font-medium">{d.device_name}</td>
                    <td className="px-4 py-2.5 text-xs font-mono text-zinc-400">{d.reported_version || '—'}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400">{timeAgo(d.last_heartbeat_at)}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400">{timeAgo(d.last_activity_at)}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400">{timeAgo(d.last_sync_at)}</td>
                    <td className="px-4 py-2.5">
                      {d.last_error
                        ? <span className="text-xs text-red-400 truncate max-w-[200px] inline-block" title={d.last_error}>{d.last_error.slice(0, 50)}</span>
                        : <span className="text-xs text-zinc-600">—</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* All good indicator */}
      {(!data.warnings || data.warnings.length === 0) && data.devices_total > 0 && (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center" data-testid="all-ok">
          <Activity className="w-6 h-6 text-emerald-400 mx-auto mb-1" />
          <p className="text-emerald-400 font-medium text-sm">Alle Systeme laufen normal</p>
        </div>
      )}

      {data.devices_total === 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center" data-testid="no-devices">
          <Monitor className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
          <p className="text-zinc-400 font-medium text-sm">Keine Geräte im aktuellen Scope</p>
          <p className="text-zinc-600 text-xs mt-1">Wähle einen Kunden / Standort oder registriere neue Geräte</p>
        </div>
      )}
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, sub, color, tid }) {
  const colorMap = {
    emerald: 'border-emerald-500/20 text-emerald-400',
    amber: 'border-amber-500/20 text-amber-400',
    blue: 'border-blue-500/20 text-blue-400',
    purple: 'border-purple-500/20 text-purple-400',
    zinc: 'border-zinc-700 text-zinc-400',
    red: 'border-red-500/20 text-red-400',
  };
  return (
    <div className={`rounded-xl border bg-zinc-900 p-4 ${colorMap[color] || colorMap.zinc}`} data-testid={tid}>
      <div className="flex items-center justify-between mb-1.5">
        <Icon className="w-4.5 h-4.5 opacity-80" />
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs opacity-70 mt-0.5">{label}</p>
      {sub && <p className="text-xs opacity-50 mt-0.5">{sub}</p>}
    </div>
  );
}

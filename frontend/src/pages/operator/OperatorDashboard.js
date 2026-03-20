import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import {
  Building2, MapPin, Monitor, KeyRound,
  AlertTriangle, CheckCircle, Clock, XCircle, Wifi, WifiOff
} from 'lucide-react';

function StatCard({ icon: Icon, label, value, color, subtext, tid }) {
  return (
    <div className={`rounded-xl border p-4 ${color}`} data-testid={tid}>
      <div className="flex items-center justify-between mb-2">
        <Icon className="w-5 h-5 opacity-80" />
        <span className="text-2xl font-bold">{value}</span>
      </div>
      <p className="text-sm font-medium opacity-90">{label}</p>
      {subtext && <p className="text-xs opacity-60 mt-1">{subtext}</p>}
    </div>
  );
}

export default function OperatorDashboard() {
  const { scope } = useCentralAuth();
  const { data: dash, loading, error } = useCentralData(
    `dashboard${scope.customerId ? `?customer_id=${scope.customerId}` : ''}${scope.locationId ? `${scope.customerId ? '&' : '?'}location_id=${scope.locationId}` : ''}`,
    { skipScope: true }
  );

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

  if (!dash) return null;

  const onlineCount = dash.recent_devices?.filter(d => d.online).length || 0;
  const offlineCount = (dash.recent_devices?.length || 0) - onlineCount;
  const mismatchDevices = dash.recent_devices?.filter(d => d.binding_status === 'mismatch') || [];
  const offlineDevices = dash.recent_devices?.filter(d => !d.online) || [];

  return (
    <div className="space-y-6" data-testid="operator-dashboard">
      <div>
        <h1 className="text-xl font-bold text-white">Übersicht</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          {scope.customerId ? 'Gefilterter Scope' : 'Alle Geschäfte & Standorte'}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={Building2} label="Kunden" value={dash.customers} tid="stat-customers"
          color="bg-zinc-900 border-zinc-800 text-white" />
        <StatCard icon={MapPin} label="Standorte" value={dash.locations} tid="stat-locations"
          color="bg-zinc-900 border-zinc-800 text-white" />
        <StatCard icon={Monitor} label="Geräte" value={dash.devices} tid="stat-devices"
          color="bg-zinc-900 border-zinc-800 text-white"
          subtext={`${onlineCount} online / ${offlineCount} offline`} />
        <StatCard icon={KeyRound} label="Lizenzen" value={dash.licenses_total} tid="stat-licenses"
          color="bg-zinc-900 border-zinc-800 text-white"
          subtext={`${dash.licenses_active} aktiv`} />
      </div>

      {/* Device Health Table */}
      {dash.recent_devices?.length > 0 && (
        <div>
          <h2 className="text-base font-semibold text-white mb-3">Geräte-Status</h2>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm" data-testid="devices-health-table">
              <thead>
                <tr className="bg-zinc-900/50 text-zinc-400 text-left">
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Gerät</th>
                  <th className="px-4 py-2.5 font-medium">Binding</th>
                  <th className="px-4 py-2.5 font-medium">Letzter Sync</th>
                  <th className="px-4 py-2.5 font-medium">Syncs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {dash.recent_devices.map(d => (
                  <tr key={d.id} className="text-zinc-300 hover:bg-zinc-900/30">
                    <td className="px-4 py-2.5">
                      {d.online
                        ? <span className="inline-flex items-center gap-1.5 text-emerald-400 text-xs"><Wifi className="w-3.5 h-3.5" /> Online</span>
                        : <span className="inline-flex items-center gap-1.5 text-zinc-500 text-xs"><WifiOff className="w-3.5 h-3.5" /> Offline</span>
                      }
                    </td>
                    <td className="px-4 py-2.5 font-medium">{d.device_name || d.id.slice(0, 8)}</td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        d.binding_status === 'bound' ? 'bg-emerald-500/10 text-emerald-400' :
                        d.binding_status === 'mismatch' ? 'bg-orange-500/10 text-orange-400' :
                        'bg-zinc-700 text-zinc-400'
                      }`}>{d.binding_status || '—'}</span>
                    </td>
                    <td className="px-4 py-2.5 text-zinc-400 text-xs">
                      {d.last_sync_at ? new Date(d.last_sync_at).toLocaleString('de-DE') : 'Nie'}
                    </td>
                    <td className="px-4 py-2.5 text-zinc-400">{d.sync_count || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Problems */}
      {(offlineDevices.length > 0 || mismatchDevices.length > 0) && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h2 className="text-base font-semibold text-white">Handlungsbedarf</h2>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {offlineDevices.length > 0 && (
              <div className="rounded-xl border border-zinc-600/20 bg-zinc-800/50 p-4 text-zinc-400" data-testid="problem-offline">
                <div className="flex items-center gap-2 mb-2">
                  <WifiOff className="w-4 h-4" />
                  <h3 className="font-semibold text-sm">{offlineDevices.length} Geräte offline</h3>
                </div>
                <div className="space-y-1.5">
                  {offlineDevices.slice(0, 5).map(d => (
                    <div key={d.id} className="text-xs bg-white/5 rounded px-2.5 py-1.5">
                      {d.device_name || d.id.slice(0, 8)} — Sync: {d.last_sync_at ? new Date(d.last_sync_at).toLocaleDateString('de-DE') : 'Nie'}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {mismatchDevices.length > 0 && (
              <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4 text-orange-400" data-testid="problem-mismatch">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4" />
                  <h3 className="font-semibold text-sm">{mismatchDevices.length} Geräte-Mismatch</h3>
                </div>
                <div className="space-y-1.5">
                  {mismatchDevices.slice(0, 5).map(d => (
                    <div key={d.id} className="text-xs bg-white/5 rounded px-2.5 py-1.5">
                      {d.device_name || d.id.slice(0, 8)}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {!offlineDevices.length && !mismatchDevices.length && (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5 text-center" data-testid="no-problems">
          <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-1.5" />
          <p className="text-emerald-400 font-medium text-sm">Alles in Ordnung</p>
        </div>
      )}
    </div>
  );
}

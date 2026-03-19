import { useCentralData } from '../../hooks/useCentralData';
import { Monitor, Wifi, WifiOff, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';

const STATUS_CONFIG = {
  active: { label: 'Aktiv', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
  inactive: { label: 'Inaktiv', color: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20' },
  blocked: { label: 'Gesperrt', color: 'text-red-400 bg-red-500/10 border-red-500/20' },
};

const BINDING_CONFIG = {
  bound: { label: 'Gebunden', color: 'text-emerald-400 bg-emerald-500/10' },
  unbound: { label: 'Ungebunden', color: 'text-zinc-400 bg-zinc-500/10' },
  mismatch: { label: 'Mismatch', color: 'text-orange-400 bg-orange-500/10' },
};

function isOnline(lastSync) {
  if (!lastSync) return false;
  return (Date.now() - new Date(lastSync).getTime()) < 24 * 60 * 60 * 1000;
}

function timeSince(dateStr) {
  if (!dateStr) return 'Nie';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `vor ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `vor ${hours}h`;
  const days = Math.floor(hours / 24);
  return `vor ${days}d`;
}

export default function OperatorDevices() {
  const { data: devices, loading, error, refetch } = useCentralData('licensing/devices');
  const { data: locations } = useCentralData('licensing/locations');

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-red-400" data-testid="devices-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
        <p className="font-medium">{error}</p>
      </div>
    );
  }

  const locationMap = {};
  locations?.forEach(l => { locationMap[l.id] = l; });

  const online = devices?.filter(d => isOnline(d.last_sync_at)) || [];
  const offline = devices?.filter(d => !isOnline(d.last_sync_at)) || [];

  return (
    <div className="space-y-6" data-testid="operator-devices">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Geräte</h1>
          <p className="text-sm text-zinc-500 mt-1">{devices?.length || 0} Geräte registriert</p>
        </div>
        <button onClick={refetch} className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors" data-testid="devices-refresh">
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4" data-testid="devices-online-count">
          <div className="flex items-center gap-2 text-emerald-400">
            <Wifi className="w-5 h-5" />
            <span className="text-2xl font-bold">{online.length}</span>
          </div>
          <p className="text-sm text-emerald-400/80 mt-1">Online (24h)</p>
        </div>
        <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-4" data-testid="devices-offline-count">
          <div className="flex items-center gap-2 text-zinc-400">
            <WifiOff className="w-5 h-5" />
            <span className="text-2xl font-bold">{offline.length}</span>
          </div>
          <p className="text-sm text-zinc-500 mt-1">Offline</p>
        </div>
        <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-4" data-testid="devices-total-count">
          <div className="flex items-center gap-2 text-white">
            <Monitor className="w-5 h-5" />
            <span className="text-2xl font-bold">{devices?.length || 0}</span>
          </div>
          <p className="text-sm text-zinc-500 mt-1">Gesamt</p>
        </div>
      </div>

      {/* Device List */}
      <div className="space-y-3">
        {devices?.length === 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center text-zinc-500" data-testid="devices-empty">
            <Monitor className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p>Keine Geräte vorhanden</p>
          </div>
        )}

        {devices?.map((device) => {
          const loc = locationMap[device.location_id];
          const online = isOnline(device.last_sync_at);
          const st = STATUS_CONFIG[device.status] || STATUS_CONFIG.inactive;
          const bd = BINDING_CONFIG[device.binding_status] || BINDING_CONFIG.unbound;

          return (
            <div key={device.id} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 hover:border-zinc-700 transition-colors" data-testid={`device-${device.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${online ? 'bg-emerald-500/10' : 'bg-zinc-800'}`}>
                    <Monitor className={`w-5 h-5 ${online ? 'text-emerald-400' : 'text-zinc-500'}`} />
                  </div>
                  <div>
                    <h3 className="text-white font-medium text-sm">{device.device_name || `Gerät ${device.id.slice(0, 8)}`}</h3>
                    <p className="text-xs text-zinc-500">{loc?.name || 'Kein Standort'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {online ? (
                    <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-full">
                      <Wifi className="w-3 h-3" /> Online
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-zinc-500 bg-zinc-800 px-2 py-1 rounded-full">
                      <WifiOff className="w-3 h-3" /> Offline
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className={`px-2 py-0.5 rounded-full border ${st.color}`}>{st.label}</span>
                <span className={`px-2 py-0.5 rounded-full ${bd.color}`}>{bd.label}</span>
                {device.binding_status === 'mismatch' && (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-orange-400 bg-orange-500/10">
                    <AlertTriangle className="w-3 h-3" /> Mismatch
                  </span>
                )}
              </div>

              <div className="mt-3 grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs text-zinc-500">
                <div>
                  <span className="block text-zinc-600">Letzter Sync</span>
                  <span className="text-zinc-300">{timeSince(device.last_sync_at)}</span>
                </div>
                <div>
                  <span className="block text-zinc-600">Syncs</span>
                  <span className="text-zinc-300">{device.sync_count || 0}</span>
                </div>
                <div>
                  <span className="block text-zinc-600">Erstellt</span>
                  <span className="text-zinc-300">{device.created_at ? new Date(device.created_at).toLocaleDateString('de-DE') : '—'}</span>
                </div>
                <div>
                  <span className="block text-zinc-600">ID</span>
                  <span className="text-zinc-300 font-mono">{device.id.slice(0, 8)}...</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

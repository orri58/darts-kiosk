import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { Monitor, Wifi, WifiOff, Ban, CheckCircle, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

export default function OperatorDevices() {
  const { apiBase, authHeaders, canManage } = useCentralAuth();
  const { data: devices, loading, error, refetch } = useCentralData('licensing/devices');

  const handleToggle = async (d) => {
    const newStatus = d.status === 'active' ? 'disabled' : 'active';
    try {
      await axios.put(`${apiBase}/licensing/devices/${d.id}`, { status: newStatus }, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
      toast.success(newStatus === 'active' ? 'Gerät aktiviert' : 'Gerät deaktiviert');
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="text-center py-12 text-red-400"><AlertTriangle className="w-8 h-8 mx-auto mb-2" /><p>{error}</p></div>;

  const now = new Date();

  return (
    <div className="space-y-5" data-testid="operator-devices">
      <div>
        <h1 className="text-xl font-bold text-white">Geräte</h1>
        <p className="text-sm text-zinc-500 mt-0.5">{devices?.length || 0} Geräte</p>
      </div>

      <div className="rounded-xl border border-zinc-800 overflow-hidden">
        <table className="w-full text-sm" data-testid="devices-table">
          <thead>
            <tr className="bg-zinc-900/50 text-zinc-400 text-left">
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Gerät</th>
              <th className="px-4 py-2.5 font-medium">Install-ID</th>
              <th className="px-4 py-2.5 font-medium">Binding</th>
              <th className="px-4 py-2.5 font-medium">Letzter Sync</th>
              <th className="px-4 py-2.5 font-medium">Syncs</th>
              <th className="px-4 py-2.5 font-medium">Geräte-Status</th>
              {canManage && <th className="px-4 py-2.5 font-medium text-right">Aktionen</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {(devices || []).map(d => {
              const online = d.last_sync_at && ((now - new Date(d.last_sync_at)) / 1000) < 600;
              return (
                <tr key={d.id} className="text-zinc-300 hover:bg-zinc-900/30">
                  <td className="px-4 py-2.5">
                    {online
                      ? <span className="inline-flex items-center gap-1.5 text-emerald-400 text-xs"><Wifi className="w-3.5 h-3.5" /> Online</span>
                      : <span className="inline-flex items-center gap-1.5 text-zinc-500 text-xs"><WifiOff className="w-3.5 h-3.5" /> Offline</span>}
                  </td>
                  <td className="px-4 py-2.5 font-medium">{d.device_name || d.id.slice(0, 8)}</td>
                  <td className="px-4 py-2.5 text-xs font-mono text-zinc-400">{d.install_id ? d.install_id.slice(0, 12) + '...' : '—'}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${d.binding_status === 'bound' ? 'bg-emerald-500/10 text-emerald-400' : d.binding_status === 'mismatch' ? 'bg-orange-500/10 text-orange-400' : 'bg-zinc-700 text-zinc-400'}`}>
                      {d.binding_status || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-zinc-400">{d.last_sync_at ? new Date(d.last_sync_at).toLocaleString('de-DE') : 'Nie'}</td>
                  <td className="px-4 py-2.5 text-zinc-400">{d.sync_count || 0}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${d.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : d.status === 'blocked' ? 'bg-red-500/10 text-red-400' : 'bg-zinc-500/10 text-zinc-400'}`}>
                      {d.status === 'active' ? 'Aktiv' : d.status === 'blocked' ? 'Gesperrt' : 'Deaktiviert'}
                    </span>
                  </td>
                  {canManage && (
                    <td className="px-4 py-2.5 text-right">
                      <button onClick={() => handleToggle(d)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white" data-testid={`toggle-device-${d.id}`}>
                        {d.status === 'active' ? <Ban className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

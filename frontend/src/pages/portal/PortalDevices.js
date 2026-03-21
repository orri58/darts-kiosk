import { useState } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { useNavigate } from 'react-router-dom';
import {
  Wifi, WifiOff, Ban, CheckCircle, AlertTriangle, ExternalLink,
  RefreshCw, RotateCcw, Play, Square, SquareCheck, X, Loader2,
} from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { Button } from '../../components/ui/button';

const BULK_ACTIONS = [
  { key: 'force_sync', label: 'Config Sync', icon: RefreshCw, desc: 'Konfiguration auf allen ausgewaehlten Geraeten synchronisieren' },
  { key: 'reload_ui', label: 'UI Reload', icon: RotateCcw, desc: 'Kiosk-Oberflaeche auf allen ausgewaehlten Geraeten neu laden' },
  { key: 'restart_backend', label: 'Backend Restart', icon: Play, desc: 'Backend-Dienst auf allen ausgewaehlten Geraeten neustarten' },
];

const BULK_LIMIT = 50;
const BULK_KEY = 'portal_last_bulk';

function loadPersistedResults() {
  try {
    const raw = localStorage.getItem(BULK_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed.ts && (Date.now() - parsed.ts) < 3600000) return parsed.data;
  } catch { /* ignore */ }
  return null;
}

export default function PortalDevices() {
  const navigate = useNavigate();
  const { apiBase, authHeaders, canManage, canManageStaff } = useCentralAuth();
  const { data: devices, loading, error, refetch } = useCentralData('licensing/devices');

  const [selected, setSelected] = useState(new Set());
  const [confirmAction, setConfirmAction] = useState(null);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResults, setBulkResults] = useState(loadPersistedResults);

  const persistResults = (data) => {
    setBulkResults(data);
    if (data) localStorage.setItem(BULK_KEY, JSON.stringify({ data, ts: Date.now() }));
    else localStorage.removeItem(BULK_KEY);
  };

  const handleToggle = async (d) => {
    const newStatus = d.status === 'active' ? 'disabled' : 'active';
    try {
      await axios.put(`${apiBase}/licensing/devices/${d.id}`, { status: newStatus }, {
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
      });
      toast.success(newStatus === 'active' ? 'Geraet aktiviert' : 'Geraet deaktiviert');
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (!devices) return;
    setSelected(prev => prev.size === devices.length ? new Set() : new Set(devices.map(d => d.id)));
  };

  const executeBulk = async () => {
    if (!confirmAction || selected.size === 0) return;
    setBulkLoading(true);
    try {
      const res = await axios.post(`${apiBase}/remote-actions/bulk`, {
        device_ids: Array.from(selected),
        action_type: confirmAction.key,
      }, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
      persistResults(res.data);
      toast.success(`${res.data.created} von ${res.data.total} Aktionen erstellt`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Bulk-Aktion fehlgeschlagen');
    } finally {
      setBulkLoading(false);
      setConfirmAction(null);
    }
  };

  if (loading) return (
    <div className="flex justify-center py-12">
      <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (error) return (
    <div className="text-center py-12 text-red-400">
      <AlertTriangle className="w-8 h-8 mx-auto mb-2" /><p>{error}</p>
    </div>
  );

  const now = new Date();
  const allSelected = devices?.length > 0 && selected.size === devices.length;
  const someSelected = selected.size > 0;
  const overLimit = selected.size > BULK_LIMIT;

  const actionLabel = (key) =>
    key === 'force_sync' ? 'Config Sync' : key === 'reload_ui' ? 'UI Reload' : 'Backend Restart';

  return (
    <div className="space-y-4" data-testid="portal-devices">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Geraete</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {devices?.length || 0} Geraete{someSelected && ` \u2014 ${selected.size} ausgewaehlt`}
          </p>
        </div>
        <Button onClick={refetch} variant="outline" className="border-zinc-700 text-zinc-400 hover:text-white" data-testid="devices-refresh-btn">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Bulk Action Bar */}
      {someSelected && canManageStaff && (
        <div className="flex items-center gap-3 px-4 py-3 bg-indigo-500/5 border border-indigo-500/20 rounded-xl" data-testid="bulk-action-bar">
          <span className="text-sm text-indigo-300 font-medium">
            {selected.size} Geraet{selected.size !== 1 ? 'e' : ''}
          </span>
          {overLimit && (
            <span className="text-xs text-red-400 font-medium" data-testid="bulk-over-limit">
              Max. {BULK_LIMIT}
            </span>
          )}
          <div className="flex-1" />
          {BULK_ACTIONS.map(a => (
            <button
              key={a.key}
              onClick={() => setConfirmAction(a)}
              disabled={overLimit || bulkLoading}
              data-testid={`bulk-btn-${a.key}`}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded-lg text-xs text-zinc-300 hover:text-white hover:border-zinc-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <a.icon className="w-3.5 h-3.5" />{a.label}
            </button>
          ))}
          <button onClick={() => setSelected(new Set())} className="p-1.5 text-zinc-500 hover:text-zinc-300" data-testid="bulk-clear-selection">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Confirm Dialog */}
      {confirmAction && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" data-testid="bulk-confirm-overlay">
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl" data-testid="bulk-confirm-dialog">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                <confirmAction.icon className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <h3 className="text-white font-semibold">{confirmAction.label}</h3>
                <p className="text-xs text-zinc-500">{confirmAction.desc}</p>
              </div>
            </div>
            <div className="bg-zinc-950 rounded-lg p-3 mb-4 border border-zinc-800">
              <p className="text-sm text-zinc-300">
                <span className="text-amber-400 font-bold">{selected.size}</span>{' '}
                Geraet{selected.size !== 1 ? 'e' : ''} betroffen
              </p>
            </div>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setConfirmAction(null)} disabled={bulkLoading}
                className="border-zinc-700 text-zinc-400" data-testid="bulk-confirm-cancel">
                Abbrechen
              </Button>
              <Button onClick={executeBulk} disabled={bulkLoading}
                className="bg-amber-600 hover:bg-amber-500 text-white" data-testid="bulk-confirm-execute">
                {bulkLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                {bulkLoading ? 'Wird ausgefuehrt...' : 'Ausfuehren'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Results — persistent */}
      {bulkResults && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden" data-testid="bulk-results-panel">
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold text-white">
                Ergebnis: {actionLabel(bulkResults.action_type)}
              </h3>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                bulkResults.denied === 0 && bulkResults.created === bulkResults.total
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : bulkResults.created > 0
                    ? 'bg-amber-500/10 text-amber-400'
                    : 'bg-red-500/10 text-red-400'
              }`}>
                {bulkResults.created}/{bulkResults.total} erstellt
              </span>
            </div>
            <button onClick={() => persistResults(null)} className="text-zinc-500 hover:text-zinc-300" data-testid="bulk-results-close">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex items-center gap-4 px-4 py-2 border-b border-zinc-800/50 text-xs">
            {bulkResults.created > 0 && <span className="text-emerald-400">{bulkResults.created} erstellt</span>}
            {bulkResults.skipped > 0 && <span className="text-amber-400">{bulkResults.skipped} uebersprungen</span>}
            {bulkResults.denied > 0 && <span className="text-red-400">{bulkResults.denied} verweigert</span>}
          </div>
          <div className="divide-y divide-zinc-800/30 max-h-[200px] overflow-y-auto">
            {bulkResults.results.map((r, i) => (
              <div key={i} className="flex items-center gap-2 px-4 py-2 text-xs" data-testid={`bulk-result-${r.device_id}`}>
                {r.status === 'created' && <CheckCircle className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />}
                {r.status === 'skipped' && <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />}
                {(r.status === 'denied' || r.status === 'error') && <Ban className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />}
                <span className="text-zinc-300 flex-1 truncate">{r.device_name || r.device_id?.slice(0, 8)}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  r.status === 'created' ? 'bg-emerald-500/10 text-emerald-400' :
                  r.status === 'skipped' ? 'bg-amber-500/10 text-amber-400' :
                  'bg-red-500/10 text-red-400'
                }`}>
                  {r.status === 'created' ? 'Erstellt' : r.status === 'skipped' ? 'Uebersprungen' : r.status === 'denied' ? 'Verweigert' : 'Fehler'}
                </span>
                {r.message && <span className="text-zinc-600 truncate max-w-[140px]" title={r.message}>{r.message}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Device Table */}
      <div className="rounded-xl border border-zinc-800 overflow-hidden">
        <table className="w-full text-sm" data-testid="devices-table">
          <thead>
            <tr className="bg-zinc-900/50 text-zinc-400 text-left">
              {canManageStaff && (
                <th className="px-3 py-2.5 w-10">
                  <button onClick={selectAll} data-testid="select-all-devices" className="p-0.5 rounded hover:bg-zinc-800">
                    {allSelected
                      ? <SquareCheck className="w-4 h-4 text-indigo-400" />
                      : <Square className="w-4 h-4 text-zinc-600" />}
                  </button>
                </th>
              )}
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Geraet</th>
              <th className="px-4 py-2.5 font-medium">Binding</th>
              <th className="px-4 py-2.5 font-medium">Letzter Sync</th>
              <th className="px-4 py-2.5 font-medium">Geraete-Status</th>
              <th className="px-4 py-2.5 font-medium text-right">Aktionen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {(devices || []).map(d => {
              const online = d.last_sync_at && ((now - new Date(d.last_sync_at)) / 1000) < 600;
              const isSel = selected.has(d.id);
              const rItem = bulkResults?.results?.find(r => r.device_id === d.id);
              const rowHighlight = rItem
                ? rItem.status === 'created' ? 'bg-emerald-500/[.03]' : (rItem.status === 'denied' || rItem.status === 'error') ? 'bg-red-500/[.03]' : ''
                : isSel ? 'bg-indigo-500/5' : '';
              return (
                <tr key={d.id} className={`text-zinc-300 hover:bg-zinc-900/30 ${rowHighlight}`} data-testid={`device-row-${d.id}`}>
                  {canManageStaff && (
                    <td className="px-3 py-2.5 cursor-pointer" onClick={e => { e.stopPropagation(); toggleSelect(d.id); }}>
                      {isSel
                        ? <SquareCheck className="w-4 h-4 text-indigo-400" />
                        : <Square className="w-4 h-4 text-zinc-600" />}
                    </td>
                  )}
                  <td className="px-4 py-2.5 cursor-pointer" onClick={() => navigate(`/portal/devices/${d.id}`)}>
                    {online
                      ? <span className="inline-flex items-center gap-1.5 text-emerald-400 text-xs"><Wifi className="w-3.5 h-3.5" /> Online</span>
                      : <span className="inline-flex items-center gap-1.5 text-zinc-500 text-xs"><WifiOff className="w-3.5 h-3.5" /> Offline</span>}
                  </td>
                  <td className="px-4 py-2.5 font-medium cursor-pointer" onClick={() => navigate(`/portal/devices/${d.id}`)}>{d.device_name || d.id.slice(0, 8)}</td>
                  <td className="px-4 py-2.5 cursor-pointer" onClick={() => navigate(`/portal/devices/${d.id}`)}>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      d.binding_status === 'bound' ? 'bg-emerald-500/10 text-emerald-400' :
                      d.binding_status === 'mismatch' ? 'bg-orange-500/10 text-orange-400' :
                      'bg-zinc-700 text-zinc-400'}`}>
                      {d.binding_status || '\u2014'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-zinc-400 cursor-pointer" onClick={() => navigate(`/portal/devices/${d.id}`)}>
                    {d.last_sync_at ? new Date(d.last_sync_at).toLocaleString('de-DE') : 'Nie'}
                  </td>
                  <td className="px-4 py-2.5 cursor-pointer" onClick={() => navigate(`/portal/devices/${d.id}`)}>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      d.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' :
                      d.status === 'blocked' ? 'bg-red-500/10 text-red-400' :
                      'bg-zinc-500/10 text-zinc-400'}`}>
                      {d.status === 'active' ? 'Aktiv' : d.status === 'blocked' ? 'Gesperrt' : 'Deaktiviert'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center gap-1.5 justify-end">
                      <button
                        onClick={e => { e.stopPropagation(); navigate(`/portal/devices/${d.id}`); }}
                        className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-indigo-400"
                        data-testid={`detail-device-${d.id}`} title="Details"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </button>
                      {canManage && (
                        <button
                          onClick={e => { e.stopPropagation(); handleToggle(d); }}
                          className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white"
                          data-testid={`toggle-device-${d.id}`}
                        >
                          {d.status === 'active' ? <Ban className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

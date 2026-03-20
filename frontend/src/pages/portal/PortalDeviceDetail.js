import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Monitor, ArrowLeft, RefreshCw, Play, RotateCcw,
  Globe, Clock, Activity, AlertTriangle, CheckCircle,
  XCircle, Wifi, WifiOff, Zap, ScrollText, BarChart3
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { useCentralAuth } from '../../context/CentralAuthContext';

const ACTION_META = {
  force_sync: { label: 'Config-Sync', icon: RefreshCw, desc: 'Config sofort vom Server ziehen', color: 'indigo' },
  restart_backend: { label: 'Backend Restart', icon: RotateCcw, desc: 'Kiosk-Backend neu starten', color: 'amber' },
  reload_ui: { label: 'UI Reload', icon: Globe, desc: 'Browser-UI neu laden', color: 'emerald' },
};

const STATUS_BADGE = {
  pending: { cls: 'bg-amber-500/10 text-amber-400', label: 'Ausstehend' },
  acked: { cls: 'bg-emerald-500/10 text-emerald-400', label: 'Ausgefuehrt' },
  failed: { cls: 'bg-red-500/10 text-red-400', label: 'Fehlgeschlagen' },
};

export default function PortalDeviceDetail() {
  const { deviceId } = useParams();
  const navigate = useNavigate();
  const { apiBase, authHeaders } = useCentralAuth();
  const [device, setDevice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchDevice = useCallback(async () => {
    try {
      const res = await axios.get(`${apiBase}/telemetry/device/${deviceId}`, { headers: authHeaders });
      setDevice(res.data);
    } catch (err) {
      if (err.response?.status === 404) toast.error('Geraet nicht gefunden');
    } finally {
      setLoading(false);
    }
  }, [apiBase, authHeaders, deviceId]);

  useEffect(() => { fetchDevice(); }, [fetchDevice]);

  const issueAction = async (actionType) => {
    setActionLoading(actionType);
    try {
      await axios.post(`${apiBase}/remote-actions/${deviceId}`, { action_type: actionType }, {
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
      });
      toast.success(`Aktion "${ACTION_META[actionType].label}" gesendet`);
      fetchDevice();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Aktion fehlgeschlagen');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!device) {
    return (
      <div className="text-center py-16">
        <Monitor className="w-12 h-12 text-zinc-700 mx-auto mb-3" />
        <p className="text-zinc-500">Geraet nicht gefunden</p>
        <Button onClick={() => navigate('/portal/devices')} variant="outline" className="mt-4 border-zinc-700 text-zinc-400">
          <ArrowLeft className="w-4 h-4 mr-2" /> Zurueck
        </Button>
      </div>
    );
  }

  const isOnline = device.is_online;
  const lastSeen = device.last_heartbeat_at ? new Date(device.last_heartbeat_at).toLocaleString('de-DE') : 'Nie';
  const lastActivity = device.last_activity_at ? new Date(device.last_activity_at).toLocaleString('de-DE') : '—';

  return (
    <div data-testid="device-detail-page">
      {/* Header */}
      <div className="flex items-center gap-4 mb-5">
        <Button onClick={() => navigate('/portal/devices')} variant="ghost" className="text-zinc-400 hover:text-white p-2" data-testid="device-back-btn">
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-white" data-testid="device-name">{device.device_name || device.id.slice(0, 8)}</h1>
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
              isOnline ? 'bg-emerald-500/10 text-emerald-400' : 'bg-zinc-800 text-zinc-500'
            }`} data-testid="device-online-status">
              {isOnline ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {isOnline ? 'Online' : 'Offline'}
            </span>
          </div>
          <p className="text-sm text-zinc-500">
            {device.customer?.name} → {device.location?.name}
          </p>
        </div>
        <Button onClick={fetchDevice} variant="outline" className="border-zinc-700 text-zinc-400 hover:text-white" data-testid="device-refresh-btn">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-3">
            <p className="text-[10px] text-zinc-600 uppercase mb-1">Version</p>
            <p className="text-sm font-mono text-white" data-testid="device-version">{device.reported_version || '—'}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-3">
            <p className="text-[10px] text-zinc-600 uppercase mb-1">Letzter Kontakt</p>
            <p className="text-sm text-white" data-testid="device-last-seen">{lastSeen}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-3">
            <p className="text-[10px] text-zinc-600 uppercase mb-1">Letzte Aktivitaet</p>
            <p className="text-sm text-white">{lastActivity}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-3">
            <p className="text-[10px] text-zinc-600 uppercase mb-1">Status</p>
            <p className="text-sm text-white capitalize">{device.status}</p>
          </CardContent>
        </Card>
      </div>

      {/* Last Error */}
      {device.last_error && (
        <div className="flex items-start gap-2.5 p-3 mb-5 rounded-lg bg-red-500/5 border border-red-500/20" data-testid="device-last-error">
          <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-400">Letzter Fehler</p>
            <p className="text-xs text-red-300/70 font-mono mt-0.5">{device.last_error}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Remote Actions + Actions Log */}
        <div className="lg:col-span-2 space-y-4">
          {/* Remote Actions */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <Zap className="w-4 h-4" />
                Remote-Aktionen
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" data-testid="remote-actions-grid">
                {Object.entries(ACTION_META).map(([key, meta]) => {
                  const Icon = meta.icon;
                  const isLoading = actionLoading === key;
                  return (
                    <button
                      key={key}
                      onClick={() => issueAction(key)}
                      disabled={!!actionLoading}
                      data-testid={`action-${key}`}
                      className={`flex flex-col items-center gap-2 p-4 rounded-lg border transition-all text-center
                        border-${meta.color}-500/20 hover:border-${meta.color}-500/40 hover:bg-${meta.color}-500/5
                        disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {isLoading ? (
                        <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Icon className={`w-6 h-6 text-${meta.color}-400`} />
                      )}
                      <span className="text-sm text-white font-medium">{meta.label}</span>
                      <span className="text-[10px] text-zinc-500">{meta.desc}</span>
                    </button>
                  );
                })}
              </div>
              <p className="text-[10px] text-zinc-600 mt-3">
                Aktionen werden beim naechsten Geraete-Poll abgeholt (max. 60s). Jede Aktion wird im Audit-Log festgehalten.
              </p>
            </CardContent>
          </Card>

          {/* Recent Actions Log */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <ScrollText className="w-4 h-4" />
                Aktions-Verlauf
              </CardTitle>
            </CardHeader>
            <CardContent>
              {device.recent_actions?.length ? (
                <div className="space-y-2" data-testid="actions-log">
                  {device.recent_actions.map(a => {
                    const badge = STATUS_BADGE[a.status] || STATUS_BADGE.pending;
                    return (
                      <div key={a.id} className="flex items-center gap-3 py-2 border-b border-zinc-800/50 last:border-0">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${badge.cls}`}>{badge.label}</span>
                        <span className="text-sm text-zinc-300 flex-1 font-mono">{a.action_type}</span>
                        <span className="text-xs text-zinc-600">{a.issued_by}</span>
                        <span className="text-xs text-zinc-600">{a.issued_at ? new Date(a.issued_at).toLocaleString('de-DE') : ''}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-zinc-600">Keine Aktionen vorhanden</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Recent Events + Daily Stats */}
        <div className="space-y-4">
          {/* Daily Stats */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <BarChart3 className="w-4 h-4" />
                Letzte 7 Tage
              </CardTitle>
            </CardHeader>
            <CardContent>
              {device.daily_stats?.length ? (
                <div className="space-y-1.5" data-testid="daily-stats">
                  {device.daily_stats.map(s => (
                    <div key={s.date} className="flex items-center gap-2 py-1.5 border-b border-zinc-800/30 last:border-0">
                      <span className="text-xs text-zinc-500 font-mono w-20">{s.date}</span>
                      <span className="text-xs text-emerald-400">{((s.revenue_cents || 0) / 100).toFixed(2)} EUR</span>
                      <span className="text-xs text-zinc-500 ml-auto">{s.sessions}S / {s.games}G</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-600">Keine Daten</p>
              )}
            </CardContent>
          </Card>

          {/* Recent Events */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Letzte Events
              </CardTitle>
            </CardHeader>
            <CardContent>
              {device.recent_events?.length ? (
                <div className="space-y-1.5" data-testid="recent-events">
                  {device.recent_events.map((e, i) => (
                    <div key={i} className="flex items-center gap-2 py-1 border-b border-zinc-800/30 last:border-0">
                      <span className="text-xs text-indigo-400 font-mono">{e.event_type}</span>
                      <span className="text-[10px] text-zinc-600 ml-auto">{e.timestamp ? new Date(e.timestamp).toLocaleString('de-DE') : ''}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-600">Keine Events</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Monitor, ArrowLeft, RefreshCw, RotateCcw,
  Globe, Clock, Activity, AlertTriangle, CheckCircle,
  XCircle, Wifi, WifiOff, Zap, ScrollText, BarChart3,
  HeartPulse, Database, Terminal, Filter, Shield, ShieldOff, ShieldAlert,
  Settings2, Save, ChevronDown, ChevronUp, Unlock, Lock, Play, Square
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { useCentralAuth } from '../../context/CentralAuthContext';

const ACTION_META = {
  unlock_board: { label: 'Freischalten', icon: Unlock, desc: 'Board fuer Spieler freischalten', primary: true },
  lock_board: { label: 'Sperren', icon: Lock, desc: 'Board sperren / Kiosk-Lockscreen', primary: true },
  start_session: { label: 'Session Starten', icon: Play, desc: 'Neue Spielsession starten', primary: true },
  stop_session: { label: 'Session Beenden', icon: Square, desc: 'Aktive Session beenden', primary: true },
  force_sync: { label: 'Config-Sync', icon: RefreshCw, desc: 'Config sofort vom Server ziehen' },
  restart_backend: { label: 'Backend Restart', icon: RotateCcw, desc: 'Kiosk-Backend neu starten' },
  reload_ui: { label: 'UI Reload', icon: Globe, desc: 'Browser-UI neu laden' },
};

const STATUS_BADGE = {
  pending: { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20', label: 'Ausstehend' },
  acked: { cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', label: 'Ausgefuehrt' },
  failed: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', label: 'Fehlgeschlagen' },
};

const HEALTH_BADGE = {
  healthy: { cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', icon: CheckCircle, label: 'Healthy' },
  degraded: { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30', icon: AlertTriangle, label: 'Degraded' },
  offline: { cls: 'bg-red-500/10 text-red-400 border-red-500/30', icon: XCircle, label: 'Offline' },
  unknown: { cls: 'bg-zinc-800 text-zinc-500 border-zinc-700', icon: Monitor, label: 'Unbekannt' },
};

const LOG_LEVEL_CLS = {
  info: 'text-zinc-400',
  warn: 'text-amber-400',
  error: 'text-red-400',
};

function timeAgo(isoStr) {
  if (!isoStr) return 'nie';
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60) return `vor ${Math.round(diff)}s`;
  if (diff < 3600) return `vor ${Math.round(diff / 60)}m`;
  if (diff < 86400) return `vor ${Math.round(diff / 3600)}h`;
  return `vor ${Math.round(diff / 86400)}d`;
}

function getHealthReason(hs, isOnline) {
  if (!isOnline) return 'Kein Heartbeat / Offline';
  if (!hs) return 'Kein Health-Snapshot empfangen';
  const reasons = [];
  const cs = hs.config_sync;
  const ap = hs.action_poller;
  const oq = hs.offline_queue;
  if (cs?.consecutive_errors >= 3) reasons.push(`${cs.consecutive_errors} Sync-Fehler`);
  if (cs?.last_error) reasons.push(`Sync: ${cs.last_error}`);
  if (ap?.consecutive_poll_errors >= 5) reasons.push(`${ap.consecutive_poll_errors} Poll-Fehler`);
  if (ap?.last_error) reasons.push(`Poller: ${ap.last_error}`);
  if (oq?.pending > 0) reasons.push(`Offline Queue: ${oq.pending} ausstehend`);
  if (oq?.last_drain_error) reasons.push(`Queue: ${oq.last_drain_error}`);
  return reasons.length > 0 ? reasons.join(' | ') : null;
}

function StatusCell({ label, value, sub }) {
  return (
    <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/50">
      <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-sm font-mono text-white truncate">{value || '\u2014'}</p>
      {sub && <p className="text-[10px] text-zinc-600 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function PortalDeviceDetail() {
  const { deviceId } = useParams();
  const navigate = useNavigate();
  const { apiBase, authHeaders } = useCentralAuth();
  const [device, setDevice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [logFilter, setLogFilter] = useState('all');
  const [configExpanded, setConfigExpanded] = useState(false);
  const [deviceConfig, setDeviceConfig] = useState(null);
  const [configSaving, setConfigSaving] = useState(false);
  const [configDirty, setConfigDirty] = useState(false);

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

  // Auto-refresh every 30s
  useEffect(() => {
    const iv = setInterval(fetchDevice, 30000);
    return () => clearInterval(iv);
  }, [fetchDevice]);

  const issueAction = async (actionType) => {
    setActionLoading(actionType);
    try {
      await axios.post(`${apiBase}/remote-actions/${deviceId}`, { action_type: actionType }, {
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
      });
      toast.success(`Aktion "${ACTION_META[actionType].label}" gesendet`);
      setTimeout(fetchDevice, 1500);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Aktion fehlgeschlagen');
    } finally {
      setActionLoading(null);
    }
  };

  const changeDeviceStatus = async (newStatus) => {
    setStatusLoading(true);
    try {
      await axios.put(`${apiBase}/licensing/devices/${deviceId}`, { status: newStatus }, {
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
      });
      toast.success(`Geraetestatus geaendert: ${newStatus}`);
      await fetchDevice();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Status-Aenderung fehlgeschlagen');
    } finally {
      setStatusLoading(false);
    }
  };

  // Device-specific config
  const fetchDeviceConfig = useCallback(async () => {
    try {
      const res = await axios.get(`${apiBase}/config/effective`, {
        headers: authHeaders,
        params: { scope: 'device', scope_id: deviceId },
      });
      setDeviceConfig(res.data?.config || res.data);
    } catch {
      setDeviceConfig(null);
    }
  }, [apiBase, authHeaders, deviceId]);

  useEffect(() => {
    if (configExpanded && !deviceConfig) fetchDeviceConfig();
  }, [configExpanded, deviceConfig, fetchDeviceConfig]);

  const updateConfigField = (section, key, value) => {
    setDeviceConfig(prev => {
      const updated = { ...prev };
      if (!updated[section]) updated[section] = {};
      updated[section] = { ...updated[section], [key]: value };
      return updated;
    });
    setConfigDirty(true);
  };

  const saveDeviceConfig = async () => {
    setConfigSaving(true);
    try {
      await axios.put(`${apiBase}/config/profile/device/${deviceId}`, {
        config: deviceConfig,
      }, {
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
      });
      toast.success('Konfiguration gespeichert und Push ausgeloest');
      setConfigDirty(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Speichern fehlgeschlagen');
    } finally {
      setConfigSaving(false);
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
  const hs = device.health_snapshot;
  const healthKey = !isOnline ? 'offline' : (hs?.health_status || 'unknown');
  const healthMeta = HEALTH_BADGE[healthKey] || HEALTH_BADGE.unknown;
  const HealthIcon = healthMeta.icon;
  const healthReason = getHealthReason(hs, isOnline);

  const logs = (device.device_logs || []).filter(l =>
    logFilter === 'all' || l.level === logFilter
  );

  return (
    <div data-testid="device-detail-page" className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button onClick={() => navigate('/portal/devices')} variant="ghost" className="text-zinc-400 hover:text-white p-2" data-testid="device-back-btn">
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-white truncate" data-testid="device-name">{device.device_name || device.id.slice(0, 8)}</h1>
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${healthMeta.cls}`} data-testid="device-health-badge">
              <HealthIcon className="w-3 h-3" />
              {healthMeta.label}
            </span>
          </div>
          <p className="text-sm text-zinc-500 truncate">
            {device.customer?.name} {device.location?.name ? `→ ${device.location.name}` : ''}
          </p>
        </div>
        <Button onClick={fetchDevice} variant="outline" className="border-zinc-700 text-zinc-400 hover:text-white" data-testid="device-refresh-btn">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Health Reason Banner */}
      {healthReason && healthKey !== 'healthy' && (
        <div className={`flex items-start gap-2.5 p-3 rounded-lg border ${
          healthKey === 'offline' ? 'bg-red-500/5 border-red-500/20' : 'bg-amber-500/5 border-amber-500/20'
        }`} data-testid="device-health-reason">
          <AlertTriangle className={`w-4 h-4 mt-0.5 flex-shrink-0 ${healthKey === 'offline' ? 'text-red-400' : 'text-amber-400'}`} />
          <div>
            <p className={`text-sm font-medium ${healthKey === 'offline' ? 'text-red-400' : 'text-amber-400'}`}>
              {healthKey === 'offline' ? 'Geraet nicht erreichbar' : 'Eingeschraenkte Funktion'}
            </p>
            <p className="text-xs text-zinc-400 font-mono mt-0.5">{healthReason}</p>
          </div>
        </div>
      )}

      {/* Status Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2" data-testid="device-status-grid">
        <StatusCell label="Version" value={device.reported_version} />
        <StatusCell label="Letzter Heartbeat" value={device.last_heartbeat_at ? timeAgo(device.last_heartbeat_at) : null} sub={device.last_heartbeat_at ? new Date(device.last_heartbeat_at).toLocaleString('de-DE') : null} />
        <StatusCell label="Config Version" value={hs?.config_applied_version ?? '\u2014'} sub={hs?.config_sync?.config_version ? `Zentral: v${hs.config_sync.config_version}` : null} />
        <StatusCell label="Letzter Sync" value={hs?.config_sync?.last_sync_at ? timeAgo(hs.config_sync.last_sync_at) : null} sub={`${hs?.config_sync?.sync_count ?? 0} Syncs, ${hs?.config_sync?.consecutive_errors ?? 0} Fehler`} />
        <StatusCell label="Letzte Aktion" value={hs?.action_poller?.last_action_at ? timeAgo(hs.action_poller.last_action_at) : null} sub={`${hs?.action_poller?.actions_executed ?? 0} OK, ${hs?.action_poller?.actions_failed ?? 0} Fehler`} />
        <StatusCell label="Offline Queue" value={hs?.offline_queue?.pending > 0 ? `${hs.offline_queue.pending} ausstehend` : 'Leer'} sub={hs?.offline_queue?.last_drain_at ? `Letzter Drain: ${timeAgo(hs.offline_queue.last_drain_at)}` : `${hs?.offline_queue?.drained_total ?? 0} gesendet, ${hs?.offline_queue?.dropped_total ?? 0} verworfen`} />
        <StatusCell label="WS Push" value={hs?.ws_push?.connected ? 'Verbunden' : (hs?.ws_push?.configured ? 'Getrennt' : 'Nicht konfiguriert')} sub={hs?.ws_push?.connected ? `${hs.ws_push.events_received ?? 0} Events` : (hs?.ws_push?.last_error ? `Fehler: ${hs.ws_push.last_error}` : (hs?.ws_push?.reconnect_count > 0 ? `${hs.ws_push.reconnect_count} Reconnects` : null))} />
        <StatusCell label="Lizenz" value={device.license_id ? 'Gebunden' : 'Keine'} sub={device.license_id ? device.license_id.slice(0, 12) + '...' : null} />
      </div>

      {/* Device Trust / Binding Control — v3.12.0 */}
      <Card className="bg-zinc-900 border-zinc-800" data-testid="device-trust-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
            <Shield className="w-4 h-4" /> Geraete-Vertrauen / Binding
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500">Status:</span>
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${
                device.status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                device.status === 'blocked' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                'bg-amber-500/10 text-amber-400 border-amber-500/20'
              }`} data-testid="device-trust-status">
                {device.status === 'active' ? <CheckCircle className="w-3 h-3" /> :
                 device.status === 'blocked' ? <ShieldAlert className="w-3 h-3" /> :
                 <ShieldOff className="w-3 h-3" />}
                {device.status === 'active' ? 'Aktiv' : device.status === 'blocked' ? 'Gesperrt' : 'Deaktiviert'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500">Binding:</span>
              <span className={`text-xs font-mono ${device.binding_status === 'bound' ? 'text-emerald-400' : 'text-amber-400'}`} data-testid="device-binding-status">
                {device.binding_status === 'bound' ? 'Gebunden' : device.binding_status || 'Unbekannt'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500">Install-ID:</span>
              <span className="text-xs font-mono text-zinc-400" data-testid="device-install-id">{device.install_id?.slice(0, 12) || '\u2014'}...</span>
            </div>
            <div className="flex items-center gap-1 ml-auto">
              {device.status !== 'active' && (
                <Button size="sm" variant="outline" disabled={statusLoading}
                  className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 text-xs h-7"
                  onClick={() => changeDeviceStatus('active')} data-testid="device-activate-btn">
                  <CheckCircle className="w-3 h-3 mr-1" /> Aktivieren
                </Button>
              )}
              {device.status === 'active' && (
                <Button size="sm" variant="outline" disabled={statusLoading}
                  className="border-amber-500/30 text-amber-400 hover:bg-amber-500/10 text-xs h-7"
                  onClick={() => changeDeviceStatus('inactive')} data-testid="device-deactivate-btn">
                  <ShieldOff className="w-3 h-3 mr-1" /> Deaktivieren
                </Button>
              )}
              {device.status !== 'blocked' && (
                <Button size="sm" variant="outline" disabled={statusLoading}
                  className="border-red-500/30 text-red-400 hover:bg-red-500/10 text-xs h-7"
                  onClick={() => changeDeviceStatus('blocked')} data-testid="device-block-btn">
                  <ShieldAlert className="w-3 h-3 mr-1" /> Sperren
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Device Quick Config — v3.13.0 */}
      <Card className="bg-zinc-900 border-zinc-800" data-testid="device-quick-config">
        <CardHeader className="pb-2 cursor-pointer" onClick={() => setConfigExpanded(!configExpanded)}>
          <CardTitle className="text-sm text-zinc-400 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Settings2 className="w-4 h-4" /> Device-Konfiguration
              {configDirty && <span className="text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">Ungespeichert</span>}
            </span>
            {configExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </CardTitle>
        </CardHeader>
        {configExpanded && (
          <CardContent className="space-y-4">
            {deviceConfig ? (
              <>
                {/* Branding */}
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 font-medium uppercase">Branding</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Cafe Name</label>
                      <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-cafe-name"
                        value={deviceConfig?.branding?.cafe_name || ''} onChange={e => updateConfigField('branding', 'cafe_name', e.target.value)} />
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Untertitel</label>
                      <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-subtitle"
                        value={deviceConfig?.branding?.subtitle || ''} onChange={e => updateConfigField('branding', 'subtitle', e.target.value)} />
                    </div>
                  </div>
                </div>
                {/* Pricing */}
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 font-medium uppercase">Preise</p>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Modus</label>
                      <select className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-pricing-mode"
                        value={deviceConfig?.pricing?.mode || 'per_game'} onChange={e => updateConfigField('pricing', 'mode', e.target.value)}>
                        <option value="per_game">Pro Spiel</option>
                        <option value="per_time">Pro Zeit</option>
                        <option value="per_player">Pro Spieler</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Preis/Credit</label>
                      <input type="number" step="0.5" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-price"
                        value={deviceConfig?.pricing?.price_per_credit ?? ''} onChange={e => updateConfigField('pricing', 'price_per_credit', parseFloat(e.target.value) || 0)} />
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Max Spieler</label>
                      <input type="number" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-max-players"
                        value={deviceConfig?.pricing?.max_players ?? ''} onChange={e => updateConfigField('pricing', 'max_players', parseInt(e.target.value) || 4)} />
                    </div>
                  </div>
                </div>
                {/* Kiosk Texts */}
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 font-medium uppercase">Kiosk-Texte</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Willkommenstitel</label>
                      <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-welcome-title"
                        value={deviceConfig?.texts?.welcome_title || ''} onChange={e => updateConfigField('texts', 'welcome_title', e.target.value)} />
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Untertitel</label>
                      <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-welcome-sub"
                        value={deviceConfig?.texts?.welcome_subtitle || ''} onChange={e => updateConfigField('texts', 'welcome_subtitle', e.target.value)} />
                    </div>
                  </div>
                </div>
                {/* Board / Autodarts */}
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 font-medium uppercase">Board / Autodarts</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Autodarts URL</label>
                      <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-autodarts-url"
                        placeholder="https://play.autodarts.io" value={deviceConfig?.boards?.autodarts_url || ''} onChange={e => updateConfigField('boards', 'autodarts_url', e.target.value)} />
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Board Name</label>
                      <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-board-name"
                        value={deviceConfig?.boards?.board_name || ''} onChange={e => updateConfigField('boards', 'board_name', e.target.value)} />
                    </div>
                  </div>
                </div>
                {/* Sound / Language */}
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 font-medium uppercase">Sound / Sprache</p>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="flex items-center gap-2">
                      <input type="checkbox" className="rounded border-zinc-600" data-testid="cfg-sound-enabled"
                        checked={deviceConfig?.sound?.enabled ?? true} onChange={e => updateConfigField('sound', 'enabled', e.target.checked)} />
                      <label className="text-xs text-zinc-400">Sound aktiv</label>
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Lautstaerke</label>
                      <input type="range" min="0" max="100" className="w-full" data-testid="cfg-sound-volume"
                        value={deviceConfig?.sound?.volume ?? 70} onChange={e => updateConfigField('sound', 'volume', parseInt(e.target.value))} />
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Sprache</label>
                      <select className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-language"
                        value={deviceConfig?.language?.default || 'de'} onChange={e => updateConfigField('language', 'default', e.target.value)}>
                        <option value="de">Deutsch</option>
                        <option value="en">English</option>
                      </select>
                    </div>
                  </div>
                </div>
                {/* Farben */}
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 font-medium uppercase">Farben</p>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Primaerfarbe</label>
                      <div className="flex items-center gap-1">
                        <input type="color" className="w-6 h-6 border border-zinc-700 rounded cursor-pointer" data-testid="cfg-primary-color"
                          value={deviceConfig?.branding?.primary_color || '#6366f1'} onChange={e => updateConfigField('branding', 'primary_color', e.target.value)} />
                        <input className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white font-mono"
                          value={deviceConfig?.branding?.primary_color || ''} onChange={e => updateConfigField('branding', 'primary_color', e.target.value)} />
                      </div>
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Sekundaerfarbe</label>
                      <div className="flex items-center gap-1">
                        <input type="color" className="w-6 h-6 border border-zinc-700 rounded cursor-pointer" data-testid="cfg-secondary-color"
                          value={deviceConfig?.branding?.secondary_color || '#1e1b4b'} onChange={e => updateConfigField('branding', 'secondary_color', e.target.value)} />
                        <input className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white font-mono"
                          value={deviceConfig?.branding?.secondary_color || ''} onChange={e => updateConfigField('branding', 'secondary_color', e.target.value)} />
                      </div>
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Akzentfarbe</label>
                      <div className="flex items-center gap-1">
                        <input type="color" className="w-6 h-6 border border-zinc-700 rounded cursor-pointer" data-testid="cfg-accent-color"
                          value={deviceConfig?.branding?.accent_color || '#f59e0b'} onChange={e => updateConfigField('branding', 'accent_color', e.target.value)} />
                        <input className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white font-mono"
                          value={deviceConfig?.branding?.accent_color || ''} onChange={e => updateConfigField('branding', 'accent_color', e.target.value)} />
                      </div>
                    </div>
                  </div>
                </div>
                {/* QR / Sharing */}
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 font-medium uppercase">QR / Sharing</p>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="flex items-center gap-2">
                      <input type="checkbox" className="rounded border-zinc-600" data-testid="cfg-qr-enabled"
                        checked={deviceConfig?.sharing?.qr_enabled ?? true} onChange={e => updateConfigField('sharing', 'qr_enabled', e.target.checked)} />
                      <label className="text-xs text-zinc-400">QR-Code aktiv</label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input type="checkbox" className="rounded border-zinc-600" data-testid="cfg-public-results"
                        checked={deviceConfig?.sharing?.public_results ?? true} onChange={e => updateConfigField('sharing', 'public_results', e.target.checked)} />
                      <label className="text-xs text-zinc-400">Oeffentl. Ergebnisse</label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input type="checkbox" className="rounded border-zinc-600" data-testid="cfg-leaderboard"
                        checked={deviceConfig?.sharing?.leaderboard_public ?? true} onChange={e => updateConfigField('sharing', 'leaderboard_public', e.target.checked)} />
                      <label className="text-xs text-zinc-400">Leaderboard oeffentl.</label>
                    </div>
                  </div>
                </div>
                {/* Kiosk-Verhalten */}
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 font-medium uppercase">Kiosk-Verhalten</p>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Auto-Lock (Min.)</label>
                      <input type="number" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-autolock"
                        value={deviceConfig?.kiosk?.auto_lock_timeout_min ?? 5} onChange={e => updateConfigField('kiosk', 'auto_lock_timeout_min', parseInt(e.target.value) || 5)} />
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-600 block mb-0.5">Idle-Timeout (Min.)</label>
                      <input type="number" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-idle"
                        value={deviceConfig?.kiosk?.idle_timeout_min ?? 10} onChange={e => updateConfigField('kiosk', 'idle_timeout_min', parseInt(e.target.value) || 10)} />
                    </div>
                    <div className="flex items-center gap-2 pt-4">
                      <input type="checkbox" className="rounded border-zinc-600" data-testid="cfg-fullscreen"
                        checked={deviceConfig?.kiosk?.fullscreen ?? false} onChange={e => updateConfigField('kiosk', 'fullscreen', e.target.checked)} />
                      <label className="text-xs text-zinc-400">Vollbild</label>
                    </div>
                  </div>
                </div>
                {/* Save */}
                <div className="flex justify-end">
                  <Button size="sm" disabled={configSaving || !configDirty}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs h-7"
                    onClick={saveDeviceConfig} data-testid="cfg-save-btn">
                    {configSaving ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
                    Speichern & Push
                  </Button>
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center py-6">
                <RefreshCw className="w-4 h-4 text-zinc-500 animate-spin mr-2" />
                <span className="text-xs text-zinc-500">Lade Konfiguration...</span>
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {/* Last Error */}
      {device.last_error && (
        <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-500/5 border border-red-500/20" data-testid="device-last-error">
          <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-400">Letzter Fehler</p>
            <p className="text-xs text-red-300/70 font-mono mt-0.5">{device.last_error}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left Column: Actions + Action Log + Logs */}
        <div className="lg:col-span-2 space-y-4">
          {/* Quick Actions */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <Zap className="w-4 h-4" /> Remote-Aktionen
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* v3.14.0: Primary board controls prominently displayed */}
              <div className="mb-3">
                <p className="text-[10px] text-zinc-500 uppercase font-mono mb-2">Board-Kontrolle</p>
                <div className="grid grid-cols-4 gap-2" data-testid="board-control-grid">
                  {Object.entries(ACTION_META).filter(([, m]) => m.primary).map(([key, meta]) => {
                    const Icon = meta.icon;
                    const isUnlock = key === 'unlock_board' || key === 'start_session';
                    return (
                      <button key={key} onClick={() => issueAction(key)} disabled={!!actionLoading} data-testid={`action-${key}`}
                        className={`flex items-center gap-2 p-3 rounded-lg border transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                          isUnlock ? 'border-emerald-500/30 hover:bg-emerald-500/10' : 'border-amber-500/30 hover:bg-amber-500/10'
                        }`}>
                        {actionLoading === key ? (
                          <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <Icon className={`w-4 h-4 ${isUnlock ? 'text-emerald-400' : 'text-amber-400'}`} />
                        )}
                        <div className="text-left min-w-0">
                          <span className="text-sm text-white block">{meta.label}</span>
                          <span className="text-[10px] text-zinc-600 block truncate">{meta.desc}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div>
                <p className="text-[10px] text-zinc-500 uppercase font-mono mb-2">System</p>
                <div className="grid grid-cols-3 gap-2" data-testid="remote-actions-grid">
                  {Object.entries(ACTION_META).filter(([, m]) => !m.primary).map(([key, meta]) => {
                    const Icon = meta.icon;
                    return (
                      <button key={key} onClick={() => issueAction(key)} disabled={!!actionLoading} data-testid={`action-${key}`}
                        className="flex items-center gap-2 p-3 rounded-lg border border-zinc-700/50 hover:border-zinc-600 hover:bg-zinc-800/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed">
                        {actionLoading === key ? (
                          <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <Icon className="w-4 h-4 text-zinc-400" />
                        )}
                        <div className="text-left min-w-0">
                          <span className="text-sm text-white block">{meta.label}</span>
                          <span className="text-[10px] text-zinc-600 block truncate">{meta.desc}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Action History */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <ScrollText className="w-4 h-4" /> Aktions-Verlauf
              </CardTitle>
            </CardHeader>
            <CardContent>
              {device.recent_actions?.length ? (
                <div className="space-y-1" data-testid="actions-log">
                  {device.recent_actions.map(a => {
                    const badge = STATUS_BADGE[a.status] || STATUS_BADGE.pending;
                    const duration = a.acked_at && a.issued_at
                      ? `${Math.round((new Date(a.acked_at) - new Date(a.issued_at)) / 1000)}s`
                      : null;
                    return (
                      <div key={a.id} className="flex items-center gap-2 py-2 border-b border-zinc-800/40 last:border-0" data-testid={`action-entry-${a.id}`}>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${badge.cls}`}>{badge.label}</span>
                        <span className="text-sm text-zinc-300 font-mono">{a.action_type}</span>
                        {duration && <span className="text-[10px] text-zinc-600 font-mono">{duration}</span>}
                        {a.result_message && (
                          <span className="text-[10px] text-zinc-500 truncate max-w-[200px]" title={a.result_message}>{a.result_message}</span>
                        )}
                        <span className="text-[10px] text-zinc-600 ml-auto flex-shrink-0">{a.issued_by} {a.issued_at ? timeAgo(a.issued_at) : ''}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-zinc-600">Keine Aktionen vorhanden</p>
              )}
            </CardContent>
          </Card>

          {/* Device Logs */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                  <Terminal className="w-4 h-4" /> Geraete-Logs
                </CardTitle>
                <div className="flex items-center gap-1" data-testid="log-filter">
                  {['all', 'info', 'warn', 'error'].map(f => (
                    <button key={f} onClick={() => setLogFilter(f)}
                      className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                        logFilter === f ? 'bg-zinc-700 text-white' : 'text-zinc-600 hover:text-zinc-400'
                      }`}>
                      {f === 'all' ? 'Alle' : f.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {logs.length ? (
                <div className="space-y-0.5 max-h-[400px] overflow-y-auto font-mono text-xs" data-testid="device-logs">
                  {logs.slice().reverse().map((l, i) => (
                    <div key={i} className="flex gap-2 py-1 border-b border-zinc-800/30 last:border-0 items-start" data-testid={`log-entry-${i}`}>
                      <span className="text-zinc-600 flex-shrink-0 w-[52px]">{l.ts ? l.ts.slice(11, 19) : ''}</span>
                      <span className={`flex-shrink-0 w-[38px] ${LOG_LEVEL_CLS[l.level] || 'text-zinc-500'}`}>{(l.level || '').toUpperCase()}</span>
                      <span className="text-indigo-400/70 flex-shrink-0 w-[90px] truncate">{l.src || ''}</span>
                      <span className="text-zinc-300 flex-1 break-all">{l.msg || ''}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-600">Keine Logs verfuegbar {logFilter !== 'all' ? `(Filter: ${logFilter})` : ''}</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Config Status + Daily Stats + Events */}
        <div className="space-y-4">
          {/* Config Sync Status */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <Database className="w-4 h-4" /> Config-Sync
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2" data-testid="config-sync-card">
              {hs?.config_sync ? (
                <>
                  <div className="flex justify-between items-center py-1">
                    <span className="text-xs text-zinc-500">Config-Version</span>
                    <span className="text-xs text-white font-mono">v{hs.config_sync.config_version || 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-t border-zinc-800/40">
                    <span className="text-xs text-zinc-500">Applied Version</span>
                    <span className="text-xs text-white font-mono">{hs.config_applied_version ?? '?'}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-t border-zinc-800/40">
                    <span className="text-xs text-zinc-500">Letzter Sync</span>
                    <span className="text-xs text-white">{hs.config_sync.last_sync_at ? timeAgo(hs.config_sync.last_sync_at) : 'nie'}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-t border-zinc-800/40">
                    <span className="text-xs text-zinc-500">Syncs gesamt</span>
                    <span className="text-xs text-white font-mono">{hs.config_sync.sync_count || 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-t border-zinc-800/40">
                    <span className="text-xs text-zinc-500">Sync-Fehler</span>
                    <span className={`text-xs font-mono ${hs.config_sync.consecutive_errors > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                      {hs.config_sync.consecutive_errors || 0} laufend
                    </span>
                  </div>
                  {hs.config_sync.last_error && (
                    <div className="p-2 mt-1 rounded bg-red-500/5 border border-red-500/10">
                      <p className="text-[10px] text-red-400 font-mono break-all">{hs.config_sync.last_error}</p>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-xs text-zinc-600">Kein Sync-Status verfuegbar</p>
              )}
            </CardContent>
          </Card>

          {/* Action Poller Status */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <HeartPulse className="w-4 h-4" /> Action-Poller
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2" data-testid="action-poller-card">
              {hs?.action_poller ? (
                <>
                  <div className="flex justify-between items-center py-1">
                    <span className="text-xs text-zinc-500">Letzter Poll</span>
                    <span className="text-xs text-white">{hs.action_poller.last_poll_at ? timeAgo(hs.action_poller.last_poll_at) : 'nie'}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-t border-zinc-800/40">
                    <span className="text-xs text-zinc-500">Ausgefuehrt</span>
                    <span className="text-xs text-emerald-400 font-mono">{hs.action_poller.actions_executed || 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-t border-zinc-800/40">
                    <span className="text-xs text-zinc-500">Fehlgeschlagen</span>
                    <span className={`text-xs font-mono ${hs.action_poller.actions_failed > 0 ? 'text-red-400' : 'text-zinc-400'}`}>{hs.action_poller.actions_failed || 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-t border-zinc-800/40">
                    <span className="text-xs text-zinc-500">Poll-Fehler</span>
                    <span className={`text-xs font-mono ${hs.action_poller.consecutive_poll_errors > 0 ? 'text-amber-400' : 'text-zinc-400'}`}>{hs.action_poller.consecutive_poll_errors || 0}</span>
                  </div>
                  {hs.action_poller.last_error && (
                    <div className="p-2 mt-1 rounded bg-red-500/5 border border-red-500/10">
                      <p className="text-[10px] text-red-400 font-mono break-all">{hs.action_poller.last_error}</p>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-xs text-zinc-600">Kein Poller-Status verfuegbar</p>
              )}
            </CardContent>
          </Card>

          {/* Daily Stats */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <BarChart3 className="w-4 h-4" /> Letzte 7 Tage
              </CardTitle>
            </CardHeader>
            <CardContent>
              {device.daily_stats?.length ? (
                <div className="space-y-1" data-testid="daily-stats">
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
                <Activity className="w-4 h-4" /> Letzte Events
              </CardTitle>
            </CardHeader>
            <CardContent>
              {device.recent_events?.length ? (
                <div className="space-y-1" data-testid="recent-events">
                  {device.recent_events.map((e, i) => (
                    <div key={i} className="flex items-center gap-2 py-1 border-b border-zinc-800/30 last:border-0">
                      <span className="text-xs text-indigo-400 font-mono">{e.event_type}</span>
                      <span className="text-[10px] text-zinc-600 ml-auto">{e.timestamp ? timeAgo(e.timestamp) : ''}</span>
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

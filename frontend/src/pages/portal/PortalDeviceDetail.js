import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ArrowLeft, Monitor, RefreshCw, RotateCcw,
  Globe, Clock, Activity, AlertTriangle, CheckCircle,
  XCircle, WifiOff, Shield, ShieldOff, ShieldAlert,
  Settings2, Save, ChevronDown, ChevronUp, Unlock, Lock, Play, Square, Hash, Sparkles
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { ProductBackLink, ProductCallout, ProductDetailCard, ProductHero, ProductInlineActions, ProductKeyValueList, ProductMetricGrid } from '../../components/shell/ProductDetail';
import { ProductStatusBadge } from '../../components/shell/ProductDataDisplay';
import { ProductLogPanel, ProductOpsRail, ProductTimelinePanel } from '../../components/shell/ProductSurfaceSystems';
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
  const location = useLocation();
  const { apiBase, authHeaders } = useCentralAuth();
  const [device, setDevice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null); // { type, message, retryable }
  const [actionLoading, setActionLoading] = useState(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [logFilter, setLogFilter] = useState('all');
  const [configExpanded, setConfigExpanded] = useState(false);
  const [configTab, setConfigTab] = useState('branding');
  const [deviceConfig, setDeviceConfig] = useState(null);
  const [configSaving, setConfigSaving] = useState(false);
  const [configDirty, setConfigDirty] = useState(false);
  const [unlockOpen, setUnlockOpen] = useState(false);
  const [unlockParams, setUnlockParams] = useState({
    pricing_mode: 'per_player', game_type: '501', credits: 3, minutes: 30, price_total: 0, players_count: 0, board_id: '',
  });

  const classifyError = (err) => {
    const status = err?.response?.status;
    const isTimeout = err?.code === 'ECONNABORTED' || err?.message?.includes('timeout');
    const isNetwork = !err?.response && (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error');

    if (status === 404) return { type: 'not_found', message: 'Geraet existiert nicht in der Datenbank.', retryable: false };
    if (status === 401) return { type: 'auth', message: 'Sitzung abgelaufen. Bitte erneut einloggen.', retryable: false };
    if (status === 403) return { type: 'forbidden', message: 'Keine Berechtigung fuer dieses Geraet.', retryable: false };
    if (status === 502) return { type: 'server_down', message: 'Zentraler Server nicht erreichbar (502).', retryable: true };
    if (status === 504) return { type: 'server_timeout', message: 'Zentraler Server antwortet nicht (504 Timeout).', retryable: true };
    if (isTimeout) return { type: 'timeout', message: 'Verbindung zu langsam oder fehlgeschlagen.', retryable: true };
    if (isNetwork) return { type: 'network', message: 'Netzwerkfehler — keine Verbindung zum Server.', retryable: true };
    return { type: 'unknown', message: err?.response?.data?.detail || err?.response?.data?.message || `Unbekannter Fehler (HTTP ${status || '?'}).`, retryable: true };
  };

  const fetchDevice = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await axios.get(`${apiBase}/telemetry/device/${deviceId}`, { headers: authHeaders, timeout: 15000 });
      setDevice(res.data);
      setFetchError(null);
    } catch (err) {
      const classified = classifyError(err);
      setFetchError(classified);
      setDevice(null);
      console.error(`[DeviceDetail] Fetch failed: type=${classified.type} status=${err?.response?.status}`, err);
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

  const issueAction = async (actionType, params = null) => {
    setActionLoading(actionType);
    try {
      const body = { action_type: actionType };
      if (params) body.params = params;
      await axios.post(`${apiBase}/remote-actions/${deviceId}`, body, {
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
      });
      toast.success(`Aktion "${ACTION_META[actionType]?.label || actionType}" gesendet`);
      setTimeout(fetchDevice, 1500);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Aktion fehlgeschlagen');
    } finally {
      setActionLoading(null);
    }
  };

  const handleBoardAction = (actionType) => {
    if (actionType === 'unlock_board' || actionType === 'start_session') {
      setUnlockOpen(true);
    } else {
      issueAction(actionType);
    }
  };

  const confirmUnlock = () => {
    const params = { ...unlockParams };
    if (!params.board_id) delete params.board_id; // let action_poller auto-discover
    issueAction('unlock_board', params);
    setUnlockOpen(false);
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
      <div className="flex items-center justify-center h-64" data-testid="device-detail-loading">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // ── Error states — each type gets its own clear UI ──
  if (fetchError) {
    const iconMap = {
      not_found: <XCircle className="w-12 h-12 text-red-500" />,
      auth: <ShieldAlert className="w-12 h-12 text-amber-500" />,
      forbidden: <Shield className="w-12 h-12 text-amber-500" />,
      server_down: <WifiOff className="w-12 h-12 text-red-400" />,
      server_timeout: <Clock className="w-12 h-12 text-orange-400" />,
      timeout: <Clock className="w-12 h-12 text-orange-400" />,
      network: <WifiOff className="w-12 h-12 text-red-400" />,
      unknown: <AlertTriangle className="w-12 h-12 text-zinc-500" />,
    };
    const titleMap = {
      not_found: 'Geraet existiert nicht',
      auth: 'Authentifizierung fehlgeschlagen',
      forbidden: 'Zugriff verweigert',
      server_down: 'Server nicht erreichbar',
      server_timeout: 'Server-Timeout',
      timeout: 'Verbindung fehlgeschlagen',
      network: 'Netzwerkfehler',
      unknown: 'Unbekannter Fehler',
    };

    return (
      <div className="text-center py-16 space-y-4" data-testid={`device-error-${fetchError.type}`}>
        <div className="mx-auto w-fit">{iconMap[fetchError.type] || iconMap.unknown}</div>
        <h2 className="text-lg font-semibold text-white">{titleMap[fetchError.type] || 'Fehler'}</h2>
        <p className="text-sm text-zinc-400 max-w-md mx-auto">{fetchError.message}</p>
        <p className="text-xs text-zinc-600 font-mono">Device ID: {deviceId}</p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button onClick={() => navigate(location.pathname.startsWith('/operator') ? '/operator/devices' : '/portal/devices')} variant="outline" className="border-zinc-700 text-zinc-400" data-testid="error-back-btn">
            <ArrowLeft className="w-4 h-4 mr-2" /> Zurueck zur Liste
          </Button>
          {fetchError.retryable && (
            <Button onClick={fetchDevice} className="bg-indigo-600 hover:bg-indigo-700 text-white" data-testid="error-retry-btn">
              <RefreshCw className="w-4 h-4 mr-2" /> Erneut versuchen
            </Button>
          )}
        </div>
      </div>
    );
  }

  // Should never happen: no error, no device, not loading
  if (!device) {
    return (
      <div className="text-center py-16" data-testid="device-error-unexpected">
        <AlertTriangle className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
        <p className="text-zinc-500">Unerwarteter Zustand — kein Geraet geladen.</p>
        <Button onClick={fetchDevice} className="mt-4 bg-indigo-600 text-white" data-testid="error-reload-btn">
          <RefreshCw className="w-4 h-4 mr-2" /> Neu laden
        </Button>
      </div>
    );
  }

  // v3.15.2: Consistent connectivity status from backend (online/degraded/offline)
  const connectivity = device.connectivity || (device.is_online ? 'online' : 'offline');
  const isOnline = connectivity === 'online';
  const hs = device.health_snapshot;
  const healthKey = connectivity === 'offline' ? 'offline' : connectivity === 'degraded' ? 'degraded' : (hs?.health_status || 'unknown');
  const healthMeta = HEALTH_BADGE[healthKey] || HEALTH_BADGE.unknown;
  const HealthIcon = healthMeta.icon;
  const healthReason = getHealthReason(hs, isOnline);

  const logs = (device.device_logs || []).filter(l =>
    logFilter === 'all' || l.level === logFilter
  );
  const surfacePrefix = location.pathname.startsWith('/operator') ? '/operator' : '/portal';
  const isOperatorSurface = surfacePrefix === '/operator';
  const searchParams = new URLSearchParams(location.search || '');
  const returnTo = searchParams.get('returnTo') || `${surfacePrefix}/devices`;
  const returnLabel = searchParams.get('returnLabel') || 'Geräte';
  const deviceListPath = returnTo;
  const licenseDetailPath = device.license_id ? `${surfacePrefix}/licenses/${device.license_id}?intent=devices&returnTo=${encodeURIComponent(`${location.pathname}${location.search || ''}`)}&returnLabel=${encodeURIComponent(device.device_name || device.id.slice(0, 8))}` : null;
  const actionTone = healthKey === 'offline' ? 'red' : healthKey === 'degraded' ? 'amber' : 'blue';
  const heroActions = [
    ...(licenseDetailPath ? [{ label: 'Lizenz öffnen', onClick: () => navigate(licenseDetailPath), trailingIcon: Hash, className: 'border-zinc-700 text-zinc-200 hover:bg-zinc-800' }] : []),
    { label: 'Neu laden', onClick: fetchDevice, trailingIcon: RefreshCw, className: 'border-zinc-700 text-zinc-200 hover:bg-zinc-800' },
    { label: returnLabel, onClick: () => navigate(deviceListPath), className: 'border-zinc-700 text-zinc-200 hover:bg-zinc-800' },
  ];
  const summaryItems = [
    { label: 'Version', value: device.reported_version || '—', tid: 'device-summary-version' },
    { label: 'Letzter Heartbeat', value: device.last_heartbeat_at ? timeAgo(device.last_heartbeat_at) : 'nie', tid: 'device-summary-heartbeat' },
    { label: 'Install-ID', value: device.install_id ? `${device.install_id.slice(0, 12)}...` : '—', tid: 'device-install-id' },
    { label: 'Lizenz', value: device.license_id ? `${device.license_id.slice(0, 12)}...` : 'Keine', tid: 'device-summary-license' },
    { label: 'Config-Version', value: hs?.config_applied_version ?? '—', tid: 'device-summary-config' },
    { label: 'Binding', value: device.binding_status || 'Unbekannt', tid: 'device-binding-status' },
    { label: 'WS Push', value: hs?.ws_push?.connected ? 'Verbunden' : (hs?.ws_push?.configured ? 'Getrennt' : 'Nicht konfiguriert'), tid: 'device-summary-ws' },
    { label: 'Offline Queue', value: hs?.offline_queue?.pending > 0 ? `${hs.offline_queue.pending} ausstehend` : 'Leer', tid: 'device-summary-queue' },
  ];
  const syncRows = [
    { label: 'Config-Version', value: hs?.config_sync?.config_version != null ? `v${hs.config_sync.config_version}` : '—', detail: 'Zentral gemeldete Version', meta: hs?.config_applied_version != null ? `Applied: ${hs.config_applied_version}` : null },
    { label: 'Letzter Sync', value: hs?.config_sync?.last_sync_at ? timeAgo(hs.config_sync.last_sync_at) : 'nie', detail: 'Zuletzt bestätigte Konfigurationsabholung', meta: `${hs?.config_sync?.sync_count ?? 0} Syncs gesamt` },
    { label: 'Fehlerlage', value: `${hs?.config_sync?.consecutive_errors ?? 0} laufend`, detail: 'Konsekutive Sync-Fehler', meta: hs?.config_sync?.last_error || null },
  ];
  const actionPollerRows = [
    { label: 'Letzter Poll', value: hs?.action_poller?.last_poll_at ? timeAgo(hs.action_poller.last_poll_at) : 'nie', detail: 'Abholung offener Remote-Aktionen', meta: hs?.action_poller?.last_action_at ? `Letzte Aktion ${timeAgo(hs.action_poller.last_action_at)}` : null },
    { label: 'Ausgeführt', value: String(hs?.action_poller?.actions_executed ?? 0), detail: 'Erfolgreich bestätigte Aktionen', meta: `${hs?.action_poller?.actions_failed ?? 0} fehlgeschlagen` },
    { label: 'Poll-Fehler', value: String(hs?.action_poller?.consecutive_poll_errors ?? 0), detail: 'Aktuelle Fehlerkette des Pollers', meta: hs?.action_poller?.last_error || null },
  ];
  const queueRows = [
    { label: 'Pending', value: hs?.offline_queue?.pending > 0 ? `${hs.offline_queue.pending} ausstehend` : 'Leer', detail: 'Noch nicht drainte Offline-Operationen', meta: hs?.offline_queue?.last_drain_at ? `Letzter Drain ${timeAgo(hs.offline_queue.last_drain_at)}` : null },
    { label: 'Drain total', value: String(hs?.offline_queue?.drained_total ?? 0), detail: 'Erfolgreich gesendete Queue-Einträge', meta: `${hs?.offline_queue?.dropped_total ?? 0} verworfen` },
    { label: 'Queue-Fehler', value: hs?.offline_queue?.last_drain_error ? 'Fehler vorhanden' : 'Keine', detail: 'Letzter Drain-/Queue-Fehler', meta: hs?.offline_queue?.last_drain_error || null },
  ];
  const wsRows = [
    { label: 'Push-Verbindung', value: hs?.ws_push?.connected ? 'Verbunden' : (hs?.ws_push?.configured ? 'Getrennt' : 'Nicht konfiguriert'), detail: 'Websocket-Anbindung zum Central Server', meta: hs?.ws_push?.connected ? `${hs?.ws_push?.events_received ?? 0} Events empfangen` : null },
    { label: 'Reconnects', value: String(hs?.ws_push?.reconnect_count ?? 0), detail: 'Neuaufbau der WS-Verbindung', meta: hs?.ws_push?.last_error || null },
  ];

  return (
    <div data-testid="device-detail-page" className="mx-auto max-w-7xl space-y-6 p-6">
      <ProductHero
        eyebrow={isOperatorSurface ? 'Operator device detail' : 'Portal device detail'}
        title={device.device_name || device.id.slice(0, 8)}
        description={device.customer?.name ? `${device.customer.name}${device.location?.name ? ` → ${device.location.name}` : ''}` : device.id}
        tone={actionTone}
        backAction={<ProductBackLink data-testid="device-back-btn" label={returnLabel} onClick={() => navigate(deviceListPath)} />}
        badge={(
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${healthMeta.cls}`} data-testid="device-health-badge">
              <HealthIcon className="w-3 h-3" />
              {healthMeta.label}
            </span>
            <ProductStatusBadge kind="device" value={device.status === 'inactive' ? 'disabled' : device.status} className="capitalize" />
            <ProductStatusBadge kind="binding" value={device.binding_status || 'unbound'} />
          </div>
        )}
        actions={<ProductInlineActions mode={isOperatorSurface ? 'operator' : 'read-only'} items={heroActions} />}
        data-testid="device-detail-hero"
      >
        <ProductCallout
          tone={healthReason && healthKey !== 'healthy' ? actionTone : 'blue'}
          eyebrow="Operational posture"
          title={healthReason && healthKey !== 'healthy' ? (healthKey === 'offline' ? 'Gerät nicht erreichbar' : 'Eingeschränkte Funktion') : 'Gerät wirkt stabil'}
          description={healthReason || 'Heartbeat, Sync und Action-Poller wirken aktuell konsistent.'}
          icon={healthReason && healthKey !== 'healthy' ? AlertTriangle : Sparkles}
          data-testid="device-health-reason"
        />

        <ProductMetricGrid columns="xl:grid-cols-4" data-testid="device-status-grid">
          <StatusCell label="Version" value={device.reported_version} />
          <StatusCell label="Letzter Heartbeat" value={device.last_heartbeat_at ? timeAgo(device.last_heartbeat_at) : null} sub={device.last_heartbeat_at ? new Date(device.last_heartbeat_at).toLocaleString('de-DE') : null} />
          <StatusCell label="Letzter Sync" value={hs?.config_sync?.last_sync_at ? timeAgo(hs.config_sync.last_sync_at) : null} sub={`${hs?.config_sync?.sync_count ?? 0} Syncs, ${hs?.config_sync?.consecutive_errors ?? 0} Fehler`} />
          <StatusCell label="Letzte Aktion" value={hs?.action_poller?.last_action_at ? timeAgo(hs.action_poller.last_action_at) : null} sub={`${hs?.action_poller?.actions_executed ?? 0} OK, ${hs?.action_poller?.actions_failed ?? 0} Fehler`} />
          <StatusCell label="Offline Queue" value={hs?.offline_queue?.pending > 0 ? `${hs.offline_queue.pending} ausstehend` : 'Leer'} sub={hs?.offline_queue?.last_drain_at ? `Letzter Drain: ${timeAgo(hs.offline_queue.last_drain_at)}` : `${hs?.offline_queue?.drained_total ?? 0} gesendet, ${hs?.offline_queue?.dropped_total ?? 0} verworfen`} />
          <StatusCell label="WS Push" value={hs?.ws_push?.connected ? 'Verbunden' : (hs?.ws_push?.configured ? 'Getrennt' : 'Nicht konfiguriert')} sub={hs?.ws_push?.connected ? `${hs.ws_push.events_received ?? 0} Events` : (hs?.ws_push?.last_error ? `Fehler: ${hs.ws_push.last_error}` : (hs?.ws_push?.reconnect_count > 0 ? `${hs.ws_push.reconnect_count} Reconnects` : null))} />
          <StatusCell label="Config Version" value={hs?.config_applied_version ?? '\u2014'} sub={hs?.config_sync?.config_version ? `Zentral: v${hs.config_sync.config_version}` : null} />
          <StatusCell label="Lizenz" value={device.license_id ? 'Gebunden' : 'Keine'} sub={device.license_id ? device.license_id.slice(0, 12) + '...' : null} />
        </ProductMetricGrid>
      </ProductHero>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(340px,0.9fr)]">
        <div className="space-y-6">
          <ProductDetailCard
            title="Geräte-Anatomie"
            eyebrow="Identity & continuity"
            description="Shared Detail-Anatomie für Portal- und Operator-Drill-ins."
            data-testid="device-trust-card"
            actions={(
              <div className="flex flex-wrap items-center gap-2">
                {device.status !== 'active' && (
                  <Button size="sm" variant="outline" disabled={statusLoading}
                    className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 text-xs h-8"
                    onClick={() => changeDeviceStatus('active')} data-testid="device-activate-btn">
                    <CheckCircle className="w-3 h-3 mr-1" /> Aktivieren
                  </Button>
                )}
                {device.status === 'active' && (
                  <Button size="sm" variant="outline" disabled={statusLoading}
                    className="border-amber-500/30 text-amber-400 hover:bg-amber-500/10 text-xs h-8"
                    onClick={() => changeDeviceStatus('inactive')} data-testid="device-deactivate-btn">
                    <ShieldOff className="w-3 h-3 mr-1" /> Deaktivieren
                  </Button>
                )}
                {device.status !== 'blocked' && (
                  <Button size="sm" variant="outline" disabled={statusLoading}
                    className="border-red-500/30 text-red-400 hover:bg-red-500/10 text-xs h-8"
                    onClick={() => changeDeviceStatus('blocked')} data-testid="device-block-btn">
                    <ShieldAlert className="w-3 h-3 mr-1" /> Sperren
                  </Button>
                )}
              </div>
            )}
          >
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span data-testid="device-name" className="text-lg font-semibold text-white">{device.device_name || device.id.slice(0, 8)}</span>
                <ProductStatusBadge kind="connectivity" value={connectivity} />
                <ProductStatusBadge kind="binding" value={device.binding_status || 'unbound'} />
                <ProductStatusBadge kind="device" value={device.status === 'inactive' ? 'disabled' : device.status} />
                {licenseDetailPath ? <ProductStatusBadge kind="license" value="active" label="Lizenz verknüpft" /> : null}
              </div>
              <ProductKeyValueList items={summaryItems} columns={2} />
            </div>
          </ProductDetailCard>

      {/* Device Config — v3.15.0: Full tabbed config matching local admin */}
      <Card className="bg-zinc-900 border-zinc-800" data-testid="device-quick-config">
        <CardHeader className="pb-2 cursor-pointer" onClick={() => setConfigExpanded(!configExpanded)}>
          <CardTitle className="text-sm text-zinc-400 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Settings2 className="w-4 h-4" /> Device-Konfiguration
              <span className="text-[9px] text-zinc-600 bg-zinc-800 px-1.5 py-0.5 rounded">Overrides — ueberschreibt globale Defaults</span>
              {configDirty && <span className="text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">Ungespeichert</span>}
            </span>
            {configExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </CardTitle>
        </CardHeader>
        {configExpanded && (
          <CardContent>
            {deviceConfig ? (
              <div className="space-y-4">
                {/* Config Tabs */}
                <Tabs value={configTab} onValueChange={setConfigTab}>
                  <TabsList className="bg-zinc-800 border border-zinc-700 w-full flex flex-wrap h-auto gap-0.5 p-1">
                    {[
                      { id: 'branding', label: 'Branding' },
                      { id: 'pricing', label: 'Preise' },
                      { id: 'sound', label: 'Sound' },
                      { id: 'stammkunde', label: 'Stammkunde' },
                      { id: 'colors', label: 'Farben' },
                      { id: 'kiosk', label: 'Kiosk' },
                      { id: 'sharing', label: 'Sharing' },
                    ].map(t => (
                      <TabsTrigger key={t.id} value={t.id} data-testid={`cfg-tab-${t.id}`}
                        className="text-xs px-2 py-1 data-[state=active]:bg-indigo-600 data-[state=active]:text-white">
                        {t.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>

                  {/* Branding Tab */}
                  <TabsContent value="branding" className="space-y-3 mt-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-[10px] text-zinc-500 block mb-1">Cafe Name</label>
                        <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" data-testid="cfg-cafe-name"
                          value={deviceConfig?.branding?.cafe_name || ''} onChange={e => updateConfigField('branding', 'cafe_name', e.target.value)} />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-500 block mb-1">Untertitel</label>
                        <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" data-testid="cfg-subtitle"
                          value={deviceConfig?.branding?.subtitle || ''} onChange={e => updateConfigField('branding', 'subtitle', e.target.value)} />
                      </div>
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-500 block mb-1">Logo URL</label>
                      <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" data-testid="cfg-logo-url"
                        placeholder="https://..." value={deviceConfig?.branding?.logo_url || ''} onChange={e => updateConfigField('branding', 'logo_url', e.target.value)} />
                    </div>
                  </TabsContent>

                  {/* Pricing Tab — v3.15.0: Full parity with local admin */}
                  <TabsContent value="pricing" className="space-y-3 mt-3">
                    <div>
                      <label className="text-[10px] text-zinc-500 block mb-1">Standard-Modus</label>
                      <div className="grid grid-cols-3 gap-2">
                        {[{v:'per_game',l:'Pro Spiel'},{v:'per_time',l:'Pro Zeit'},{v:'per_player',l:'Pro Spieler'}].map(m => (
                          <button key={m.v} onClick={() => updateConfigField('pricing','mode',m.v)} data-testid={`cfg-mode-${m.v}`}
                            className={`p-2 rounded border text-xs transition-all ${deviceConfig?.pricing?.mode===m.v ? 'border-indigo-500 bg-indigo-500/20 text-indigo-300' : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'}`}>
                            {m.l}
                          </button>
                        ))}
                      </div>
                    </div>
                    {/* Per Game */}
                    <div className="bg-zinc-800/50 rounded p-3 space-y-2">
                      <p className="text-[10px] text-zinc-500 uppercase">Pro Spiel</p>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[10px] text-zinc-600 block mb-0.5">Preis/Spiel (EUR)</label>
                          <input type="number" step="0.5" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-per-game-price"
                            value={deviceConfig?.pricing?.per_game?.price_per_credit ?? 2} onChange={e => {
                              const pg = { ...(deviceConfig?.pricing?.per_game || {}), price_per_credit: parseFloat(e.target.value) || 0 };
                              updateConfigField('pricing', 'per_game', pg);
                            }} />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-600 block mb-0.5">Standard Credits</label>
                          <input type="number" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-per-game-credits"
                            value={deviceConfig?.pricing?.per_game?.default_credits ?? 3} onChange={e => {
                              const pg = { ...(deviceConfig?.pricing?.per_game || {}), default_credits: parseInt(e.target.value) || 1 };
                              updateConfigField('pricing', 'per_game', pg);
                            }} />
                        </div>
                      </div>
                    </div>
                    {/* Per Time */}
                    <div className="bg-zinc-800/50 rounded p-3 space-y-2">
                      <p className="text-[10px] text-zinc-500 uppercase">Pro Zeit</p>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[10px] text-zinc-600 block mb-0.5">30 Min (EUR)</label>
                          <input type="number" step="0.5" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-per-time-30"
                            value={deviceConfig?.pricing?.per_time?.price_per_30_min ?? 5} onChange={e => {
                              const pt = { ...(deviceConfig?.pricing?.per_time || {}), price_per_30_min: parseFloat(e.target.value) || 0 };
                              updateConfigField('pricing', 'per_time', pt);
                            }} />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-600 block mb-0.5">60 Min (EUR)</label>
                          <input type="number" step="0.5" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-per-time-60"
                            value={deviceConfig?.pricing?.per_time?.price_per_60_min ?? 8} onChange={e => {
                              const pt = { ...(deviceConfig?.pricing?.per_time || {}), price_per_60_min: parseFloat(e.target.value) || 0 };
                              updateConfigField('pricing', 'per_time', pt);
                            }} />
                        </div>
                      </div>
                    </div>
                    {/* Per Player */}
                    <div className="bg-zinc-800/50 rounded p-3 space-y-2">
                      <p className="text-[10px] text-zinc-500 uppercase">Pro Spieler</p>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[10px] text-zinc-600 block mb-0.5">Preis/Spieler (EUR)</label>
                          <input type="number" step="0.5" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-per-player-price"
                            value={deviceConfig?.pricing?.per_player?.price_per_player ?? 1.5} onChange={e => {
                              const pp = { ...(deviceConfig?.pricing?.per_player || {}), price_per_player: parseFloat(e.target.value) || 0 };
                              updateConfigField('pricing', 'per_player', pp);
                            }} />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-600 block mb-0.5">Max. Spieler</label>
                          <input type="number" min="1" max="8" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-max-players"
                            value={deviceConfig?.pricing?.max_players ?? 4} onChange={e => updateConfigField('pricing', 'max_players', parseInt(e.target.value) || 4)} />
                        </div>
                      </div>
                    </div>
                    {/* Game Types */}
                    <div>
                      <label className="text-[10px] text-zinc-500 block mb-1">Erlaubte Spielarten</label>
                      <div className="flex flex-wrap gap-1">
                        {['301','501','Cricket','Training','Around the Clock','Shanghai'].map(g => {
                          const types = deviceConfig?.pricing?.allowed_game_types || ['301','501','Cricket'];
                          const active = types.includes(g);
                          return (
                            <button key={g} data-testid={`cfg-game-${g}`} onClick={() => {
                              const newTypes = active ? types.filter(t => t !== g) : [...types, g];
                              updateConfigField('pricing', 'allowed_game_types', newTypes);
                            }} className={`px-2 py-1 rounded text-[10px] border transition-all ${active ? 'border-indigo-500 bg-indigo-500/20 text-indigo-300' : 'border-zinc-700 text-zinc-500'}`}>
                              {g}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </TabsContent>

                  {/* Sound Tab — v3.15.0 */}
                  <TabsContent value="sound" className="space-y-3 mt-3">
                    <div className="flex items-center justify-between bg-zinc-800/50 rounded p-3 border border-zinc-700">
                      <span className="text-xs text-zinc-300">Sound-Effekte</span>
                      <input type="checkbox" className="rounded border-zinc-600" data-testid="cfg-sound-enabled"
                        checked={deviceConfig?.sound?.enabled ?? true} onChange={e => updateConfigField('sound', 'enabled', e.target.checked)} />
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-500 block mb-1">Lautstaerke: {deviceConfig?.sound?.volume ?? 70}%</label>
                      <input type="range" min="0" max="100" step="5" className="w-full accent-indigo-500" data-testid="cfg-sound-volume"
                        value={deviceConfig?.sound?.volume ?? 70} onChange={e => updateConfigField('sound', 'volume', parseInt(e.target.value))} />
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-500 block mb-1">Sound-Pack</label>
                      <div className="flex gap-1">
                        {['classic','arcade','minimal'].map(p => (
                          <button key={p} data-testid={`cfg-spack-${p}`} onClick={() => updateConfigField('sound','sound_pack',p)}
                            className={`px-2 py-1 rounded text-[10px] border ${deviceConfig?.sound?.sound_pack===p ? 'border-indigo-500 bg-indigo-500/20 text-indigo-300' : 'border-zinc-700 text-zinc-400'}`}>
                            {p}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-500 block mb-1">Rate Limit: {deviceConfig?.sound?.rate_limit_ms ?? 1000}ms</label>
                      <input type="range" min="500" max="5000" step="250" className="w-full accent-indigo-500" data-testid="cfg-sound-rate"
                        value={deviceConfig?.sound?.rate_limit_ms ?? 1000} onChange={e => updateConfigField('sound', 'rate_limit_ms', parseInt(e.target.value))} />
                    </div>
                    <div className="flex items-center justify-between bg-zinc-800/50 rounded p-3 border border-zinc-700">
                      <span className="text-xs text-zinc-300">Ruhezeiten</span>
                      <input type="checkbox" className="rounded border-zinc-600" data-testid="cfg-quiet-hours"
                        checked={deviceConfig?.sound?.quiet_hours_enabled ?? false} onChange={e => updateConfigField('sound', 'quiet_hours_enabled', e.target.checked)} />
                    </div>
                    {deviceConfig?.sound?.quiet_hours_enabled && (
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[10px] text-zinc-600 block mb-0.5">Von</label>
                          <input type="time" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-quiet-start"
                            value={deviceConfig?.sound?.quiet_hours_start || '22:00'} onChange={e => updateConfigField('sound', 'quiet_hours_start', e.target.value)} />
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-600 block mb-0.5">Bis</label>
                          <input type="time" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-quiet-end"
                            value={deviceConfig?.sound?.quiet_hours_end || '08:00'} onChange={e => updateConfigField('sound', 'quiet_hours_end', e.target.value)} />
                        </div>
                      </div>
                    )}
                    <div>
                      <label className="text-[10px] text-zinc-500 block mb-1">Sprache</label>
                      <select className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" data-testid="cfg-language"
                        value={deviceConfig?.language?.default || 'de'} onChange={e => updateConfigField('language', 'default', e.target.value)}>
                        <option value="de">Deutsch</option>
                        <option value="en">English</option>
                      </select>
                    </div>
                  </TabsContent>

                  {/* Stammkunde Tab — v3.15.0 */}
                  <TabsContent value="stammkunde" className="space-y-3 mt-3">
                    <div className="flex items-center justify-between bg-zinc-800/50 rounded p-3 border border-zinc-700">
                      <div>
                        <span className="text-xs text-zinc-300">Top Stammkunden auf Lockscreen</span>
                        <p className="text-[10px] text-zinc-600 mt-0.5">Registrierte Top-Spieler auf dem gesperrten Bildschirm anzeigen</p>
                      </div>
                      <input type="checkbox" className="rounded border-zinc-600" data-testid="cfg-stammkunde-enabled"
                        checked={deviceConfig?.stammkunde_display?.enabled ?? true} onChange={e => updateConfigField('stammkunde_display', 'enabled', e.target.checked)} />
                    </div>
                    {deviceConfig?.stammkunde_display?.enabled && (
                      <>
                        <div>
                          <label className="text-[10px] text-zinc-500 block mb-1">Zeitraum</label>
                          <div className="grid grid-cols-4 gap-1">
                            {[{v:'today',l:'Heute'},{v:'week',l:'Woche'},{v:'month',l:'Monat'},{v:'all',l:'Gesamt'}].map(p => (
                              <button key={p.v} data-testid={`cfg-sk-period-${p.v}`} onClick={() => updateConfigField('stammkunde_display','period',p.v)}
                                className={`px-2 py-1 rounded text-[10px] border ${deviceConfig?.stammkunde_display?.period===p.v ? 'border-indigo-500 bg-indigo-500/20 text-indigo-300' : 'border-zinc-700 text-zinc-400'}`}>
                                {p.l}
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="text-[10px] text-zinc-600 block mb-0.5">Rotation (Sek.)</label>
                            <input type="number" min="5" max="8" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-sk-interval"
                              value={deviceConfig?.stammkunde_display?.interval_seconds ?? 6} onChange={e => updateConfigField('stammkunde_display', 'interval_seconds', parseInt(e.target.value) || 6)} />
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-600 block mb-0.5">Max. Eintraege</label>
                            <input type="number" min="1" max="3" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-sk-max"
                              value={deviceConfig?.stammkunde_display?.max_entries ?? 3} onChange={e => updateConfigField('stammkunde_display', 'max_entries', parseInt(e.target.value) || 3)} />
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-600 block mb-0.5">Nick Max Laenge</label>
                            <input type="number" min="8" max="30" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-sk-nick"
                              value={deviceConfig?.stammkunde_display?.nickname_max_length ?? 15} onChange={e => updateConfigField('stammkunde_display', 'nickname_max_length', parseInt(e.target.value) || 15)} />
                          </div>
                        </div>
                      </>
                    )}
                  </TabsContent>

                  {/* Colors Tab */}
                  <TabsContent value="colors" className="space-y-3 mt-3">
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        {k:'primary_color',l:'Primaerfarbe',d:'#6366f1'},
                        {k:'secondary_color',l:'Sekundaerfarbe',d:'#1e1b4b'},
                        {k:'accent_color',l:'Akzentfarbe',d:'#f59e0b'},
                      ].map(c => (
                        <div key={c.k}>
                          <label className="text-[10px] text-zinc-500 block mb-1">{c.l}</label>
                          <div className="flex items-center gap-1">
                            <input type="color" className="w-6 h-6 border border-zinc-700 rounded cursor-pointer" data-testid={`cfg-${c.k}`}
                              value={deviceConfig?.branding?.[c.k] || c.d} onChange={e => updateConfigField('branding', c.k, e.target.value)} />
                            <input className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white font-mono"
                              value={deviceConfig?.branding?.[c.k] || ''} onChange={e => updateConfigField('branding', c.k, e.target.value)} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </TabsContent>

                  {/* Kiosk Tab */}
                  <TabsContent value="kiosk" className="space-y-3 mt-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-[10px] text-zinc-500 block mb-1">Willkommenstitel</label>
                        <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" data-testid="cfg-welcome-title"
                          value={deviceConfig?.texts?.welcome_title || ''} onChange={e => updateConfigField('texts', 'welcome_title', e.target.value)} />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-500 block mb-1">Untertitel</label>
                        <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" data-testid="cfg-welcome-sub"
                          value={deviceConfig?.texts?.welcome_subtitle || ''} onChange={e => updateConfigField('texts', 'welcome_subtitle', e.target.value)} />
                      </div>
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-500 block mb-1">Autodarts URL</label>
                      <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" data-testid="cfg-autodarts-url"
                        placeholder="https://play.autodarts.io" value={deviceConfig?.boards?.autodarts_url || ''} onChange={e => updateConfigField('boards', 'autodarts_url', e.target.value)} />
                    </div>
                    <div>
                      <label className="text-[10px] text-zinc-500 block mb-1">Board Name</label>
                      <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" data-testid="cfg-board-name"
                        value={deviceConfig?.boards?.board_name || ''} onChange={e => updateConfigField('boards', 'board_name', e.target.value)} />
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="text-[10px] text-zinc-500 block mb-1">Auto-Lock (Min.)</label>
                        <input type="number" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-autolock"
                          value={deviceConfig?.kiosk?.auto_lock_timeout_min ?? 5} onChange={e => updateConfigField('kiosk', 'auto_lock_timeout_min', parseInt(e.target.value) || 5)} />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-500 block mb-1">Idle-Timeout (Min.)</label>
                        <input type="number" className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-white" data-testid="cfg-idle"
                          value={deviceConfig?.kiosk?.idle_timeout_min ?? 10} onChange={e => updateConfigField('kiosk', 'idle_timeout_min', parseInt(e.target.value) || 10)} />
                      </div>
                      <div className="flex items-center gap-2 pt-5">
                        <input type="checkbox" className="rounded border-zinc-600" data-testid="cfg-fullscreen"
                          checked={deviceConfig?.kiosk?.fullscreen ?? false} onChange={e => updateConfigField('kiosk', 'fullscreen', e.target.checked)} />
                        <label className="text-xs text-zinc-400">Vollbild</label>
                      </div>
                    </div>
                  </TabsContent>

                  {/* Sharing Tab */}
                  <TabsContent value="sharing" className="space-y-3 mt-3">
                    <div className="space-y-2">
                      {[
                        {k:'qr_enabled',l:'QR-Code aktiv'},
                        {k:'public_results',l:'Oeffentliche Ergebnisse'},
                        {k:'leaderboard_public',l:'Leaderboard oeffentlich'},
                      ].map(s => (
                        <div key={s.k} className="flex items-center gap-2">
                          <input type="checkbox" className="rounded border-zinc-600" data-testid={`cfg-${s.k}`}
                            checked={deviceConfig?.sharing?.[s.k] ?? true} onChange={e => updateConfigField('sharing', s.k, e.target.checked)} />
                          <label className="text-xs text-zinc-400">{s.l}</label>
                        </div>
                      ))}
                    </div>
                  </TabsContent>
                </Tabs>

                {/* Save button (always visible) */}
                <div className="flex justify-end pt-2 border-t border-zinc-800">
                  <Button size="sm" disabled={configSaving || !configDirty}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs h-7"
                    onClick={saveDeviceConfig} data-testid="cfg-save-btn">
                    {configSaving ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
                    Speichern & Push
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center py-6">
                <RefreshCw className="w-4 h-4 text-zinc-500 animate-spin mr-2" />
                <span className="text-xs text-zinc-500">Lade Konfiguration...</span>
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {device.last_error && (
        <ProductCallout
          tone="red"
          eyebrow="Last error"
          title="Zuletzt gemeldeter Runtime-Fehler"
          description={device.last_error}
          icon={XCircle}
          data-testid="device-last-error"
        />
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.85fr)]">
        <div className="space-y-6">
          <ProductDetailCard
            title="Remote-Aktionen"
            eyebrow="Control surface"
            description="Board-Steuerung und Systemeingriffe im selben Produktmuster wie der Rest des Drill-ins."
          >
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-[10px] uppercase tracking-[0.18em] text-zinc-500">Board-Kontrolle</p>
                <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4" data-testid="board-control-grid">
                  {Object.entries(ACTION_META).filter(([, m]) => m.primary).map(([key, meta]) => {
                    const Icon = meta.icon;
                    const isUnlock = key === 'unlock_board' || key === 'start_session';
                    return (
                      <button
                        key={key}
                        onClick={() => handleBoardAction(key)}
                        disabled={!!actionLoading}
                        data-testid={`action-${key}`}
                        className={`rounded-2xl border px-4 py-3 text-left transition-all disabled:cursor-not-allowed disabled:opacity-50 ${isUnlock ? 'border-emerald-500/25 bg-emerald-500/5 hover:bg-emerald-500/10' : 'border-amber-500/25 bg-amber-500/5 hover:bg-amber-500/10'}`}
                      >
                        <div className="flex items-start gap-3">
                          {actionLoading === key ? <div className="mt-0.5 h-4 w-4 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" /> : <Icon className={`mt-0.5 h-4 w-4 ${isUnlock ? 'text-emerald-400' : 'text-amber-400'}`} />}
                          <div>
                            <p className="text-sm font-medium text-white">{meta.label}</p>
                            <p className="mt-1 text-xs text-zinc-500">{meta.desc}</p>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div>
                <p className="mb-2 text-[10px] uppercase tracking-[0.18em] text-zinc-500">System</p>
                <div className="grid gap-2 md:grid-cols-3" data-testid="remote-actions-grid">
                  {Object.entries(ACTION_META).filter(([, m]) => !m.primary).map(([key, meta]) => {
                    const Icon = meta.icon;
                    return (
                      <button
                        key={key}
                        onClick={() => issueAction(key)}
                        disabled={!!actionLoading}
                        data-testid={`action-${key}`}
                        className="rounded-2xl border border-zinc-800 bg-zinc-950/30 px-4 py-3 text-left transition-all hover:border-zinc-700 hover:bg-zinc-900/50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <div className="flex items-start gap-3">
                          {actionLoading === key ? <div className="mt-0.5 h-4 w-4 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" /> : <Icon className="mt-0.5 h-4 w-4 text-zinc-400" />}
                          <div>
                            <p className="text-sm font-medium text-white">{meta.label}</p>
                            <p className="mt-1 text-xs text-zinc-500">{meta.desc}</p>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </ProductDetailCard>

          <ProductTimelinePanel
            title="Aktions-Verlauf"
            eyebrow="Execution history"
            description="Ausgabe, Latenz und Ergebnis der zuletzt angestoßenen Remote-Aktionen."
            items={device.recent_actions || []}
            empty="Keine Aktionen vorhanden"
            testId="actions-log"
            renderTitle={(a) => ACTION_META[a.action_type]?.label || a.action_type}
            renderMeta={(a) => {
              const badge = STATUS_BADGE[a.status] || STATUS_BADGE.pending;
              return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium ${badge.cls}`}>{badge.label}</span>;
            }}
            renderBody={(a) => {
              const duration = a.acked_at && a.issued_at ? `${Math.round((new Date(a.acked_at) - new Date(a.issued_at)) / 1000)}s` : null;
              return (
                <div className="space-y-1">
                  <p className="text-zinc-500">{a.result_message || ACTION_META[a.action_type]?.desc || 'Ohne Rückmeldung.'}</p>
                  <p className="font-mono text-[11px] text-zinc-600">{a.issued_by || 'system'} · {a.issued_at ? timeAgo(a.issued_at) : 'ohne Zeit'}{duration ? ` · ${duration}` : ''}</p>
                </div>
              );
            }}
          />

          <ProductLogPanel logs={device.device_logs || []} logFilter={logFilter} onChangeFilter={setLogFilter} levelClasses={LOG_LEVEL_CLS} />
        </div>

        <div className="space-y-6">
          <ProductOpsRail
            title="Config-Sync"
            eyebrow="Operational rail"
            description="Version, Fehlerkette und letzte Abholung der zentralen Konfiguration."
            rows={syncRows}
            testId="config-sync-card"
          />

          <ProductOpsRail
            title="Action-Poller"
            eyebrow="Operational rail"
            description="Zustand des Pollers, der Remote-Aktionen bestätigt und ausführt."
            rows={actionPollerRows}
            testId="action-poller-card"
          />

          <ProductOpsRail
            title="Queue & WS"
            eyebrow="Transport layer"
            description="Offline-Queue und Websocket-Push im selben Runtime-Block statt verstreuter Statuskarten."
            rows={[...queueRows, ...wsRows]}
            testId="transport-rail-card"
          />

          <ProductTimelinePanel
            title="Letzte 7 Tage"
            eyebrow="Commercial pulse"
            description="Kompakter Verlauf von Umsatz, Sessions und Games pro Tag."
            items={device.daily_stats || []}
            empty="Keine Daten"
            testId="daily-stats"
            renderTitle={(s) => s.date}
            renderMeta={(s) => <span className="text-sm font-medium text-emerald-300">{((s.revenue_cents || 0) / 100).toFixed(2)} EUR</span>}
            renderBody={(s) => <p className="font-mono text-[11px] text-zinc-600">{s.sessions} Sessions · {s.games} Games</p>}
          />

          <ProductTimelinePanel
            title="Letzte Events"
            eyebrow="Runtime stream"
            description="Event-Typen aus der jüngsten Telemetrie in derselben Timeline-Semantik wie Logs und Aktionen."
            items={device.recent_events || []}
            empty="Keine Events"
            testId="recent-events"
            renderTitle={(e) => e.event_type || 'Event'}
            renderMeta={(e) => <span className="text-[11px] text-zinc-500">{e.timestamp ? timeAgo(e.timestamp) : '—'}</span>}
            renderBody={(e) => e.message ? <p>{e.message}</p> : null}
          />
        </div>
      </div>
    </div>
  </div>

      {/* Unlock Board Dialog */}
      <Dialog open={unlockOpen} onOpenChange={setUnlockOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-700 text-white max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold flex items-center gap-2">
              <Unlock className="w-5 h-5 text-emerald-400" /> Board Freischalten
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Board ID (optional) */}
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Board-ID (leer = automatisch)</label>
              <input className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-white" data-testid="unlock-board-id"
                placeholder="z.B. BOARD-1" value={unlockParams.board_id} onChange={e => setUnlockParams(p => ({ ...p, board_id: e.target.value }))} />
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 px-3 py-3 text-xs leading-5 text-zinc-400">
              Remote-Freischaltung folgt ebenfalls dem credits-only Flow: Credits laden, Board öffnen, echte Abbuchung erst beim autoritativen Matchstart.
            </div>
            {/* Game Type */}
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Spielart</label>
              <select className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-white" data-testid="unlock-game-type"
                value={unlockParams.game_type} onChange={e => setUnlockParams(p => ({ ...p, game_type: e.target.value }))}>
                <option value="301">301</option>
                <option value="501">501</option>
                <option value="Cricket">Cricket</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Credits</label>
                <input type="number" min="1" className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-white" data-testid="unlock-credits"
                  value={unlockParams.credits} onChange={e => setUnlockParams(p => ({ ...p, credits: parseInt(e.target.value) || 1 }))} />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Verkaufsbetrag (EUR)</label>
                <input type="number" step="0.5" min="0" className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-white" data-testid="unlock-price"
                  value={unlockParams.price_total} onChange={e => setUnlockParams(p => ({ ...p, price_total: parseFloat(e.target.value) || 0 }))} />
              </div>
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" className="border-zinc-700 text-zinc-400" onClick={() => setUnlockOpen(false)} data-testid="unlock-cancel-btn">Abbrechen</Button>
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={confirmUnlock} disabled={!!actionLoading} data-testid="unlock-confirm-btn">
              {actionLoading === 'unlock_board' ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Unlock className="w-4 h-4 mr-1" />}
              Freischalten
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

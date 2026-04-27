import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useCentralAuth } from '../../context/CentralAuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import {
  KeyRound, Copy, RefreshCw, ArrowLeft, Monitor, Wifi, WifiOff,
  Ban, CheckCircle, AlertTriangle, Archive, Unlink, Shield, Clock, Users,
  Sparkles, Gauge, ExternalLink, TriangleAlert
} from 'lucide-react';

const STATUS_CONF = {
  active: { cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', label: 'Aktiv', icon: CheckCircle },
  grace: { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20', label: 'Toleranz', icon: Clock },
  expired: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', label: 'Abgelaufen', icon: AlertTriangle },
  blocked: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', label: 'Gesperrt', icon: Ban },
  test: { cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20', label: 'Test', icon: Shield },
  deactivated: { cls: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20', label: 'Deaktiviert', icon: Ban },
  archived: { cls: 'bg-zinc-600/10 text-zinc-500 border-zinc-600/20', label: 'Archiviert', icon: Archive },
};

function StatusBadge({ status }) {
  const c = STATUS_CONF[status] || STATUS_CONF.active;
  const Icon = c.icon;
  return (
    <span data-testid="license-status-badge" className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${c.cls}`}>
      <Icon className="w-3 h-3" /> {c.label}
    </span>
  );
}

function InfoRow({ label, value, tid }) {
  return (
    <div className="flex justify-between py-2 border-b border-zinc-800/50">
      <span className="text-zinc-500 text-sm">{label}</span>
      <span data-testid={tid} className="text-zinc-200 text-sm font-medium">{value || '—'}</span>
    </div>
  );
}

function bucketLabel(value) {
  return {
    healthy: 'Gesund',
    watch: 'Beobachten',
    attention: 'Aktion nötig',
    urgent: 'Dringend',
  }[value] || value || '—';
}

function capacityLabel(value) {
  return {
    unconfigured: 'Kein Limit',
    unassigned: 'Noch ungenutzt',
    available: 'Platz vorhanden',
    near_capacity: 'Fast voll',
    full: 'Voll belegt',
    over_capacity: 'Überbucht',
  }[value] || value || '—';
}

function postureLabel(value) {
  return {
    ready: 'Ready',
    degraded: 'Degraded',
    review_required: 'Review',
    blocked: 'Blocked',
  }[value] || value || '—';
}

function tokenStateLabel(value) {
  return {
    active: 'Token bereit',
    consumed: 'Token verbraucht',
    expired: 'Token abgelaufen',
    revoked: 'Token widerrufen',
    missing: 'Kein Token',
  }[value] || value || '—';
}

function ReadinessBadge({ readiness }) {
  const tones = {
    healthy: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
    watch: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
    attention: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
    urgent: 'border-red-500/20 bg-red-500/10 text-red-300',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${tones[readiness?.action_bucket] || tones.watch}`}>
      <Sparkles className="w-3 h-3" /> {bucketLabel(readiness?.action_bucket)}
    </span>
  );
}

function ReadinessCard({ icon: Icon, label, value, hint, tone = 'zinc', tid }) {
  const tones = {
    emerald: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
    amber: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
    red: 'border-red-500/20 bg-red-500/10 text-red-300',
    blue: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
    zinc: 'border-zinc-800 bg-zinc-900/60 text-zinc-300',
  };
  return (
    <div data-testid={tid} className={`rounded-2xl border p-4 ${tones[tone] || tones.zinc}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-current/70">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
          {hint && <p className="mt-1 text-xs text-current/75">{hint}</p>}
        </div>
        <div className="rounded-xl bg-black/20 p-2.5">
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

function TokenSection({ token, rawToken, onRegenerate, loading, tokenHistory, deviceCount }) {
  const [revealed, setRevealed] = useState(false);
  const displayToken = rawToken || (token ? token.token_preview : null);
  const hasHistory = tokenHistory && tokenHistory.length > 0;
  const allUsed = hasHistory && tokenHistory.every(t => t.used_at || t.is_revoked);

  const copyToken = () => {
    if (rawToken) {
      navigator.clipboard.writeText(rawToken);
      toast.success('Token kopiert');
    } else {
      toast.error('Token nicht verfügbar — bitte neu generieren');
    }
  };

  // State 1: No token ever created
  if (!token && !rawToken && !hasHistory) {
    return (
      <div data-testid="token-empty-state" className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-5">
        <div className="flex items-center gap-3 mb-3">
          <KeyRound className="w-5 h-5 text-zinc-500" />
          <h3 className="text-zinc-300 font-medium">Aktivierungstoken</h3>
        </div>
        <p className="text-zinc-500 text-sm mb-4">Noch kein Token erstellt. Erstellen Sie einen Token, um ein Gerät mit dieser Lizenz zu verbinden.</p>
        <Button data-testid="create-token-btn" onClick={onRegenerate} disabled={loading} size="sm" className="bg-emerald-600 hover:bg-emerald-700">
          <KeyRound className="w-4 h-4 mr-2" /> Token erstellen
        </Button>
      </div>
    );
  }

  // State 2: All tokens used/revoked, no active token (device already registered)
  if (!token && !rawToken && allUsed) {
    const lastUsed = tokenHistory.find(t => t.used_at);
    return (
      <div data-testid="token-used-state" className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-emerald-400" />
            <h3 className="text-zinc-300 font-medium">Aktivierung abgeschlossen</h3>
          </div>
          <Button data-testid="regenerate-token-btn" variant="outline" size="sm" onClick={onRegenerate} disabled={loading}
            className="border-zinc-700 hover:border-zinc-600 text-zinc-400 hover:text-zinc-200">
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Neuen Token erstellen
          </Button>
        </div>
        <p className="text-zinc-400 text-sm">
          {deviceCount > 0
            ? `${deviceCount} Gerät(e) erfolgreich verbunden. Der Token wurde bei der Registrierung verwendet.`
            : 'Token wurde verwendet. Erstellen Sie bei Bedarf einen neuen Token.'}
        </p>
        {lastUsed && (
          <p className="text-zinc-600 text-xs mt-2">
            Verwendet am: {new Date(lastUsed.used_at).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
            {lastUsed.created_by && ` — Erstellt von: ${lastUsed.created_by}`}
          </p>
        )}
      </div>
    );
  }

  // State 3: Active token exists
  return (
    <div data-testid="token-section" className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <KeyRound className="w-5 h-5 text-emerald-400" />
          <h3 className="text-zinc-300 font-medium">Aktivierungstoken</h3>
        </div>
        <Button data-testid="regenerate-token-btn" variant="outline" size="sm" onClick={onRegenerate} disabled={loading}
          className="border-zinc-700 hover:border-zinc-600 text-zinc-400 hover:text-zinc-200">
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Neu generieren
        </Button>
      </div>

      <div className="bg-zinc-950 border border-zinc-800 rounded-md p-3 flex items-center justify-between mb-3">
        <code data-testid="token-display" className="text-sm font-mono text-emerald-400 select-all">
          {revealed && rawToken ? rawToken : (displayToken || '••••••••••••')}
        </code>
        <div className="flex items-center gap-2">
          {rawToken && (
            <button data-testid="reveal-token-btn" onClick={() => setRevealed(!revealed)} className="text-zinc-500 hover:text-zinc-300 text-xs">
              {revealed ? 'Verbergen' : 'Anzeigen'}
            </button>
          )}
          <button data-testid="copy-token-btn" onClick={copyToken} className="text-zinc-500 hover:text-zinc-300">
            <Copy className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="bg-zinc-900/80 border border-dashed border-zinc-700 rounded-md p-3">
        <p className="text-zinc-400 text-xs leading-relaxed">
          <strong className="text-zinc-300">Nächster Schritt:</strong> Geben Sie diesen Token am Gerät ein, um es mit dieser Lizenz zu verbinden.
          Starten Sie das Kiosk-System und verwenden Sie den Token bei der Ersteinrichtung.
        </p>
      </div>

      {token && (
        <div className="mt-3 flex gap-4 text-xs text-zinc-600">
          <span>Erstellt: {token.created_at ? new Date(token.created_at).toLocaleDateString('de-DE') : '—'}</span>
          <span>Gültig bis: {token.expires_at ? new Date(token.expires_at).toLocaleDateString('de-DE') : 'Unbegrenzt'}</span>
          <span>Von: {token.created_by || '—'}</span>
        </div>
      )}
    </div>
  );
}

function DevicesSection({ devices, maxDevices, onUnbind, onOpenDevice, licenseStatus }) {
  if (!devices || devices.length === 0) {
    return (
      <div data-testid="devices-empty-state" className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-5">
        <div className="flex items-center gap-3 mb-3">
          <Monitor className="w-5 h-5 text-zinc-500" />
          <h3 className="text-zinc-300 font-medium">Gebundene Geräte <span className="text-zinc-600 text-sm">0/{maxDevices}</span></h3>
        </div>
        <p className="text-zinc-500 text-sm">Noch keine Geräte verbunden. Verwenden Sie den Aktivierungstoken oben, um ein Gerät zu registrieren.</p>
      </div>
    );
  }

  return (
    <div data-testid="devices-section" className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-5">
      <div className="flex items-center gap-3 mb-4">
        <Monitor className="w-5 h-5 text-emerald-400" />
        <h3 className="text-zinc-300 font-medium">Gebundene Geräte <span className="text-zinc-600 text-sm">{devices.length}/{maxDevices}</span></h3>
      </div>
      <div className="space-y-2">
        {devices.map(dev => {
          // v3.15.2: Use backend-provided connectivity status (single rule)
          const connectivity = dev.connectivity || (dev.is_online ? 'online' : (dev.last_heartbeat_at && (Date.now() - new Date(dev.last_heartbeat_at).getTime() < 300000) ? 'online' : 'offline'));
          const online = connectivity === 'online';
          const degraded = connectivity === 'degraded';
          return (
            <div key={dev.id} data-testid={`device-row-${dev.id}`} className="flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded-md p-3">
              <div className="flex items-center gap-3">
                {online
                  ? <Wifi className="w-4 h-4 text-emerald-400" />
                  : degraded
                    ? <Wifi className="w-4 h-4 text-amber-400" />
                    : <WifiOff className="w-4 h-4 text-zinc-600" />}
                <div>
                  <button onClick={() => onOpenDevice?.(dev.id)} className="text-zinc-200 text-sm font-medium hover:text-white hover:underline">{dev.device_name}</button>
                  <span className="text-zinc-600 text-xs ml-2">{dev.id.slice(0, 8)}...</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs ${online ? 'text-emerald-500' : degraded ? 'text-amber-400' : 'text-zinc-600'}`}>
                  {online ? 'Online' : degraded ? 'Instabil' : (dev.last_heartbeat_at ? `Zuletzt: ${new Date(dev.last_heartbeat_at).toLocaleDateString('de-DE')}` : 'Noch kein Heartbeat')}
                  {dev.ws_connected && ' (WS)'}
                </span>
                {licenseStatus !== 'archived' && (
                  <button data-testid={`unbind-device-${dev.id}`} onClick={() => onUnbind(dev.id, dev.device_name)}
                    className="text-zinc-600 hover:text-red-400 transition-colors" title="Gerät entkoppeln">
                    <Unlink className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function PortalLicenseDetail() {
  const { licenseId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { apiBase, authHeaders, canManage, canReviewRemoteActions } = useCentralAuth();
  const [lic, setLic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [rawToken, setRawToken] = useState(location.state?.rawToken || null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionFeedback, setActionFeedback] = useState(location.state?.actionFeedback || null);
  const intent = searchParams.get('intent') || '';
  const surfacePrefix = location.pathname.startsWith('/operator') ? '/operator' : '/portal';

  const classifyError = (err) => {
    const status = err?.response?.status;
    const isTimeout = err?.code === 'ECONNABORTED' || err?.message?.includes('timeout');
    const isNetwork = !err?.response && (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error');
    if (status === 404) return { type: 'not_found', message: 'Lizenz existiert nicht in der Datenbank.', retryable: false };
    if (status === 401) return { type: 'auth', message: 'Sitzung abgelaufen. Bitte erneut einloggen.', retryable: false };
    if (status === 403) return { type: 'forbidden', message: 'Keine Berechtigung fuer diese Lizenz.', retryable: false };
    if (status === 502) return { type: 'server_down', message: 'Zentraler Server nicht erreichbar (502).', retryable: true };
    if (status === 504) return { type: 'server_timeout', message: 'Zentraler Server antwortet nicht (504 Timeout).', retryable: true };
    if (isTimeout) return { type: 'timeout', message: 'Verbindung zu langsam oder fehlgeschlagen.', retryable: true };
    if (isNetwork) return { type: 'network', message: 'Netzwerkfehler — keine Verbindung zum Server.', retryable: true };
    return { type: 'unknown', message: err?.response?.data?.detail || `Unbekannter Fehler (HTTP ${status || '?'}).`, retryable: true };
  };

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await axios.get(`${apiBase}/licensing/licenses/${licenseId}`, { headers: authHeaders, timeout: 15000 });
      setLic(res.data);
      setFetchError(null);
    } catch (err) {
      const classified = classifyError(err);
      setFetchError(classified);
      setLic(null);
      console.error(`[LicenseDetail] Fetch failed: type=${classified.type}`, err);
    } finally {
      setLoading(false);
    }
  }, [apiBase, authHeaders, licenseId]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  const handleRegenerate = async () => {
    setActionLoading(true);
    try {
      const res = await axios.post(`${apiBase}/licensing/licenses/${licenseId}/regenerate-token`, {}, { headers: authHeaders });
      setRawToken(res.data.raw_token);
      setActionFeedback({
        tone: 'success',
        title: 'Frischer Token erstellt',
        message: res.data.revoked_count > 0
          ? `${res.data.revoked_count} alte(r) Token widerrufen. Nur noch den neuen Token am Gerät verwenden.`
          : 'Nur noch den neuen Token am Gerät verwenden.',
      });
      toast.success(res.data.revoked_count > 0 ? `Neuer Token erstellt (${res.data.revoked_count} alte widerrufen)` : 'Token erstellt');
      fetchDetail();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    } finally {
      setActionLoading(false);
    }
  };

  const handleGetToken = async () => {
    setActionLoading(true);
    try {
      const res = await axios.get(`${apiBase}/licensing/licenses/${licenseId}/token`, { headers: authHeaders });
      if (res.data.raw_token) setRawToken(res.data.raw_token);
      setActionFeedback({
        tone: 'success',
        title: res.data.exists ? 'Aktiver Token bereit' : 'Token erstellt',
        message: res.data.exists
          ? 'Den bestehenden Token jetzt am Gerät verwenden oder bei Unsicherheit direkt neu ausstellen.'
          : 'Nächster Schritt: Token am Gerät eingeben und die Registrierung abschließen.',
      });
      if (!res.data.exists) toast.success('Token erstellt');
      fetchDetail();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    } finally {
      setActionLoading(false);
    }
  };

  const handleUnbind = async (deviceId, deviceName) => {
    if (!window.confirm(`Gerät "${deviceName}" wirklich entkoppeln?`)) return;
    try {
      await axios.post(`${apiBase}/licensing/licenses/${licenseId}/unbind-device/${deviceId}`, {}, { headers: authHeaders });
      toast.success(`${deviceName} entkoppelt`);
      fetchDetail();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    }
  };

  const runSuggestedAction = async (action) => {
    if (!action) return;
    const execution = action.execution || {};

    if (execution.mode === 'direct' && execution.action === 'ensure_activation_token' && canReviewRemoteActions) {
      setActionLoading(true);
      try {
        const res = await axios.get(`${apiBase}/licensing/licenses/${licenseId}/token`, { headers: authHeaders });
        const nextRawToken = res.data.raw_token || null;
        if (nextRawToken) setRawToken(nextRawToken);
        setActionFeedback({
          tone: 'success',
          title: res.data.exists ? 'Aktiver Token bereit' : 'Token erstellt',
          message: res.data.exists
            ? 'Den bestehenden Token jetzt am Gerät verwenden oder bei Unsicherheit direkt neu ausstellen.'
            : 'Nächster Schritt: Token am Gerät eingeben und die Registrierung abschließen.',
        });
        toast.success(res.data.exists ? 'Aktiver Token bereit' : 'Token erstellt');
        await fetchDetail();
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Fehler');
      } finally {
        setActionLoading(false);
      }
      return;
    }

    if (execution.mode === 'direct' && execution.action === 'regenerate_activation_token' && canReviewRemoteActions) {
      await handleRegenerate();
      return;
    }

    if (execution.mode === 'direct' && execution.action === 'reactivate_license' && canManage && st === 'deactivated') {
      await handleStatusChange('activate');
      return;
    }

    if (execution.target === 'remote_actions' && isOperatorSurface) {
      navigate(remoteActionsPath);
      return;
    }

    navigate(`${location.pathname}?intent=${encodeURIComponent(action.intent || '')}`);
  };

  const handleStatusChange = async (action) => {
    const labels = { deactivate: 'deaktivieren', archive: 'archivieren', activate: 'reaktivieren' };
    if (!window.confirm(`Lizenz wirklich ${labels[action]}?`)) return;
    setActionLoading(true);
    try {
      if (action === 'activate') {
        await axios.put(`${apiBase}/licensing/licenses/${licenseId}`, { status: 'active' }, { headers: authHeaders });
        setActionFeedback({
          tone: 'success',
          title: 'Lizenz wieder aktiv',
          message: 'Wenn der Standort noch kein Gerät hat, direkt den Aktivierungstoken prüfen oder neu ausstellen.',
        });
      } else {
        await axios.delete(`${apiBase}/licensing/licenses/${licenseId}?action=${action}`, { headers: authHeaders });
      }
      toast.success(`Lizenz ${labels[action]}t`);
      fetchDetail();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64" data-testid="license-detail-loading"><div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" /></div>;

  if (fetchError) {
    return (
      <div className="text-center py-16 space-y-4" data-testid={`license-error-${fetchError.type}`}>
        <p className="text-lg font-semibold text-white">
          {fetchError.type === 'not_found' ? 'Lizenz existiert nicht' :
           fetchError.type === 'auth' ? 'Authentifizierung fehlgeschlagen' :
           fetchError.type === 'forbidden' ? 'Zugriff verweigert' :
           fetchError.type === 'server_down' || fetchError.type === 'server_timeout' ? 'Server nicht erreichbar' :
           'Fehler beim Laden'}
        </p>
        <p className="text-sm text-zinc-400">{fetchError.message}</p>
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => navigate('/portal/licenses')} className="px-4 py-2 border border-zinc-700 text-zinc-400 rounded-lg text-sm" data-testid="license-error-back">Zurueck</button>
          {fetchError.retryable && <button onClick={fetchDetail} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm" data-testid="license-error-retry">Erneut versuchen</button>}
        </div>
      </div>
    );
  }

  if (!lic) return null;

  const st = lic.computed_status || lic.status;
  const isOperational = ['active', 'test', 'grace'].includes(st);
  const readiness = lic.commercial_readiness || {};
  const isOperatorSurface = location.pathname.startsWith('/operator');
  const listPath = isOperatorSurface ? '/operator/licenses' : '/portal/licenses';
  const remoteActionsPath = `/operator/remote-actions?license_id=${encodeURIComponent(licenseId)}`;
  const suggestedActions = readiness.suggested_actions || [];
  const primaryAction = suggestedActions[0];
  const pressureTone = readiness.action_bucket === 'urgent'
    ? 'red'
    : readiness.action_bucket === 'attention'
      ? 'amber'
      : readiness.action_bucket === 'watch'
        ? 'blue'
        : 'emerald';

  return (
    <div data-testid="license-detail-page" className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <button data-testid="back-btn" onClick={() => navigate(listPath)} className="text-zinc-500 hover:text-zinc-300">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-semibold text-zinc-100">Lizenz: {lic.plan_type}</h1>
            <p className="text-zinc-500 text-sm mt-0.5">{lic.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <ReadinessBadge readiness={readiness} />
          <StatusBadge status={st} />
        </div>
      </div>

      <section className="rounded-3xl border border-zinc-800 bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 p-5" data-testid="license-readiness-hero">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs text-indigo-300">
              <Sparkles className="w-3.5 h-3.5" /> Commercial Readiness Drill-in
            </div>
            <h2 className="mt-3 text-lg font-semibold text-white">{readiness.primary_message || 'Lizenzlage wird ausgewertet'}</h2>
            <p className="mt-1 text-sm text-zinc-400 max-w-2xl">{readiness.recommended_action || 'Kein direkter Eingriff nötig.'}</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {primaryAction?.execution?.mode === 'direct' && (
              <Button size="sm" onClick={() => runSuggestedAction(primaryAction)} disabled={actionLoading} className="bg-emerald-600 hover:bg-emerald-700">
                {primaryAction.type === 'reactivate_license' ? 'Jetzt reaktivieren' : 'Direkt ausführen'}
              </Button>
            )}
            {suggestedActions.some((item) => item.type === 'review_bound_devices') && isOperatorSurface && (
              <Button variant="outline" size="sm" onClick={() => navigate(remoteActionsPath)} className="border-indigo-500/20 text-indigo-300 hover:bg-indigo-500/10">
                Geräte prüfen <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
              </Button>
            )}
            {isOperatorSurface && (
              <Button variant="outline" size="sm" onClick={() => navigate(remoteActionsPath)} className="border-indigo-500/20 text-indigo-300 hover:bg-indigo-500/10">
                Remote Actions <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => navigate(listPath)} className="border-zinc-700 text-zinc-300 hover:bg-zinc-800">
              Portfolio
            </Button>
          </div>
        </div>

        {actionFeedback && (
          <div className={`mt-4 rounded-2xl border px-4 py-3 ${actionFeedback.tone === 'success' ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-200' : 'border-zinc-700 bg-zinc-900/70 text-zinc-200'}`} data-testid="license-action-feedback">
            <p className="text-sm font-medium">{actionFeedback.title}</p>
            {actionFeedback.message && <p className="mt-1 text-xs text-current/80">{actionFeedback.message}</p>}
          </div>
        )}

        <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          <ReadinessCard icon={TriangleAlert} label="Bucket" value={bucketLabel(readiness.action_bucket)} hint={readiness.risk_flags?.join(' · ') || 'Keine Flags'} tone={pressureTone} tid="license-readiness-bucket" />
          <ReadinessCard icon={Clock} label="Renewal" value={readiness.renewal_days != null ? `${readiness.renewal_days} Tage` : 'Unbegrenzt'} hint={st === 'grace' ? 'Aktuell in Grace' : 'Vertragslaufzeit'} tone={readiness.renewal_days != null && readiness.renewal_days <= 14 ? 'amber' : 'zinc'} tid="license-readiness-renewal" />
          <ReadinessCard icon={Gauge} label="Kapazität" value={`${lic.device_count ?? 0}/${lic.max_devices ?? '—'}`} hint={capacityLabel(readiness.capacity_state)} tone={['full', 'over_capacity'].includes(readiness.capacity_state) ? 'amber' : readiness.capacity_state === 'near_capacity' ? 'blue' : 'zinc'} tid="license-readiness-capacity" />
          <ReadinessCard icon={KeyRound} label="Tokenlage" value={tokenStateLabel(readiness.token_state)} hint={readiness.token_summary?.message || 'Kein Tokenstatus'} tone={readiness.token_state === 'active' ? 'blue' : ['expired', 'revoked'].includes(readiness.token_state) ? 'amber' : 'zinc'} tid="license-readiness-token" />
          <ReadinessCard icon={Shield} label="Posture" value={postureLabel(readiness.posture_status)} hint={`${readiness.posture_counts?.blocked || 0} blocked · ${readiness.posture_counts?.review_required || 0} review · ${readiness.posture_counts?.degraded || 0} degraded`} tone={readiness.posture_status === 'blocked' ? 'red' : readiness.posture_status === 'review_required' ? 'amber' : readiness.posture_status === 'degraded' ? 'blue' : 'emerald'} tid="license-readiness-posture" />
        </div>

        {suggestedActions.length > 0 && (
          <div className="mt-4 rounded-2xl border border-zinc-800 bg-black/20 p-4" data-testid="license-suggested-actions">
            <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Empfohlene nächste Schritte</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {suggestedActions.map((action) => (
                <button
                  key={action.type}
                  onClick={() => runSuggestedAction(action)}
                  disabled={actionLoading || (action.execution?.mode === 'direct' && action.type === 'reactivate_license' && !canManage) || (action.execution?.mode === 'direct' && ['generate_activation_token', 'get_activation_token', 'regenerate_activation_token'].includes(action.type) && !canReviewRemoteActions)}
                  className={`rounded-full border px-3 py-1 text-xs transition-colors ${action.intent === intent ? 'border-white/30 bg-white/10 text-white' : 'border-zinc-700 text-zinc-300 hover:border-zinc-500 hover:text-white'} disabled:cursor-not-allowed disabled:opacity-50`}
                  title={action.reason}
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Stammdaten */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-5">
        <h3 className="text-zinc-300 font-medium mb-3 flex items-center gap-2"><Shield className="w-4 h-4 text-zinc-500" /> Stammdaten</h3>
        <InfoRow label="Kunde" value={lic.customer_name} tid="lic-customer" />
        <InfoRow label="Standort" value={lic.location_name} tid="lic-location" />
        <InfoRow label="Plan" value={lic.plan_type} tid="lic-plan" />
        <InfoRow label="Max. Geräte" value={lic.max_devices} tid="lic-max-devices" />
        <InfoRow label="Gültig ab" value={lic.starts_at ? new Date(lic.starts_at).toLocaleDateString('de-DE') : 'Sofort'} tid="lic-starts" />
        <InfoRow label="Gültig bis" value={lic.ends_at ? new Date(lic.ends_at).toLocaleDateString('de-DE') : 'Unbegrenzt'} tid="lic-ends" />
        <InfoRow label="Erstellt am" value={lic.created_at ? new Date(lic.created_at).toLocaleDateString('de-DE') : '—'} tid="lic-created" />
        <InfoRow label="Erstellt von" value={lic.created_by} tid="lic-created-by" />
        {lic.notes && <InfoRow label="Notizen" value={lic.notes} tid="lic-notes" />}
      </div>

      {/* Token */}
      {isOperational && (
        <TokenSection
          token={lic.active_token}
          rawToken={rawToken}
          onRegenerate={lic.active_token ? handleRegenerate : handleGetToken}
          loading={actionLoading}
          tokenHistory={lic.token_history}
          deviceCount={lic.device_count}
        />
      )}

      {/* Devices */}
      <DevicesSection
        devices={lic.devices}
        maxDevices={lic.max_devices}
        onUnbind={handleUnbind}
        onOpenDevice={(deviceId) => navigate(`${surfacePrefix}/devices/${deviceId}`)}
        licenseStatus={st}
      />

      {/* Actions */}
      {canManage && (
        <div data-testid="license-actions" className="flex flex-wrap gap-3 pt-2">
          {st === 'deactivated' && (
            <Button data-testid="activate-btn" onClick={() => handleStatusChange('activate')} disabled={actionLoading}
              size="sm" className="bg-emerald-600 hover:bg-emerald-700">
              <CheckCircle className="w-4 h-4 mr-2" /> Reaktivieren
            </Button>
          )}
          {isOperational && (
            <Button data-testid="deactivate-btn" onClick={() => handleStatusChange('deactivate')} disabled={actionLoading}
              size="sm" variant="outline" className="border-amber-700 text-amber-400 hover:bg-amber-900/30">
              <Ban className="w-4 h-4 mr-2" /> Deaktivieren
            </Button>
          )}
          {(st !== 'archived') && (
            <Button data-testid="archive-btn" onClick={() => handleStatusChange('archive')} disabled={actionLoading}
              size="sm" variant="outline" className="border-zinc-700 text-zinc-400 hover:bg-zinc-800">
              <Archive className="w-4 h-4 mr-2" /> Archivieren
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

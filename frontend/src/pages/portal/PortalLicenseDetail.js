import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useCentralAuth } from '../../context/CentralAuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import {
  KeyRound, Copy, RefreshCw, ArrowLeft, Monitor, Wifi, WifiOff,
  Ban, CheckCircle, AlertTriangle, Archive, Unlink, Shield, Clock, Users
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
          {revealed && rawToken ? rawToken : (displayToken ? `${displayToken}...` : '••••••••••••')}
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

function DevicesSection({ devices, maxDevices, onUnbind, licenseStatus }) {
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
          const online = dev.last_heartbeat_at && (Date.now() - new Date(dev.last_heartbeat_at).getTime() < 300000);
          return (
            <div key={dev.id} data-testid={`device-row-${dev.id}`} className="flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded-md p-3">
              <div className="flex items-center gap-3">
                {online
                  ? <Wifi className="w-4 h-4 text-emerald-400" />
                  : <WifiOff className="w-4 h-4 text-zinc-600" />}
                <div>
                  <span className="text-zinc-200 text-sm font-medium">{dev.device_name}</span>
                  <span className="text-zinc-600 text-xs ml-2">{dev.id.slice(0, 8)}...</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs ${online ? 'text-emerald-500' : 'text-zinc-600'}`}>
                  {online ? 'Online' : (dev.last_heartbeat_at ? `Zuletzt: ${new Date(dev.last_heartbeat_at).toLocaleDateString('de-DE')}` : 'Noch kein Heartbeat')}
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
  const { apiBase, authHeaders, canManage } = useCentralAuth();
  const [lic, setLic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rawToken, setRawToken] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchDetail = useCallback(async () => {
    try {
      const res = await axios.get(`${apiBase}/licensing/licenses/${licenseId}`, { headers: authHeaders });
      setLic(res.data);
    } catch (err) {
      toast.error('Lizenz nicht gefunden');
      navigate('/portal/licenses');
    } finally {
      setLoading(false);
    }
  }, [apiBase, authHeaders, licenseId, navigate]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  const handleRegenerate = async () => {
    setActionLoading(true);
    try {
      const res = await axios.post(`${apiBase}/licensing/licenses/${licenseId}/regenerate-token`, {}, { headers: authHeaders });
      setRawToken(res.data.raw_token);
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

  const handleStatusChange = async (action) => {
    const labels = { deactivate: 'deaktivieren', archive: 'archivieren', activate: 'reaktivieren' };
    if (!window.confirm(`Lizenz wirklich ${labels[action]}?`)) return;
    setActionLoading(true);
    try {
      if (action === 'activate') {
        await axios.put(`${apiBase}/licensing/licenses/${licenseId}`, { status: 'active' }, { headers: authHeaders });
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

  if (loading) return <div className="p-8 text-zinc-500">Laden...</div>;
  if (!lic) return null;

  const st = lic.computed_status || lic.status;
  const isOperational = ['active', 'test', 'grace'].includes(st);

  return (
    <div data-testid="license-detail-page" className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button data-testid="back-btn" onClick={() => navigate('/portal/licenses')} className="text-zinc-500 hover:text-zinc-300">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-semibold text-zinc-100">Lizenz: {lic.plan_type}</h1>
            <p className="text-zinc-500 text-sm mt-0.5">{lic.id}</p>
          </div>
        </div>
        <StatusBadge status={st} />
      </div>

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

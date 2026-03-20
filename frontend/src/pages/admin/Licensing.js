/**
 * Local Admin — Licensing (Read-Only Status View)
 * v3.6.0: All license management moved to Central Server / Operator Portal.
 * This page only shows device registration status, license state, and sync info.
 */
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  KeyRound, Shield, Monitor, RefreshCw, Wifi, WifiOff,
  CheckCircle, Clock, XCircle, AlertTriangle, Server, ExternalLink
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { useI18n } from '../../context/I18nContext';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  active:     { icon: CheckCircle, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20', label: 'Aktiv' },
  grace:      { icon: Clock,       color: 'text-amber-400 bg-amber-500/10 border-amber-500/20', label: 'Toleranzzeitraum' },
  expired:    { icon: XCircle,     color: 'text-red-400 bg-red-500/10 border-red-500/20', label: 'Abgelaufen' },
  blocked:    { icon: XCircle,     color: 'text-red-400 bg-red-500/10 border-red-500/20', label: 'Gesperrt' },
  test:       { icon: Shield,      color: 'text-blue-400 bg-blue-500/10 border-blue-500/20', label: 'Test-Lizenz' },
  no_license: { icon: AlertTriangle, color: 'text-zinc-500 bg-zinc-500/10 border-zinc-500/20', label: 'Keine Lizenz' },
};

export default function AdminLicensing() {
  const { t } = useI18n();
  const [regStatus, setRegStatus] = useState(null);
  const [licStatus, setLicStatus] = useState(null);
  const [syncConfig, setSyncConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [regRes, licRes, syncRes] = await Promise.all([
        axios.get(`${API}/licensing/registration-status`).catch(() => null),
        axios.get(`${API}/licensing/status`).catch(() => null),
        axios.get(`${API}/licensing/sync-config`).catch(() => null),
      ]);
      if (regRes) setRegStatus(regRes.data);
      if (licRes) setLicStatus(licRes.data);
      if (syncRes) setSyncConfig(syncRes.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleForceSync = async () => {
    setSyncing(true);
    try {
      await axios.post(`${API}/licensing/force-sync`);
      toast.success('Sync erfolgreich');
      await fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Sync fehlgeschlagen');
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const isRegistered = regStatus?.status === 'registered';
  const licStat = licStatus?.license_status || 'no_license';
  const statusConf = STATUS_CONFIG[licStat] || STATUS_CONFIG.no_license;
  const StatusIcon = statusConf.icon;

  return (
    <div className="space-y-6" data-testid="admin-licensing-readonly">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-amber-400" /> Lizenz & Registrierung
          </h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Read-Only — Verwaltung erfolgt im zentralen Portal
          </p>
        </div>
        <Button
          onClick={handleForceSync}
          disabled={syncing || !isRegistered}
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm"
          data-testid="force-sync-btn"
        >
          <RefreshCw className={`w-4 h-4 mr-1.5 ${syncing ? 'animate-spin' : ''}`} />
          Sync erzwingen
        </Button>
      </div>

      {/* Registration Status */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <Monitor className="w-5 h-5 text-zinc-400" />
            <h2 className="text-base font-semibold text-white">Geräte-Registrierung</h2>
            <span className={`ml-auto text-xs px-2.5 py-0.5 rounded-full font-medium ${
              isRegistered ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
            }`} data-testid="reg-status-badge">
              {isRegistered ? 'Registriert' : 'Nicht registriert'}
            </span>
          </div>

          {isRegistered ? (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <InfoRow label="Install-ID" value={regStatus.install_id} mono />
              <InfoRow label="Gerätename" value={regStatus.device_name} />
              <InfoRow label="Customer" value={regStatus.customer_name} />
              <InfoRow label="API Key" value={regStatus.api_key ? `${regStatus.api_key.slice(0, 8)}...` : '—'} mono />
              <InfoRow label="Registriert am" value={regStatus.registered_at ? new Date(regStatus.registered_at).toLocaleString('de-DE') : '—'} />
            </div>
          ) : (
            <p className="text-sm text-zinc-400">
              Dieses Gerät ist noch nicht registriert. Die Registrierung erfolgt automatisch über den Kiosk-Screen.
            </p>
          )}
        </CardContent>
      </Card>

      {/* License Status */}
      <Card className={`border ${statusConf.color.split(' ').pop()}`}>
        <CardContent className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <StatusIcon className={`w-5 h-5 ${statusConf.color.split(' ')[0]}`} />
            <h2 className="text-base font-semibold text-white">Lizenzstatus</h2>
            <span className={`ml-auto text-xs px-2.5 py-0.5 rounded-full font-medium ${statusConf.color}`} data-testid="lic-status-badge">
              {statusConf.label}
            </span>
          </div>

          {licStatus ? (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <InfoRow label="Plan" value={licStatus.plan_type || '—'} />
              <InfoRow label="Kunde" value={licStatus.customer_name || '—'} />
              <InfoRow label="Ablauf" value={licStatus.expiry ? new Date(licStatus.expiry).toLocaleDateString('de-DE') : 'Unbegrenzt'} />
              <InfoRow label="Toleranz bis" value={licStatus.grace_until ? new Date(licStatus.grace_until).toLocaleDateString('de-DE') : '—'} />
              <InfoRow label="Binding-Status" value={licStatus.binding_status || '—'} />
              <InfoRow label="Max. Geräte" value={licStatus.max_devices || '—'} />
            </div>
          ) : (
            <p className="text-sm text-zinc-400">Keine Lizenzinformationen verfügbar.</p>
          )}
        </CardContent>
      </Card>

      {/* Sync Info */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <Server className="w-5 h-5 text-zinc-400" />
            <h2 className="text-base font-semibold text-white">Synchronisierung</h2>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <InfoRow label="Zentraler Server" value={syncConfig?.central_server_url || '—'} />
            <InfoRow label="Letzte Sync" value={licStatus?.server_timestamp ? new Date(licStatus.server_timestamp).toLocaleString('de-DE') : '—'} />
            <InfoRow label="Sync-Intervall" value={syncConfig?.sync_interval_minutes ? `${syncConfig.sync_interval_minutes} Min.` : '—'} />
          </div>
        </CardContent>
      </Card>

      {/* Hint: Management in Central Portal */}
      <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4 flex items-start gap-3" data-testid="central-portal-hint">
        <ExternalLink className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-indigo-300">Lizenzverwaltung im zentralen Portal</p>
          <p className="text-xs text-indigo-400/70 mt-1">
            Lizenzen erstellen, verlängern, sperren und Token generieren — alles zentral unter <strong>/operator</strong>
          </p>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value, mono }) {
  return (
    <div>
      <p className="text-xs text-zinc-500 mb-0.5">{label}</p>
      <p className={`text-zinc-300 ${mono ? 'font-mono text-xs' : ''}`}>{value}</p>
    </div>
  );
}

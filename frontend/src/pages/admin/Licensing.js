/**
 * Local Admin — Licensing (Read-Only Status View)
 * License management stays in the central portal; this page focuses on local device visibility.
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
  KeyRound,
  Shield,
  Monitor,
  RefreshCw,
  CheckCircle,
  Clock,
  XCircle,
  AlertTriangle,
  Server,
  ExternalLink,
  Link2,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { useI18n } from '../../context/I18nContext';
import { toast } from 'sonner';
import {
  AdminEmptyState,
  AdminPage,
  AdminSection,
  AdminStatCard,
  AdminStatsGrid,
  AdminStatusPill,
} from '../../components/admin/AdminShell';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  active: { icon: CheckCircle, tone: 'emerald', label: 'Aktiv' },
  grace: { icon: Clock, tone: 'amber', label: 'Toleranzzeitraum' },
  expired: { icon: XCircle, tone: 'red', label: 'Abgelaufen' },
  blocked: { icon: XCircle, tone: 'red', label: 'Gesperrt' },
  test: { icon: Shield, tone: 'blue', label: 'Test-Lizenz' },
  no_license: { icon: AlertTriangle, tone: 'neutral', label: 'Keine Lizenz' },
};

function formatDateTime(value) {
  if (!value) return '–';
  return new Date(value).toLocaleString('de-DE');
}

function formatDate(value) {
  if (!value) return '–';
  return new Date(value).toLocaleDateString('de-DE');
}

function InfoGrid({ items }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.5)] px-4 py-3"
        >
          <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">{item.label}</p>
          <p className={`mt-2 break-all text-sm text-[var(--color-text)] ${item.mono ? 'font-mono' : ''}`}>{item.value || '–'}</p>
          {item.hint ? <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{item.hint}</p> : null}
        </div>
      ))}
    </div>
  );
}

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

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

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

  const isRegistered = regStatus?.status === 'registered';
  const licStat = licStatus?.license_status || 'no_license';
  const statusConf = STATUS_CONFIG[licStat] || STATUS_CONFIG.no_license;

  const registrationItems = useMemo(
    () => [
      { label: 'Install-ID', value: regStatus?.install_id, mono: true },
      { label: 'Gerätename', value: regStatus?.device_name },
      { label: 'Customer', value: regStatus?.customer_name },
      {
        label: 'API-Key',
        value: regStatus?.api_key ? `${regStatus.api_key.slice(0, 8)}...` : '–',
        mono: true,
        hint: 'Aus Sicherheitsgründen gekürzt',
      },
      { label: 'Registriert am', value: formatDateTime(regStatus?.registered_at) },
    ],
    [regStatus]
  );

  const licenseItems = useMemo(
    () => [
      { label: 'Plan', value: licStatus?.plan_type || '–' },
      { label: 'Kunde', value: licStatus?.customer_name || '–' },
      { label: 'Ablauf', value: licStatus?.expiry ? formatDate(licStatus.expiry) : 'Unbegrenzt' },
      { label: 'Toleranz bis', value: formatDate(licStatus?.grace_until) },
      { label: 'Binding-Status', value: licStatus?.binding_status || '–' },
      { label: 'Max. Geräte', value: licStatus?.max_devices || '–' },
    ],
    [licStatus]
  );

  const syncItems = useMemo(
    () => [
      { label: 'Zentraler Server', value: syncConfig?.central_server_url || '–' },
      { label: 'Letzte erfolgreiche Sichtung', value: formatDateTime(licStatus?.server_timestamp) },
      { label: 'Sync-Intervall', value: syncConfig?.sync_interval_minutes ? `${syncConfig.sync_interval_minutes} Min.` : '–' },
    ],
    [licStatus, syncConfig]
  );

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-amber-500" />
      </div>
    );
  }

  return (
    <AdminPage
      eyebrow="Central license mirror"
      title={t('licensing') || 'Lizenz & Registrierung'}
      description="Bewusst lokal und read-only: Hier sieht man nur, ob dieses Gerät registriert ist, welche Lizenz gespiegelt wurde und wann zuletzt mit dem Zentralserver abgeglichen wurde."
      actions={
        <Button
          onClick={handleForceSync}
          disabled={syncing || !isRegistered}
          className="bg-amber-500 text-black hover:bg-amber-400 disabled:bg-zinc-800 disabled:text-zinc-500"
          data-testid="force-sync-btn"
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
          Sync erzwingen
        </Button>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard icon={Monitor} label="Gerätestatus" value={isRegistered ? 'Registriert' : 'Ausstehend'} hint={regStatus?.device_name || 'Noch keine Registrierung sichtbar'} tone={isRegistered ? 'emerald' : 'amber'} />
        <AdminStatCard icon={KeyRound} label="Lizenzstatus" value={statusConf.label} hint={licStatus?.plan_type || 'Kein aktiver Plan gespiegelt'} tone={statusConf.tone} />
        <AdminStatCard icon={Server} label="Sync-Ziel" value={syncConfig?.central_server_url ? 'Verbunden' : 'Unbekannt'} hint={syncConfig?.central_server_url || 'Kein Zentralserver gemeldet'} tone={syncConfig?.central_server_url ? 'blue' : 'neutral'} />
        <AdminStatCard icon={Link2} label="Portal-Verwaltung" value="/portal" hint="Erstellen, sperren, verlängern und binden passiert zentral" tone="violet" />
      </AdminStatsGrid>

      <div className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
        <div className="space-y-6">
          <AdminSection
            title="Geräte-Registrierung"
            description="Lokale Sicht auf die zentrale Gerätebindung. Wenn hier noch nichts steht, ist das Gerät aus Venue-Sicht noch nicht sauber angebunden."
            actions={<AdminStatusPill tone={isRegistered ? 'emerald' : 'amber'}>{isRegistered ? 'registriert' : 'nicht registriert'}</AdminStatusPill>}
          >
            {isRegistered ? (
              <InfoGrid items={registrationItems} />
            ) : (
              <AdminEmptyState
                icon={Monitor}
                title="Dieses Gerät ist noch nicht registriert"
                description="Die Registrierung erfolgt über den Kiosk-/Pairing-Fluss. Erst danach tauchen Install-ID, Customer und API-Bindung sauber hier auf."
              />
            )}
          </AdminSection>

          <AdminSection
            title="Lizenzstatus"
            description="Was zuletzt lokal gespiegelt wurde. Diese Ansicht ersetzt keine zentrale Lizenzverwaltung, sondern zeigt nur den Stand, mit dem das Gerät gerade arbeitet."
            actions={<AdminStatusPill tone={statusConf.tone}>{statusConf.label}</AdminStatusPill>}
          >
            {licStatus ? (
              <InfoGrid items={licenseItems} />
            ) : (
              <AdminEmptyState
                icon={KeyRound}
                title="Keine Lizenzinformationen vorhanden"
                description="Entweder wurde noch nichts gespiegelt oder der Zentralserver hat diesem Gerät aktuell keinen verwertbaren Lizenzstatus geliefert."
              />
            )}
          </AdminSection>
        </div>

        <div className="space-y-6">
          <AdminSection title="Synchronisierung" description="Wichtig für Support: wohin dieses Gerät spricht und wann zuletzt ein zentraler Zeitstempel ankam.">
            <InfoGrid items={syncItems} />
          </AdminSection>

          <AdminSection title="Bewusste Grenze dieser Seite" description="Warum hier absichtlich keine Verwaltungsknöpfe mehr wohnen.">
            <div className="rounded-2xl border border-[rgb(var(--color-primary-rgb)/0.18)] bg-[rgb(var(--color-primary-rgb)/0.08)] p-4 text-sm leading-6 text-[var(--color-text-secondary)]">
              Lizenzobjekte, Laufzeiten, Sperren, Rebinding und Token-Erstellung gehören ins zentrale Portal. Diese lokale Seite ist nur die operative Kontrollanzeige, damit niemand im Venue im falschen Layer herumdoktert.
            </div>
          </AdminSection>

          <AdminSection title="Portal-Hinweis" description="Direkter Kontext für Operatoren und Support.">
            <div className="flex items-start gap-3 rounded-2xl border border-indigo-500/20 bg-indigo-500/8 p-4" data-testid="central-portal-hint">
              <ExternalLink className="mt-0.5 h-5 w-5 flex-shrink-0 text-indigo-400" />
              <div>
                <p className="font-medium text-indigo-200">Lizenzverwaltung läuft zentral</p>
                <p className="mt-1 text-sm leading-6 text-indigo-200/80">
                  Lizenzen erstellen, verlängern, sperren oder neue Bindungstoken erzeugen: alles zentral unter <strong>/portal</strong>. Lokal bleibt nur die Sichtprüfung.
                </p>
              </div>
            </div>
          </AdminSection>
        </div>
      </div>
    </AdminPage>
  );
}

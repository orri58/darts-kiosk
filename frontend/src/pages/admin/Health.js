import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Activity,
  AlertTriangle,
  Camera,
  CheckCircle,
  Clock,
  HardDrive,
  RefreshCw,
  Server,
  ShieldCheck,
  Wifi,
  WifiOff,
  XCircle,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import {
  AdminEmptyState,
  AdminLinkTile,
  AdminPage,
  AdminSection,
  AdminStatCard,
  AdminStatsGrid,
  AdminStatusPill,
} from '../../components/admin/AdminShell';

const API_ROOT = process.env.REACT_APP_BACKEND_URL;
const API = `${API_ROOT}/api`;

const HEALTH_META = {
  healthy: { label: 'Gesund', tone: 'emerald', icon: CheckCircle },
  degraded: { label: 'Degradiert', tone: 'amber', icon: AlertTriangle },
  unhealthy: { label: 'Kritisch', tone: 'red', icon: XCircle },
};

function formatDateTime(value) {
  if (!value) return '–';
  return new Date(value).toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatUptime(seconds) {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

export default function AdminHealth() {
  const { token } = useAuth();
  const { t } = useI18n();
  const [health, setHealth] = useState(null);
  const [backups, setBackups] = useState(null);
  const [screenshots, setScreenshots] = useState([]);
  const [screenshotUrls, setScreenshotUrls] = useState({});
  const [loading, setLoading] = useState(true);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const fetchHealth = useCallback(async () => {
    try {
      const [healthRes, backupsRes, screenshotsRes] = await Promise.all([
        axios.get(`${API}/health/detailed`, { headers }),
        axios.get(`${API}/backups`, { headers }),
        axios.get(`${API}/health/screenshots`, { headers }),
      ]);

      setHealth(healthRes.data);
      setBackups(backupsRes.data);
      setScreenshots(screenshotsRes.data || []);
    } catch (error) {
      console.error('Failed to fetch health:', error);
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  useEffect(() => {
    let cancelled = false;
    let urlsToRevoke = [];

    const loadImages = async () => {
      if (!screenshots.length) {
        setScreenshotUrls({});
        return;
      }

      const entries = await Promise.all(
        screenshots.map(async (screenshot) => {
          try {
            const response = await axios.get(`${API_ROOT}${screenshot.path}`, {
              headers,
              responseType: 'blob',
            });
            const url = URL.createObjectURL(response.data);
            urlsToRevoke.push(url);
            return [screenshot.filename, url];
          } catch {
            return [screenshot.filename, null];
          }
        })
      );

      if (!cancelled) {
        setScreenshotUrls(
          Object.fromEntries(entries.filter(([, url]) => Boolean(url)))
        );
      }
    };

    loadImages();

    return () => {
      cancelled = true;
      urlsToRevoke.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [screenshots, headers]);

  const metrics = useMemo(() => {
    const agents = Object.entries(health?.agent_status || {});
    const offlineAgents = agents.filter(([, agent]) => !agent.is_online).length;
    const recentBackups = backups?.backups || [];

    return {
      agents,
      offlineAgents,
      observerSuccessRate: health?.observer_metrics?.success_rate || 0,
      observerEvents: health?.observer_metrics?.total_events || 0,
      recentErrors: health?.recent_errors || [],
      latestBackup: recentBackups[0] || null,
      backupCount: backups?.stats?.total_backups || 0,
    };
  }, [health, backups]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  const meta = HEALTH_META[health?.status] || {
    label: health?.status || 'Unbekannt',
    tone: 'neutral',
    icon: Activity,
  };
  const StatusIcon = meta.icon;

  return (
    <AdminPage
      eyebrow="Runtime health"
      title={t('health') || t('system_health')}
      description="Diagnoseoberfläche für Laufzeit-Signale: Services, Agent-Erreichbarkeit, Observer-Fehler und Artefakte. Für Backups, Logs und Neustarts ist die System-Seite zuständig."
      actions={
        <div className="flex flex-wrap gap-2">
          {health?.last_check && (
            <AdminStatusPill tone="blue">
              <Clock className="w-3 h-3" /> geprüft {formatDateTime(health.last_check)}
            </AdminStatusPill>
          )}
          <Button
            onClick={fetchHealth}
            variant="outline"
            className="border-zinc-700 text-zinc-300 hover:text-white"
          >
            <RefreshCw className="w-4 h-4 mr-2" /> Aktualisieren
          </Button>
        </div>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard
          icon={StatusIcon}
          label="Gesamtstatus"
          value={meta.label}
          hint="Abgeleitet aus Observer- und Agent-Signalen"
          tone={meta.tone}
        />
        <AdminStatCard
          icon={Clock}
          label="Uptime"
          value={formatUptime(health?.uptime_seconds || 0)}
          hint={health?.start_time ? `Seit ${formatDateTime(health.start_time)}` : 'Seit letztem Prozessstart'}
          tone="blue"
        />
        <AdminStatCard
          icon={WifiOff}
          label="Offline Agents"
          value={metrics.offlineAgents}
          hint={`${metrics.agents.length} Agent-Ziele überwacht`}
          tone={metrics.offlineAgents > 0 ? 'red' : 'emerald'}
        />
        <AdminStatCard
          icon={Activity}
          label="Observer Erfolgsrate"
          value={`${metrics.observerSuccessRate.toFixed(0)}%`}
          hint={`${metrics.observerEvents} erfasste Observer-Events`}
          tone={metrics.observerSuccessRate >= 80 ? 'emerald' : metrics.observerEvents > 0 ? 'amber' : 'neutral'}
        />
      </AdminStatsGrid>

      <div className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
        <div className="space-y-6">
          <AdminSection title="Runtime-Dienste" description="Was der laufende Prozess selbst über Scheduler, Backup-Service und Observer meldet.">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-white">Session Scheduler</p>
                    <p className="text-xs text-zinc-500">Auto-Lock und Expiry-Prüfung</p>
                  </div>
                  <AdminStatusPill tone={health?.scheduler_running ? 'emerald' : 'red'}>
                    {health?.scheduler_running ? 'Läuft' : 'Gestoppt'}
                  </AdminStatusPill>
                </div>
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-white">Backup-Service</p>
                    <p className="text-xs text-zinc-500">Geplanter DB-Backup-Worker</p>
                  </div>
                  <AdminStatusPill tone={health?.backup_service_running ? 'emerald' : 'red'}>
                    {health?.backup_service_running ? 'Läuft' : 'Gestoppt'}
                  </AdminStatusPill>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-zinc-800 bg-zinc-900/60 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-lg font-semibold text-white">Observer-Diagnostik</p>
                <AdminStatusPill tone={metrics.observerSuccessRate >= 80 ? 'emerald' : metrics.observerEvents > 0 ? 'amber' : 'neutral'}>
                  {metrics.observerSuccessRate.toFixed(1)}%
                </AdminStatusPill>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Events gesamt</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{health?.observer_metrics?.total_events || 0}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Erfolgreich</p>
                  <p className="mt-2 text-2xl font-semibold text-emerald-400">{health?.observer_metrics?.successful || 0}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Fehlgeschlagen</p>
                  <p className="mt-2 text-2xl font-semibold text-red-400">{health?.observer_metrics?.failed || 0}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Letzter Erfolg</p>
                  <p className="mt-2 text-sm text-zinc-200">{formatDateTime(health?.observer_metrics?.last_success)}</p>
                </div>
              </div>

              {health?.observer_metrics?.last_error && (
                <div className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                  <span className="font-medium">Letzter Observer-Fehler:</span> {health.observer_metrics.last_error}
                </div>
              )}
            </div>
          </AdminSection>

          <AdminSection title="Agent-Erreichbarkeit" description="Nur Boards mit gepflegter Agent-API-URL werden hier aktiv überwacht.">
            {metrics.agents.length > 0 ? (
              <div className="space-y-3">
                {metrics.agents.map(([boardId, agent]) => (
                  <div key={boardId} className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-4">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium text-white">{boardId}</p>
                          <AdminStatusPill tone={agent.is_online ? 'emerald' : 'red'}>
                            {agent.is_online ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                            {agent.is_online ? 'Online' : 'Offline'}
                          </AdminStatusPill>
                        </div>
                        <p className="mt-1 break-all text-sm font-mono text-zinc-500">{agent.agent_url}</p>
                        <p className="mt-1 text-xs text-zinc-500">
                          Letzter Heartbeat: {formatDateTime(agent.last_heartbeat)}
                          {agent.consecutive_failures ? ` · Fehler in Folge: ${agent.consecutive_failures}` : ''}
                        </p>
                      </div>

                      <div className="text-left md:text-right">
                        <p className="text-sm font-medium text-white">
                          {agent.latency_ms ? `${agent.latency_ms} ms` : '–'}
                        </p>
                        <p className="text-xs text-zinc-500">Latenz</p>
                      </div>
                    </div>

                    {agent.error && (
                      <div className="mt-3 rounded-2xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-100">
                        {agent.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <AdminEmptyState
                icon={Wifi}
                title="Keine Agent-Ziele in der Health-Überwachung"
                description="Diese Ansicht füllt sich erst, wenn Boards mit agent_api_base_url konfiguriert sind. Discovery allein reicht dafür noch nicht."
              />
            )}
          </AdminSection>
        </div>

        <div className="space-y-6">
          <AdminSection title="Aktuelle Auffälligkeiten" description="Neueste Fehler und Hinweise aus dem Runtime-Monitor.">
            {metrics.recentErrors.length > 0 ? (
              <div className="space-y-3">
                {metrics.recentErrors.slice().reverse().slice(0, 8).map((error, index) => (
                  <div key={`${error.timestamp}-${index}`} className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <AdminStatusPill tone="red">{error.category || 'runtime'}</AdminStatusPill>
                      <span className="text-xs text-zinc-500">{formatDateTime(error.timestamp)}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-300">{error.message}</p>
                    {error.screenshot && (
                      <p className="mt-2 text-xs text-zinc-500">Screenshot-Artefakt vorhanden</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">Keine aktuellen Runtime-Fehler im Puffer.</p>
            )}
          </AdminSection>

          <AdminSection title="Backup-Posture" description="Nur Lesesicht — Verwaltung bleibt absichtlich auf der System-Seite.">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                <span className="text-zinc-400">DB-Backups vorhanden</span>
                <AdminStatusPill tone={metrics.backupCount > 0 ? 'emerald' : 'amber'}>
                  <HardDrive className="w-3 h-3" /> {metrics.backupCount}
                </AdminStatusPill>
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                <p className="text-zinc-400">Letztes Backup</p>
                <p className="mt-1 font-medium text-white">
                  {metrics.latestBackup ? formatDateTime(metrics.latestBackup.created_at) : 'Noch keines vorhanden'}
                </p>
              </div>
            </div>
          </AdminSection>

          <AdminSection title="Direkt weiter" description="Wenn Diagnose in Aktion umschlagen soll.">
            <div className="space-y-3">
              <AdminLinkTile
                icon={Server}
                title="System"
                description="Für Logs, Backups, Updates und Neustarts auf die Maintenance-Fläche wechseln."
                href="/admin/system"
                tone="amber"
                cta="Zu System"
              />
              <AdminLinkTile
                icon={ShieldCheck}
                title="Discovery"
                description="Wenn ein Agent fehlt, zuerst LAN-Sichtbarkeit und Pairing prüfen."
                href="/admin/discovery"
                tone="blue"
                cta="Discovery öffnen"
              />
            </div>
          </AdminSection>
        </div>
      </div>

      <AdminSection title="Fehler-Screenshots" description="Gesicherte Artefakte aus data/autodarts_debug. Hilfreich für Support, aber kein vollständiges Screen-Recording.">
        {screenshots.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {screenshots.map((screenshot) => (
              <a
                key={screenshot.filename}
                href={screenshotUrls[screenshot.filename] || '#'}
                target="_blank"
                rel="noreferrer"
                className="overflow-hidden rounded-3xl border border-zinc-800 bg-zinc-900/70 transition hover:border-amber-500/30"
              >
                <div className="aspect-[16/9] bg-zinc-950">
                  {screenshotUrls[screenshot.filename] ? (
                    <img
                      src={screenshotUrls[screenshot.filename]}
                      alt={screenshot.filename}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-zinc-600">
                      <Camera className="h-8 w-8" />
                    </div>
                  )}
                </div>
                <div className="p-4">
                  <p className="truncate text-sm font-medium text-white">{screenshot.filename}</p>
                  <p className="mt-1 text-xs text-zinc-500">{formatDateTime(screenshot.created_at)}</p>
                </div>
              </a>
            ))}
          </div>
        ) : (
          <AdminEmptyState
            icon={Camera}
            title="Keine Fehler-Screenshots vorhanden"
            description="Wenn der Observer aktuell sauber läuft, bleibt dieser Bereich absichtlich leer."
          />
        )}
      </AdminSection>
    </AdminPage>
  );
}

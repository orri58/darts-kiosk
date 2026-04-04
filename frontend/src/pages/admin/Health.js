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

const READINESS_META = {
  ready: { label: 'Einsatzbereit', tone: 'emerald', icon: ShieldCheck },
  warning: { label: 'Mit Hinweisen', tone: 'amber', icon: AlertTriangle },
  blocked: { label: 'Nicht bereit', tone: 'red', icon: XCircle },
};

const CHECK_STATUS_META = {
  ok: { label: 'OK', tone: 'emerald' },
  warn: { label: 'Prüfen', tone: 'amber' },
  fail: { label: 'Blocker', tone: 'red' },
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
  const [readiness, setReadiness] = useState(null);
  const [backups, setBackups] = useState(null);
  const [consistency, setConsistency] = useState(null);
  const [repairingBoardId, setRepairingBoardId] = useState('');
  const [screenshots, setScreenshots] = useState([]);
  const [screenshotUrls, setScreenshotUrls] = useState({});
  const [loading, setLoading] = useState(true);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const fetchHealth = useCallback(async () => {
    try {
      const [healthRes, readinessRes, backupsRes, consistencyRes, screenshotsRes] = await Promise.all([
        axios.get(`${API}/health/detailed`, { headers }),
        axios.get(`${API}/system/readiness`, { headers }),
        axios.get(`${API}/backups`, { headers }),
        axios.get(`${API}/system/session-consistency`, { headers }),
        axios.get(`${API}/health/screenshots`, { headers }),
      ]);

      setHealth(healthRes.data);
      setReadiness(readinessRes.data);
      setBackups(backupsRes.data);
      setConsistency(consistencyRes.data);
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

  const handleRepairBoard = useCallback(async (boardId) => {
    if (!boardId) return;
    if (!window.confirm(`Konsistenz-Reparatur für ${boardId} ausführen?`)) return;

    setRepairingBoardId(boardId);
    try {
      await axios.post(`${API}/system/session-consistency/repair/${encodeURIComponent(boardId)}`, {}, { headers });
      await fetchHealth();
    } catch (error) {
      console.error('Failed to repair board consistency:', error);
    } finally {
      setRepairingBoardId('');
    }
  }, [headers, fetchHealth]);

  const metrics = useMemo(() => {
    const agents = Object.entries(health?.agent_status || {});
    const offlineAgents = agents.filter(([, agent]) => !agent.is_online).length;
    const recentBackups = backups?.backups || [];
    const readinessChecks = readiness?.checks || [];
    const readinessGroups = Object.entries(
      readinessChecks.reduce((acc, check) => {
        const bucket = acc[check.group] || [];
        bucket.push(check);
        acc[check.group] = bucket;
        return acc;
      }, {})
    );

    return {
      agents,
      offlineAgents,
      observerSuccessRate: health?.observer_metrics?.success_rate || 0,
      observerEvents: health?.observer_metrics?.total_events || 0,
      recentErrors: health?.recent_errors || [],
      latestBackup: recentBackups[0] || null,
      backupCount: backups?.stats?.total_backups || 0,
      readinessChecks,
      readinessGroups,
      readinessFailCount: readiness?.summary?.fail_count || 0,
      readinessWarnCount: readiness?.summary?.warn_count || 0,
      consistencyBoards: consistency?.boards || [],
      consistencyFindings: consistency?.findings || [],
      consistencyCriticalCount: consistency?.summary?.critical_count || 0,
      consistencyWarningCount: consistency?.summary?.warning_count || 0,
    };
  }, [health, backups, readiness, consistency]);

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
  const readinessMeta = READINESS_META[readiness?.status] || {
    label: readiness?.status || 'Unbekannt',
    tone: 'neutral',
    icon: ShieldCheck,
  };
  const ReadinessIcon = readinessMeta.icon;

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
          icon={ReadinessIcon}
          label="Board-PC Readiness"
          value={readinessMeta.label}
          hint={readiness?.board?.exists ? `${readiness.board.board_id} · ${readiness.board.name || 'ohne Namen'}` : 'Lokales Board fehlt oder ist unklar'}
          tone={readinessMeta.tone}
        />
        <AdminStatCard
          icon={AlertTriangle}
          label="Blockierende Checks"
          value={metrics.readinessFailCount}
          hint={`${metrics.readinessWarnCount} weitere Hinweise`}
          tone={metrics.readinessFailCount > 0 ? 'red' : metrics.readinessWarnCount > 0 ? 'amber' : 'emerald'}
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
        <AdminStatCard
          icon={AlertTriangle}
          label="Lifecycle-Issues"
          value={metrics.consistencyFindings.length}
          hint={`${metrics.consistencyCriticalCount} kritisch · ${metrics.consistencyWarningCount} warnend`}
          tone={metrics.consistencyCriticalCount > 0 ? 'red' : metrics.consistencyWarningCount > 0 ? 'amber' : 'emerald'}
        />
      </AdminStatsGrid>

      <AdminSection
        title="Session / Board consistency"
        description="Erkennt Runtime-Widersprüche zwischen Board-Status, aktiver Session und terminalen Lifecycle-Zuständen. Genau das Zeug, das nach Restarts oder kaputten Observer-Enden später Ärger macht."
        actions={
          <AdminStatusPill tone={metrics.consistencyCriticalCount > 0 ? 'red' : metrics.consistencyWarningCount > 0 ? 'amber' : 'emerald'}>
            {metrics.consistencyFindings.length} Finding(s)
          </AdminStatusPill>
        }
      >
        {metrics.consistencyFindings.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-[1.05fr,0.95fr]">
            <div className="space-y-3">
              {metrics.consistencyFindings.map((finding, index) => (
                <div key={`${finding.board_id}-${finding.code}-${index}`} className="rounded-3xl border border-zinc-800 bg-zinc-900/70 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <AdminStatusPill tone={finding.severity === 'critical' ? 'red' : finding.severity === 'warning' ? 'amber' : 'blue'}>
                      {finding.severity}
                    </AdminStatusPill>
                    <AdminStatusPill tone="neutral">{finding.board_id}</AdminStatusPill>
                    <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">{finding.code}</span>
                  </div>
                  <p className="mt-3 text-sm font-medium text-white">{finding.summary}</p>
                  <p className="mt-2 text-sm text-zinc-400">{finding.detail}</p>
                  <p className="mt-2 text-xs text-zinc-500">Empfehlung: {finding.recommended_action}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                    <span>Board: {finding.board_status || '–'}</span>
                    <span>Session: {finding.session_status || '–'}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="space-y-3">
              {metrics.consistencyBoards.map((board) => (
                <div key={board.board_id} className="rounded-3xl border border-zinc-800 bg-zinc-900/70 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-white font-medium">{board.board_id}</p>
                      <p className="text-xs text-zinc-500">{board.name || 'Ohne Namen'} · Status: {board.board_status}</p>
                    </div>
                    <AdminStatusPill tone={board.issues?.length ? (board.issues.some((item) => item.severity === 'critical') ? 'red' : 'amber') : 'emerald'}>
                      {board.issues?.length || 0} Issues
                    </AdminStatusPill>
                  </div>
                  <div className="mt-3 rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3 text-xs text-zinc-400">
                    <p>Aktive Sessions: {board.active_session_count}</p>
                    <p className="mt-1 break-all">Letzte Session: {board.latest_session?.id || '–'} · {board.latest_session?.status || 'keine'}</p>
                  </div>
                  {board.issues?.length > 0 && (
                    <Button
                      onClick={() => handleRepairBoard(board.board_id)}
                      disabled={repairingBoardId === board.board_id}
                      className="mt-3 w-full bg-amber-500 text-black hover:bg-amber-400"
                    >
                      <RefreshCw className={`mr-2 h-4 w-4 ${repairingBoardId === board.board_id ? 'animate-spin' : ''}`} />
                      {repairingBoardId === board.board_id ? 'Repair läuft…' : 'Safe repair ausführen'}
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <AdminEmptyState
            icon={ShieldCheck}
            title="Keine Board-/Session-Widersprüche erkannt"
            description="Lifecycle sieht konsistent aus. Genau so will man das nach Restarts und Timeout-Enden haben."
          />
        )}
      </AdminSection>

      <AdminSection
        title="Board-PC readiness"
        description="Kompakte Preflight-Sicht dafür, ob dieser Rechner lokal sinnvoll betrieben und supportet werden kann. Keine Buzzwords, nur die Checks, die im Problemfall wirklich zählen."
        actions={
          <AdminStatusPill tone={readinessMeta.tone}>
            <ReadinessIcon className="w-3 h-3" /> {readinessMeta.label}
          </AdminStatusPill>
        }
      >
        <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
          <div className="space-y-4">
            {(metrics.readinessFailCount > 0 || metrics.readinessWarnCount > 0) && (
              <div className={`rounded-3xl border px-5 py-4 ${metrics.readinessFailCount > 0 ? 'border-red-500/30 bg-red-500/10' : 'border-amber-500/30 bg-amber-500/10'}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <AdminStatusPill tone={metrics.readinessFailCount > 0 ? 'red' : 'amber'}>
                    {metrics.readinessFailCount > 0 ? 'Blocker vorhanden' : 'Hinweise vorhanden'}
                  </AdminStatusPill>
                  <p className="text-sm text-white">
                    {metrics.readinessFailCount > 0
                      ? `${metrics.readinessFailCount} Check(s) blockieren eine saubere lokale Betriebsbereitschaft.`
                      : `${metrics.readinessWarnCount} Check(s) sollten vor dem nächsten echten Einsatz überprüft werden.`}
                  </p>
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {metrics.readinessChecks
                    .filter((check) => check.status !== 'ok')
                    .slice(0, 6)
                    .map((check) => {
                      const checkMeta = CHECK_STATUS_META[check.status] || CHECK_STATUS_META.warn;
                      return (
                        <div key={check.key} className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-medium text-white">{check.label}</p>
                            <AdminStatusPill tone={checkMeta.tone}>{checkMeta.label}</AdminStatusPill>
                          </div>
                          <p className="mt-1 text-xs text-zinc-300 break-all">{check.detail}</p>
                          {check.remediation && <p className="mt-2 text-xs text-zinc-500">{check.remediation}</p>}
                        </div>
                      );
                    })}
                </div>
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              {metrics.readinessGroups.map(([groupName, groupChecks]) => (
                <div key={groupName} className="rounded-3xl border border-zinc-800 bg-zinc-900/70 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold uppercase tracking-[0.18em] text-zinc-400">{groupName}</p>
                    <AdminStatusPill
                      tone={groupChecks.some((item) => item.status === 'fail') ? 'red' : groupChecks.some((item) => item.status === 'warn') ? 'amber' : 'emerald'}
                    >
                      {groupChecks.filter((item) => item.status === 'ok').length}/{groupChecks.length} ok
                    </AdminStatusPill>
                  </div>
                  <div className="mt-3 space-y-3">
                    {groupChecks.map((check) => {
                      const checkMeta = CHECK_STATUS_META[check.status] || CHECK_STATUS_META.warn;
                      return (
                        <div key={check.key} className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm text-white">{check.label}</p>
                            <AdminStatusPill tone={checkMeta.tone}>{checkMeta.label}</AdminStatusPill>
                          </div>
                          <p className="mt-1 text-xs text-zinc-500 break-all">{check.detail}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl border border-zinc-800 bg-zinc-900/70 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-white">Lokales Board</p>
                  <p className="text-sm text-zinc-500">Die Identität dieses Rechners muss zu Board-ID und Ziel-URLs passen.</p>
                </div>
                <AdminStatusPill tone={readiness?.board?.exists ? 'emerald' : 'red'}>
                  {readiness?.board?.exists ? 'Gefunden' : 'Fehlt'}
                </AdminStatusPill>
              </div>
              <div className="mt-4 space-y-3 text-sm">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                  <p className="text-zinc-500">Board-ID</p>
                  <p className="mt-1 font-mono text-white">{readiness?.board?.board_id || readiness?.local_board_id || '–'}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                  <p className="text-zinc-500">Board-Konfiguration</p>
                  <p className="mt-1 text-white">{readiness?.board?.name || 'Kein Name verfügbar'}</p>
                  <p className="mt-1 text-xs text-zinc-500">Status: {readiness?.board?.status || 'unbekannt'}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                  <p className="text-zinc-500">Observer-Ziel</p>
                  <p className="mt-1 break-all font-mono text-xs text-zinc-300">{readiness?.board?.autodarts_target_url || 'Nicht gesetzt'}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                  <p className="text-zinc-500">Agent-API</p>
                  <p className="mt-1 break-all font-mono text-xs text-zinc-300">{readiness?.board?.agent_api_base_url || 'Nicht gesetzt'}</p>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-zinc-800 bg-zinc-900/70 p-5">
              <p className="text-lg font-semibold text-white">Lokale Operator-URLs</p>
              <div className="mt-4 space-y-3">
                {Object.entries(readiness?.local_urls || {}).map(([key, value]) => (
                  <div key={key} className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">{key}</p>
                    <p className="mt-1 break-all font-mono text-xs text-zinc-200">{value}</p>
                  </div>
                ))}
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">Datenbank</p>
                  <p className="mt-1 break-all font-mono text-xs text-zinc-200">{readiness?.runtime?.database_path || '–'}</p>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-zinc-800 bg-zinc-900/70 p-5">
              <p className="text-lg font-semibold text-white">Nächste sinnvolle Schritte</p>
              <div className="mt-4 space-y-2">
                {(readiness?.recommended_actions || []).map((step, index) => (
                  <div key={`${index}-${step}`} className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3 text-sm text-zinc-300">
                    <span className="mr-2 text-zinc-500">{index + 1}.</span>
                    {step}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </AdminSection>

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

import { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { Activity, Clock, FileText, RefreshCw, ShieldCheck, Target, User } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import {
  AdminEmptyState,
  AdminPage,
  AdminSection,
  AdminStatCard,
  AdminStatsGrid,
  AdminStatusPill,
} from '../../components/admin/AdminShell';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getActionTone(action = '') {
  if (action.includes('login')) return 'blue';
  if (action.includes('unlock')) return 'emerald';
  if (action.includes('lock')) return 'red';
  if (action.includes('create')) return 'amber';
  if (action.includes('update')) return 'violet';
  if (action.includes('delete')) return 'red';
  return 'neutral';
}

function getSessionStatusMeta(status) {
  switch (status) {
    case 'active':
      return { tone: 'amber', label: 'Aktiv' };
    case 'finished':
      return { tone: 'emerald', label: 'Beendet' };
    case 'expired':
      return { tone: 'blue', label: 'Abgelaufen' };
    case 'cancelled':
      return { tone: 'red', label: 'Abgebrochen' };
    default:
      return { tone: 'neutral', label: status || 'Unbekannt' };
  }
}

export default function AdminLogs() {
  const { token } = useAuth();
  const { t } = useI18n();
  const [auditLogs, setAuditLogs] = useState([]);
  const [sessionLogs, setSessionLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const [auditRes, sessionRes] = await Promise.all([
        axios.get(`${API}/logs/audit?limit=50`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/logs/sessions?limit=50`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setAuditLogs(auditRes.data || []);
      setSessionLogs(sessionRes.data || []);
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const stats = useMemo(() => {
    const uniqueUsers = new Set(auditLogs.map((log) => log.username).filter(Boolean)).size;
    const activeSessions = sessionLogs.filter((session) => session.status === 'active').length;
    return {
      auditCount: auditLogs.length,
      sessionCount: sessionLogs.length,
      uniqueUsers,
      activeSessions,
    };
  }, [auditLogs, sessionLogs]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-amber-500" />
      </div>
    );
  }

  return (
    <AdminPage
      eyebrow="Operational history"
      title={t('logs')}
      description="Die letzten Audit- und Session-Ereignisse in einer ruhigeren Operator-Ansicht. Gut für Support, Plausibilitätschecks und kurze Rückfragen — nicht als forensisches SIEM verkleidet."
      actions={
        <Button onClick={fetchLogs} variant="outline" className="border-zinc-700 text-zinc-300 hover:text-white">
          <RefreshCw className="mr-2 h-4 w-4" /> Aktualisieren
        </Button>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard icon={ShieldCheck} label="Audit-Einträge" value={stats.auditCount} hint="letzte 50 System-/Benutzeraktionen" tone="blue" />
        <AdminStatCard icon={Target} label="Session-Einträge" value={stats.sessionCount} hint="letzte 50 Venue-Sessions" tone="amber" />
        <AdminStatCard icon={User} label="Benutzer im Audit" value={stats.uniqueUsers} hint="sichtbar im aktuellen Fenster" tone="violet" />
        <AdminStatCard icon={Activity} label="Aktive Sessions" value={stats.activeSessions} hint="Status in der Session-Historie" tone={stats.activeSessions > 0 ? 'emerald' : 'neutral'} />
      </AdminStatsGrid>

      <Tabs defaultValue="audit" className="space-y-6">
        <TabsList className="sticky top-3 z-20 flex h-auto flex-nowrap gap-1 overflow-x-auto rounded-[1.4rem] border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.82)] p-1.5 shadow-[0_16px_36px_rgba(0,0,0,0.22)] backdrop-blur">
          <TabsTrigger value="audit" className="rounded-[1rem] px-4 py-2.5 data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <FileText className="mr-2 h-4 w-4" /> Audit Log
          </TabsTrigger>
          <TabsTrigger value="sessions" className="rounded-[1rem] px-4 py-2.5 data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Target className="mr-2 h-4 w-4" /> Sessions
          </TabsTrigger>
        </TabsList>

        <TabsContent value="audit">
          <AdminSection
            title="Audit-Protokoll"
            description="Konfigurations- und Zugriffsaktionen in kompakter Chronologie."
            actions={<AdminStatusPill tone="blue">{auditLogs.length} Einträge</AdminStatusPill>}
          >
            {auditLogs.length === 0 ? (
              <AdminEmptyState
                icon={ShieldCheck}
                title="Noch keine Audit-Einträge sichtbar"
                description="Wenn Admin-Aktionen, Logins oder Konfigurationsänderungen passieren, tauchen sie hier gesammelt auf."
              />
            ) : (
              <div className="space-y-3">
                {auditLogs.map((log) => (
                  <div
                    key={log.id}
                    className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.52)] p-4"
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <AdminStatusPill tone={getActionTone(log.action)}>{log.action}</AdminStatusPill>
                          {log.entity_type ? <AdminStatusPill tone="neutral">{log.entity_type}</AdminStatusPill> : null}
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-[var(--color-text-secondary)]">
                          <span className="inline-flex items-center gap-1.5"><User className="h-3.5 w-3.5" />{log.username || 'system'}</span>
                          <span className="inline-flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" />{formatDate(log.created_at)}</span>
                        </div>
                        {log.details ? (
                          <div className="mt-3 rounded-2xl border border-[rgb(var(--color-border-rgb)/0.72)] bg-[rgb(var(--color-bg-rgb)/0.46)] px-3 py-2 font-mono text-xs text-[var(--color-text-secondary)] overflow-x-auto">
                            {JSON.stringify(log.details)}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </AdminSection>
        </TabsContent>

        <TabsContent value="sessions">
          <AdminSection
            title="Session-Verlauf"
            description="Die letzten Sessions mit Status, Umfang und monetärem Kontext für schnelle Venue-Rückfragen."
            actions={<AdminStatusPill tone="amber">{sessionLogs.length} Einträge</AdminStatusPill>}
          >
            {sessionLogs.length === 0 ? (
              <AdminEmptyState
                icon={Target}
                title="Noch keine Sessions vorhanden"
                description="Sobald lokale Sessions angelegt oder beendet werden, erscheint hier der jüngste Verlauf."
              />
            ) : (
              <div className="space-y-4">
                {sessionLogs.map((session) => {
                  const status = getSessionStatusMeta(session.status);
                  return (
                    <div
                      key={session.id}
                      className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.52)] p-4"
                    >
                      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <AdminStatusPill tone={status.tone}>{status.label}</AdminStatusPill>
                            <span className="font-mono text-xs text-[var(--color-text-muted)]">{session.id.slice(0, 8)}...</span>
                          </div>
                          <div className="mt-3">
                            <p className="text-base font-semibold text-[var(--color-text)]">{session.game_type || 'N/A'}</p>
                            <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Modus: {session.pricing_mode || '–'} • Spieler: {session.players_count ?? '–'}</p>
                          </div>
                        </div>

                        <div className="grid min-w-0 gap-3 sm:grid-cols-2 xl:min-w-[360px] xl:grid-cols-2">
                          <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.7)] bg-[rgb(var(--color-bg-rgb)/0.42)] px-3 py-2">
                            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Credits</p>
                            <p className="mt-1 text-sm text-[var(--color-text)]">{session.credits_remaining} / {session.credits_total}</p>
                          </div>
                          <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.7)] bg-[rgb(var(--color-bg-rgb)/0.42)] px-3 py-2">
                            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Preis</p>
                            <p className="mt-1 text-sm font-semibold text-[var(--color-primary)]">{session.price_total?.toFixed(2)} €</p>
                          </div>
                          <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.7)] bg-[rgb(var(--color-bg-rgb)/0.42)] px-3 py-2 sm:col-span-2">
                            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Zeitfenster</p>
                            <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Start: {formatDate(session.started_at)}{session.ended_at ? ` • Ende: ${formatDate(session.ended_at)}` : ''}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </AdminSection>
        </TabsContent>
      </Tabs>
    </AdminPage>
  );
}

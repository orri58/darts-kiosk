import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCentralAuth } from '../../context/CentralAuthContext';
import {
  WifiOff, Activity, DollarSign, Zap, AlertTriangle,
  Monitor, Clock, RefreshCw, Gamepad2, Workflow, ExternalLink, ShieldAlert, Send,
  KeyRound, Sparkles, TriangleAlert, Gauge, ArrowRight
} from 'lucide-react';

function formatCurrency(cents) {
  return new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(cents / 100);
}

function timeAgo(isoStr) {
  if (!isoStr) return 'Nie';
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60) return `vor ${Math.floor(diff)}s`;
  if (diff < 3600) return `vor ${Math.floor(diff / 60)} Min.`;
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)} Std.`;
  return `vor ${Math.floor(diff / 86400)} Tagen`;
}

function bucketLabel(value) {
  return {
    healthy: 'Gesund',
    watch: 'Beobachten',
    attention: 'Aktion nötig',
    urgent: 'Dringend',
  }[value] || value || '—';
}

function ReadinessBadge({ bucket }) {
  const tones = {
    healthy: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
    watch: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
    attention: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
    urgent: 'border-red-500/20 bg-red-500/10 text-red-300',
  };
  return <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${tones[bucket] || tones.watch}`}>{bucketLabel(bucket)}</span>;
}

export default function OperatorDashboard() {
  const navigate = useNavigate();
  const { scope, apiBase, authHeaders, isAuthenticated, canReviewRemoteActions } = useCentralAuth();
  const [data, setData] = useState(null);
  const [remoteActionData, setRemoteActionData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const buildScopeParams = useCallback(() => {
    const params = new URLSearchParams();
    if (scope.deviceId) params.set('device_id', scope.deviceId);
    else if (scope.locationId) params.set('location_id', scope.locationId);
    else if (scope.customerId) params.set('customer_id', scope.customerId);
    return params;
  }, [scope]);

  const fetchDashboard = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const params = buildScopeParams();
      const qs = params.toString() ? `?${params.toString()}` : '';
      const remoteActionPromise = scope.deviceId
        ? Promise.all([
            fetch(`${apiBase}/remote-actions/${scope.deviceId}/summary?limit=20`, { headers: authHeaders }),
            fetch(`${apiBase}/remote-actions/${scope.deviceId}/history?limit=5`, { headers: authHeaders }),
          ])
        : (() => {
            const remoteActionParams = new URLSearchParams(params);
            remoteActionParams.set('limit', '12');
            remoteActionParams.set('recent_limit', '5');
            return Promise.all([
              fetch(`${apiBase}/remote-actions/overview?${remoteActionParams.toString()}`, { headers: authHeaders }),
            ]);
          })();

      const [telemetryRes, remoteActionResponses] = await Promise.all([
        fetch(`${apiBase}/telemetry/dashboard${qs}`, { headers: authHeaders }),
        remoteActionPromise,
      ]);
      if (!telemetryRes.ok) throw new Error(`HTTP ${telemetryRes.status}`);
      if (remoteActionResponses.some((res) => !res.ok)) throw new Error(`HTTP ${remoteActionResponses.find((res) => !res.ok)?.status}`);

      setData(await telemetryRes.json());
      if (scope.deviceId) {
        const [summaryRes, historyRes] = remoteActionResponses;
        setRemoteActionData({
          summary: await summaryRes.json(),
          recent_items: (await historyRes.json())?.items || [],
          queue_metrics: { totals: {} },
        });
      } else {
        setRemoteActionData(await remoteActionResponses[0].json());
      }
      setError(null);
    } catch (err) {
      setError(err.message || 'Laden fehlgeschlagen');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isAuthenticated, apiBase, authHeaders, buildScopeParams, scope.deviceId]);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  useEffect(() => {
    const interval = setInterval(fetchDashboard, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  const handleRefresh = () => { setRefreshing(true); fetchDashboard(); };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-red-400" data-testid="dashboard-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
        <p>{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const onlinePct = data.devices_total > 0 ? Math.round((data.devices_online / data.devices_total) * 100) : 0;
  const queueMetrics = remoteActionData?.queue_metrics?.totals || {};
  const queueSummary = remoteActionData?.summary?.counts || {};
  const recentRemoteActions = remoteActionData?.recent_items || [];
  const needsAttention = (queueMetrics.needs_triage || 0) + (data.warnings?.length || 0);
  const licensePortfolio = data.license_portfolio_summary || null;
  const licenseCounts = licensePortfolio?.counts || {};
  const licenseFocus = licensePortfolio?.focus_queues || {};

  const openRemoteActions = (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== '' && value != null) params.set(key, String(value));
    });
    navigate(`/operator/remote-actions${params.toString() ? `?${params.toString()}` : ''}`);
  };

  const openLicense = (licenseId) => navigate(`/operator/licenses/${licenseId}`);
  const openLicenses = () => navigate('/operator/licenses');

  return (
    <div className="space-y-5" data-testid="operator-dashboard">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Betriebsübersicht</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {scope.customerId ? 'Gefilterter Scope' : 'Alle Standorte'} — Live-Daten
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors text-sm"
          data-testid="refresh-dashboard-btn"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          Aktualisieren
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          icon={Monitor}
          label="Geräte online"
          value={`${data.devices_online} / ${data.devices_total}`}
          sub={data.ws_connected_count != null ? `${data.ws_connected_count} via WebSocket` : `${onlinePct}% erreichbar`}
          color={data.devices_online > 0 ? 'emerald' : 'zinc'}
          tid="kpi-online"
        />
        <KpiCard
          icon={DollarSign}
          label="Umsatz heute"
          value={formatCurrency(data.revenue_today_cents)}
          sub={`7 Tage: ${formatCurrency(data.revenue_7d_cents)}`}
          color="amber"
          tid="kpi-revenue-today"
        />
        <KpiCard
          icon={Gamepad2}
          label="Sessions heute"
          value={data.sessions_today}
          sub={`7 Tage: ${data.sessions_7d}`}
          color="blue"
          tid="kpi-sessions"
        />
        <KpiCard
          icon={Zap}
          label="Spiele heute"
          value={data.games_today}
          sub={`7 Tage: ${data.games_7d}`}
          color="purple"
          tid="kpi-games"
        />
      </div>

      {licensePortfolio && (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 overflow-hidden" data-testid="dashboard-license-summary">
          <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-950/40 flex items-start justify-between gap-3 flex-wrap">
            <div>
              <div className="flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-indigo-400" />
                <h2 className="text-sm font-semibold text-white">Commercial Readiness</h2>
                <ReadinessBadge bucket={(licenseCounts.urgent || 0) > 0 ? 'urgent' : (licenseCounts.attention || 0) > 0 ? 'attention' : (licenseCounts.watch || 0) > 0 ? 'watch' : 'healthy'} />
              </div>
              <p className="text-xs text-zinc-500 mt-1">Gleiche Lizenzlogik wie im Portfolio — direkt aus dem Dashboard in die Drill-ins springen.</p>
            </div>
            <button
              onClick={openLicenses}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-500/10 px-3 py-1.5 text-sm text-indigo-300 hover:bg-indigo-500/20"
              data-testid="dashboard-open-licenses"
            >
              Lizenzportfolio öffnen <ExternalLink className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="p-4 space-y-4">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <QueueMetricCard icon={TriangleAlert} label="Dringend" value={licenseCounts.urgent ?? 0} sub="inaktiv, blockiert oder überzogen" tone={(licenseCounts.urgent ?? 0) > 0 ? 'red' : 'zinc'} onClick={openLicenses} tid="dashboard-license-urgent" />
              <QueueMetricCard icon={Clock} label="Renewals / Grace" value={(licenseCounts.renewal_due ?? 0) + (licenseCounts.in_grace ?? 0)} sub={`${licenseCounts.renewal_due ?? 0} fällig · ${licenseCounts.in_grace ?? 0} grace`} tone={((licenseCounts.renewal_due ?? 0) + (licenseCounts.in_grace ?? 0)) > 0 ? 'amber' : 'zinc'} onClick={openLicenses} tid="dashboard-license-renewals" />
              <QueueMetricCard icon={Sparkles} label="Aktivierungslücken" value={licenseCounts.activation_gap ?? 0} sub="verkauft, aber noch nicht live" tone={(licenseCounts.activation_gap ?? 0) > 0 ? 'blue' : 'zinc'} onClick={openLicenses} tid="dashboard-license-gaps" />
              <QueueMetricCard icon={Gauge} label="Kapazitätsdruck" value={licenseCounts.full_or_over_capacity ?? 0} sub={`${licenseCounts.near_capacity ?? 0} fast/voll`} tone={((licenseCounts.full_or_over_capacity ?? 0) + (licenseCounts.near_capacity ?? 0)) > 0 ? 'amber' : 'zinc'} onClick={openLicenses} tid="dashboard-license-capacity" />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <LicenseFocusList
                title="Jetzt eskalieren"
                hint="Die kritischsten Lizenzen zuerst."
                items={licenseFocus.urgent || []}
                empty="Keine akuten Lizenzblocker im Scope."
                onOpenLicense={openLicense}
                accent="red"
              />
              <LicenseFocusList
                title="Renewal & Aktivierung"
                hint="Die naechsten kommerziellen Hebel."
                items={[...(licenseFocus.renewals || []), ...(licenseFocus.activation_gaps || [])].slice(0, 6)}
                empty="Kein unmittelbarer Renewal- oder Aktivierungsdruck."
                onOpenLicense={openLicense}
                accent="amber"
              />
            </div>
          </div>
        </div>
      )}

      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 overflow-hidden" data-testid="dashboard-remote-actions-summary">
        <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-950/40 flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="flex items-center gap-2">
              <Workflow className="w-4 h-4 text-indigo-400" />
              <h2 className="text-sm font-semibold text-white">Remote Action Queue</h2>
              {needsAttention > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-300">
                  <ShieldAlert className="w-3 h-3" /> {needsAttention} Signale
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-500 mt-1">Erste Operator-Surface für Review-, Delivery- und Incident-Druck</p>
          </div>
          <button
            onClick={() => openRemoteActions()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-500/10 px-3 py-1.5 text-sm text-indigo-300 hover:bg-indigo-500/20"
            data-testid="dashboard-open-remote-actions"
          >
            Remote Actions öffnen <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="p-4 grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-4">
          <div className="space-y-4">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <QueueMetricCard
                icon={Clock}
                label="Pending Review"
                value={queueSummary.pending_approval ?? 0}
                sub={canReviewRemoteActions ? 'sofort prüfbar' : 'Review erforderlich'}
                tone={(queueSummary.pending_approval ?? 0) > 0 ? 'amber' : 'zinc'}
                onClick={() => openRemoteActions({ approval_state: 'pending' })}
                tid="dashboard-ra-pending-review"
              />
              <QueueMetricCard
                icon={Send}
                label="Pending Delivery"
                value={queueSummary.pending_delivery ?? 0}
                sub="freigegeben, wartet auf Gerät"
                tone={(queueSummary.pending_delivery ?? 0) > 0 ? 'blue' : 'zinc'}
                onClick={() => openRemoteActions({ request_state: 'delivered' })}
                tid="dashboard-ra-pending-delivery"
              />
              <QueueMetricCard
                icon={AlertTriangle}
                label="Blockiert"
                value={(queueSummary.expired ?? 0) + (queueSummary.refused ?? 0) + (queueSummary.failed ?? 0)}
                sub={`${queueSummary.expired ?? 0} expired · ${queueSummary.failed ?? 0} failed`}
                tone={(queueSummary.expired ?? 0) + (queueSummary.refused ?? 0) + (queueSummary.failed ?? 0) > 0 ? 'red' : 'zinc'}
                onClick={() => openRemoteActions({ sort: 'state_priority' })}
                tid="dashboard-ra-triage"
              />
              <QueueMetricCard
                icon={Activity}
                label="Abgeschlossen"
                value={queueSummary.completed ?? 0}
                sub={`${queueSummary.succeeded ?? 0} erfolgreich`}
                tone="emerald"
                onClick={() => openRemoteActions({ request_state: 'completed' })}
                tid="dashboard-ra-completed"
              />
            </div>

            {recentRemoteActions.length > 0 && (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 overflow-hidden">
                <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
                  <p className="text-sm font-medium text-white">Neueste Queue-Bewegungen</p>
                  <button
                    onClick={() => openRemoteActions({ sort: 'issued_desc' })}
                    className="text-xs text-zinc-500 hover:text-white"
                  >
                    Verlauf öffnen
                  </button>
                </div>
                <div className="divide-y divide-zinc-800/50">
                  {recentRemoteActions.slice(0, 4).map((item) => (
                    <button
                      key={item.id}
                      onClick={() => openRemoteActions({ device_id: item.device_id })}
                      className="w-full text-left px-4 py-3 hover:bg-zinc-900/40 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm text-zinc-100 font-medium">{item.action_type}</p>
                          <p className="text-xs text-zinc-500 mt-1">{item.scope?.device_name || item.device_id?.slice(0, 8) || 'Gerät'} · {item.scope?.location_name || 'ohne Standort'}</p>
                        </div>
                        <div className="text-right">
                          <StateBadge item={item} />
                          <p className="text-xs text-zinc-600 mt-1">{timeAgo(item.issued_at)}</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-white">Operator-Empfehlung</p>
              <span className="text-xs text-zinc-500">Priorisiert</span>
            </div>
            {(queueSummary.pending_approval ?? 0) > 0 ? (
              <ActionSuggestion
                title="Review Queue zuerst leeren"
                text={`${queueSummary.pending_approval} Aktion(en) warten auf manuelle Freigabe. Das ist der direkteste Bottleneck.`}
                cta="Zu Pending Review"
                onClick={() => openRemoteActions({ approval_state: 'pending', sort: 'state_priority' })}
              />
            ) : (queueSummary.pending_delivery ?? 0) > 0 ? (
              <ActionSuggestion
                title="Delivery-Stau prüfen"
                text={`${queueSummary.pending_delivery} Aktion(en) sind freigegeben, aber noch nicht am Gerät angekommen.`}
                cta="Zu Pending Delivery"
                onClick={() => openRemoteActions({ request_state: 'delivered' })}
              />
            ) : needsAttention > 0 ? (
              <ActionSuggestion
                title="Warnungen & blockierte Aktionen sichten"
                text="Gerätewarnungen oder expirte/refused Actions sind vorhanden. Ein schneller Triage-Pass lohnt sich." 
                cta="Triage öffnen"
                onClick={() => openRemoteActions({ sort: 'state_priority' })}
              />
            ) : (
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
                <p className="text-sm font-medium text-emerald-300">Queue unter Kontrolle</p>
                <p className="text-xs text-emerald-200/70 mt-1">Keine offenen Reviews und kein sichtbarer Remote-Action-Druck im aktuellen Scope.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {data.warnings?.length > 0 && (
        <div data-testid="warnings-section">
          <div className="flex items-center gap-2 mb-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-semibold text-white">Handlungsbedarf ({data.warnings.length})</h2>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
            {data.warnings.slice(0, 8).map((w, i) => (
              <div key={i} className={`rounded-lg border px-3.5 py-2.5 flex items-start gap-2.5 text-sm ${
                w.type === 'error' ? 'border-red-500/20 bg-red-500/5 text-red-400' :
                w.type === 'offline' ? 'border-amber-500/20 bg-amber-500/5 text-amber-400' :
                'border-zinc-700 bg-zinc-800/50 text-zinc-400'
              }`}>
                {w.type === 'error' ? <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" /> :
                 w.type === 'offline' ? <WifiOff className="w-4 h-4 flex-shrink-0 mt-0.5" /> :
                 <Clock className="w-4 h-4 flex-shrink-0 mt-0.5" />}
                <div className="flex-1">
                  <div>
                    <span className="font-medium">{w.device}</span>
                    <span className="opacity-70 ml-1.5">— {w.message}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.devices?.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-white mb-2.5">Geräte-Status</h2>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm" data-testid="device-health-table">
              <thead>
                <tr className="bg-zinc-900/50 text-zinc-500 text-left text-xs uppercase tracking-wider">
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Gerät</th>
                  <th className="px-4 py-2.5 font-medium">Version</th>
                  <th className="px-4 py-2.5 font-medium">Letzter Heartbeat</th>
                  <th className="px-4 py-2.5 font-medium">Letzte Aktivität</th>
                  <th className="px-4 py-2.5 font-medium">Letzter Sync</th>
                  <th className="px-4 py-2.5 font-medium">Fehler</th>
                  <th className="px-4 py-2.5 font-medium text-right">Remote Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {data.devices.map(d => (
                  <tr key={d.id} className="text-zinc-300 hover:bg-zinc-900/30 transition-colors">
                    <td className="px-4 py-2.5">
                      {d.online
                        ? <span className="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-medium"><span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> Online</span>
                        : <span className="inline-flex items-center gap-1.5 text-zinc-500 text-xs font-medium"><span className="w-2 h-2 rounded-full bg-zinc-600" /> Offline</span>
                      }
                    </td>
                    <td className="px-4 py-2.5 font-medium">{d.device_name}</td>
                    <td className="px-4 py-2.5 text-xs font-mono text-zinc-400">{d.reported_version || '—'}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400">{timeAgo(d.last_heartbeat_at)}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400">{timeAgo(d.last_activity_at)}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400">{timeAgo(d.last_sync_at)}</td>
                    <td className="px-4 py-2.5">
                      {d.last_error
                        ? <span className="text-xs text-red-400 truncate max-w-[200px] inline-block" title={d.last_error}>{d.last_error.slice(0, 50)}</span>
                        : <span className="text-xs text-zinc-600">—</span>
                      }
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => openRemoteActions({ device_id: d.id })}
                        className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-indigo-300 hover:bg-indigo-500/10"
                      >
                        Queue <ExternalLink className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(!data.warnings || data.warnings.length === 0) && data.devices_total > 0 && (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center" data-testid="all-ok">
          <Activity className="w-6 h-6 text-emerald-400 mx-auto mb-1" />
          <p className="text-emerald-400 font-medium text-sm">Alle Systeme laufen normal</p>
        </div>
      )}

      {data.devices_total === 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center" data-testid="no-devices">
          <Monitor className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
          <p className="text-zinc-400 font-medium text-sm">Keine Geräte im aktuellen Scope</p>
          <p className="text-zinc-600 text-xs mt-1">Wähle einen Kunden / Standort oder registriere neue Geräte</p>
        </div>
      )}
    </div>
  );
}

function LicenseFocusList({ title, hint, items, empty, onOpenLicense, accent = 'zinc' }) {
  const tones = {
    red: 'border-red-500/20 bg-red-500/5',
    amber: 'border-amber-500/20 bg-amber-500/5',
    zinc: 'border-zinc-800 bg-zinc-950/30',
  };
  return (
    <div className={`rounded-xl border p-4 ${tones[accent] || tones.zinc}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-white">{title}</p>
          <p className="mt-1 text-xs text-zinc-500">{hint}</p>
        </div>
        <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-zinc-400">{items.length}</span>
      </div>
      <div className="mt-3 space-y-2">
        {items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-800 px-3 py-4 text-sm text-zinc-500">{empty}</div>
        ) : items.map((item) => (
          <button key={item.license_id} onClick={() => onOpenLicense(item.license_id)} className="w-full rounded-xl border border-zinc-800 bg-zinc-950/70 px-3 py-3 text-left hover:border-zinc-700 transition-colors">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-white">{item.plan_type || 'Lizenz'} <span className="text-zinc-500 font-mono text-xs">{item.license_id.slice(0, 8)}</span></p>
                <p className="mt-1 text-xs text-zinc-400">{item.primary_message}</p>
              </div>
              <ArrowRight className="w-4 h-4 text-zinc-600" />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, sub, color, tid }) {
  const colorMap = {
    emerald: 'border-emerald-500/20 text-emerald-400',
    amber: 'border-amber-500/20 text-amber-400',
    blue: 'border-blue-500/20 text-blue-400',
    purple: 'border-purple-500/20 text-purple-400',
    zinc: 'border-zinc-700 text-zinc-400',
    red: 'border-red-500/20 text-red-400',
  };
  return (
    <div className={`rounded-xl border bg-zinc-900 p-4 ${colorMap[color] || colorMap.zinc}`} data-testid={tid}>
      <div className="flex items-center justify-between mb-1.5">
        <Icon className="w-4.5 h-4.5 opacity-80" />
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs opacity-70 mt-0.5">{label}</p>
      {sub && <p className="text-xs opacity-50 mt-0.5">{sub}</p>}
    </div>
  );
}

function QueueMetricCard({ icon: Icon, label, value, sub, tone, onClick, tid }) {
  const tones = {
    zinc: 'border-zinc-800 text-zinc-400 hover:border-zinc-700',
    amber: 'border-amber-500/20 text-amber-400 hover:border-amber-500/40',
    blue: 'border-blue-500/20 text-blue-400 hover:border-blue-500/40',
    red: 'border-red-500/20 text-red-400 hover:border-red-500/40',
    emerald: 'border-emerald-500/20 text-emerald-400 hover:border-emerald-500/40',
  };
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border bg-zinc-900/70 p-4 text-left transition-colors ${tones[tone] || tones.zinc}`}
      data-testid={tid}
    >
      <div className="flex items-center justify-between mb-1.5">
        <Icon className="w-4 h-4 opacity-80" />
        <ExternalLink className="w-3.5 h-3.5 opacity-50" />
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs opacity-70 mt-0.5">{label}</p>
      <p className="text-xs opacity-50 mt-0.5">{sub}</p>
    </button>
  );
}

function ActionSuggestion({ title, text, cta, onClick }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-3">
      <p className="text-sm font-medium text-white">{title}</p>
      <p className="text-xs text-zinc-500 mt-1">{text}</p>
      <button onClick={onClick} className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 hover:bg-zinc-700">
        {cta} <ExternalLink className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function StateBadge({ item }) {
  const state = String(item?.request_state || '').toLowerCase();
  const approval = String(item?.approval_state || '').toLowerCase();
  const base = 'inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium';
  if (approval === 'pending' || state === 'pending_review') return <span className={`${base} border-amber-500/20 bg-amber-500/10 text-amber-300`}>Pending Review</span>;
  if (state === 'delivered') return <span className={`${base} border-blue-500/20 bg-blue-500/10 text-blue-300`}>Pending Delivery</span>;
  if (state === 'completed') return <span className={`${base} border-emerald-500/20 bg-emerald-500/10 text-emerald-300`}>Completed</span>;
  if (state === 'refused' || approval === 'refused') return <span className={`${base} border-red-500/20 bg-red-500/10 text-red-300`}>Refused</span>;
  if (state === 'expired') return <span className={`${base} border-orange-500/20 bg-orange-500/10 text-orange-300`}>Expired</span>;
  return <span className={`${base} border-zinc-700 bg-zinc-800 text-zinc-300`}>{item?.request_state || 'unknown'}</span>;
}

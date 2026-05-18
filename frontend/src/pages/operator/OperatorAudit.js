import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useCentralData } from '../../hooks/useCentralData';
import { ScrollText, RefreshCw, ExternalLink, Radar, Workflow, ShieldCheck, Clock3 } from 'lucide-react';
import { ProductPageHeader, ProductSection, ProductStatCard, SurfaceBadge } from '../../components/shell/ProductShell';
import { ProductPageState } from '../../components/shell/ProductDataDisplay';
import { ProductDetailCard, ProductInlineActions } from '../../components/shell/ProductDetail';

const ACTION_COLORS = {
  SYNC_OK: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  SYNC_NO_LICENSE: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  SYNC_BLOCKED: 'text-red-400 bg-red-500/10 border-red-500/20',
  DEVICE_REGISTERED: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  DEVICE_REGISTRATION_FAILED: 'text-red-400 bg-red-500/10 border-red-500/20',
  DEVICE_CREATED: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  DEVICE_STATUS_CHANGED: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  REG_TOKEN_CREATED: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  REG_TOKEN_USED: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
  REG_TOKEN_REVOKED: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
  USER_CREATED: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  USER_UPDATED: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20',
  CUSTOMER_CREATED: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  CUSTOMER_STATUS_CHANGED: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  LOCATION_CREATED: 'text-teal-400 bg-teal-500/10 border-teal-500/20',
  LOCATION_UPDATED: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20',
  LICENSE_CREATED: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  LICENSE_UPDATED: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20',
  remote_action_requested: 'text-amber-300 bg-amber-500/10 border-amber-500/20',
  remote_action_review_approved: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20',
  remote_action_review_refused: 'text-red-300 bg-red-500/10 border-red-500/20',
  remote_action_finalized: 'text-blue-300 bg-blue-500/10 border-blue-500/20',
  remote_action_auto_finalized: 'text-orange-300 bg-orange-500/10 border-orange-500/20',
};

const ACTION_LABELS = {
  SYNC_OK: 'Sync erfolgreich',
  SYNC_NO_LICENSE: 'Keine Lizenz',
  SYNC_BLOCKED: 'Sync blockiert',
  DEVICE_REGISTERED: 'Gerät registriert',
  DEVICE_REGISTRATION_FAILED: 'Registrierung fehlgeschlagen',
  DEVICE_REGISTERED_BIND_CONFLICT: 'Binding-Konflikt',
  DEVICE_CREATED: 'Gerät erstellt',
  DEVICE_STATUS_CHANGED: 'Gerätestatus geändert',
  REG_TOKEN_CREATED: 'Token erstellt',
  REG_TOKEN_USED: 'Token verwendet',
  REG_TOKEN_REVOKED: 'Token widerrufen',
  USER_CREATED: 'Benutzer erstellt',
  USER_UPDATED: 'Benutzer aktualisiert',
  CUSTOMER_CREATED: 'Kunde erstellt',
  CUSTOMER_STATUS_CHANGED: 'Kundenstatus geändert',
  LOCATION_CREATED: 'Standort erstellt',
  LOCATION_UPDATED: 'Standort aktualisiert',
  LICENSE_CREATED: 'Lizenz erstellt',
  LICENSE_UPDATED: 'Lizenz aktualisiert',
  remote_action_requested: 'Remote Action angefordert',
  remote_action_review_approved: 'Remote Action freigegeben',
  remote_action_review_refused: 'Remote Action abgelehnt',
  remote_action_finalized: 'Remote Action finalisiert',
  remote_action_auto_finalized: 'Remote Action automatisch finalisiert',
};

function formatTime(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return `${d.toLocaleDateString('de-DE')} ${d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}`;
}

function compactJson(value) {
  if (!value) return '—';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function OperatorAudit() {
  const [searchParams, setSearchParams] = useSearchParams();
  const endpoint = useMemo(() => {
    const params = new URLSearchParams(searchParams);
    if (!params.get('limit')) params.set('limit', '100');
    return `licensing/audit-log?${params.toString()}`;
  }, [searchParams]);
  const { data: entries, loading, error, refetch } = useCentralData(endpoint);

  const filterChips = [
    ['action_prefix', searchParams.get('action_prefix')],
    ['action', searchParams.get('action')],
    ['actor', searchParams.get('actor')],
    ['device_id', searchParams.get('device_id')],
    ['location_id', searchParams.get('location_id')],
    ['customer_id', searchParams.get('customer_id')],
    ['license_id', searchParams.get('license_id')],
  ].filter(([, value]) => value);

  const clearFilters = () => setSearchParams(new URLSearchParams());
  const list = entries || [];
  const remoteActions = list.filter((entry) => String(entry.action || '').startsWith('remote_action')).length;
  const userChanges = list.filter((entry) => String(entry.action || '').startsWith('USER_')).length;
  const recentActors = new Set(list.map((entry) => entry.actor).filter(Boolean)).size;

  if (loading) {
    return <ProductPageState kind="loading" title="Audit-Log wird geladen" description="Aktivität, Actor-Trail und Scope-Drilldowns werden zusammengezogen." data-testid="operator-audit-loading" />;
  }

  if (error) {
    return <ProductPageState kind="error" title="Audit-Log konnte nicht geladen werden" description={error} data-testid="audit-error" />;
  }

  return (
    <div className="space-y-6" data-testid="operator-audit">
      <ProductPageHeader
        eyebrow="Operator control surface"
        title="Aktivität"
        badge={<SurfaceBadge tone="amber">Audit trail</SurfaceBadge>}
        description="Remote Actions, Scope-Wechsel und Admin-Eingriffe jetzt in einer einheitlichen Audit-Surface statt in einer losen Eventliste."
        actions={
          <div className="flex items-center gap-2">
            {filterChips.length > 0 && (
              <button onClick={clearFilters} className="rounded-lg bg-zinc-800 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-700">Filter zurücksetzen</button>
            )}
            <button onClick={refetch} className="rounded-lg bg-zinc-800 p-2 text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-white" data-testid="audit-refresh">
              <RefreshCw className="w-5 h-5" />
            </button>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ProductStatCard icon={ScrollText} label="Einträge" value={list.length} hint="Aktueller Audit-Slice" data-testid="operator-audit-total" />
        <ProductStatCard icon={Workflow} label="Remote Actions" value={remoteActions} hint="Mit Review / Delivery Bezug" tone={remoteActions > 0 ? 'amber' : 'default'} data-testid="operator-audit-remote-actions" />
        <ProductStatCard icon={ShieldCheck} label="User Changes" value={userChanges} hint="Benutzer- und Zugriffsänderungen" tone={userChanges > 0 ? 'blue' : 'default'} data-testid="operator-audit-user-changes" />
        <ProductStatCard icon={Radar} label="Actors" value={recentActors} hint="Distinct Auslöser im Slice" tone="purple" data-testid="operator-audit-actors" />
      </div>

      {filterChips.length > 0 && (
        <ProductDetailCard title="Aktive Filter" eyebrow="Scope lock" description="Dieser Audit-Slice ist aktuell bewusst gefiltert.">
          <div className="flex flex-wrap items-center gap-2">
            {filterChips.map(([label, value]) => (
              <span key={label} className="rounded-full border border-indigo-400/20 bg-indigo-500/10 px-2.5 py-1 text-xs text-indigo-100">{label}: {value}</span>
            ))}
          </div>
        </ProductDetailCard>
      )}

      <ProductSection
        eyebrow="Operational timeline"
        title="Audit-Feed"
        description="Operator-taugliche Timeline mit Scope-Kontext und aufklappbaren Detailblöcken."
        actions={<ProductInlineActions mode="operator" items={[{ label: 'Aktualisieren', onClick: refetch, className: 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' }]} />}
      >
        <div className="space-y-3 p-4">
          {list.length === 0 ? (
            <ProductPageState kind="empty" compact title="Keine Aktivitäten vorhanden" description="Sobald Audit-Events im aktuellen Scope vorhanden sind, erscheinen sie hier in chronologischer Form." data-testid="audit-empty" />
          ) : list.map((e) => {
            const color = ACTION_COLORS[e.action] || 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20';
            const label = ACTION_LABELS[e.action] || e.action;
            const scope = e.scope || {};

            return (
              <details key={e.id} className="group rounded-3xl border border-zinc-800 bg-zinc-900/50 px-4 py-4" data-testid={`audit-${e.id}`}>
                <summary className="flex cursor-pointer list-none items-start gap-3">
                  <span className={`mt-0.5 inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>{label}</span>
                  <div className="min-w-0 flex-1">
                    <p className="break-words text-sm text-zinc-300">{e.message || '—'}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-3">
                      {e.actor && <span className="text-xs text-indigo-400/70">von {e.actor}</span>}
                      <span className="inline-flex items-center gap-1 text-xs text-zinc-600"><Clock3 className="h-3 w-3" /> {formatTime(e.timestamp)}</span>
                      {scope.device_name && <span className="text-xs text-zinc-500">Gerät {scope.device_name}</span>}
                      {scope.location_name && <span className="text-xs text-zinc-500">Standort {scope.location_name}</span>}
                    </div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-zinc-600 transition-transform group-open:rotate-45" />
                </summary>

                <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 text-sm">
                  <DetailField label="Action" value={e.action} mono />
                  <DetailField label="Actor" value={e.actor || '—'} />
                  <DetailField label="Device" value={scope.device_name || e.device_id || '—'} mono={!scope.device_name} />
                  <DetailField label="License" value={scope.license_id || e.license_id || '—'} mono />
                  <DetailField label="Location" value={scope.location_name || '—'} />
                  <DetailField label="Customer" value={scope.customer_name || '—'} />
                </div>

                {e.details && (
                  <div className="mt-4 rounded-2xl border border-zinc-800 bg-black/30 p-4">
                    <p className="mb-2 text-xs uppercase tracking-wider text-zinc-500">Details</p>
                    <pre className="whitespace-pre-wrap break-words text-xs text-zinc-300">{compactJson(e.details)}</pre>
                  </div>
                )}
              </details>
            );
          })}
        </div>
      </ProductSection>
    </div>
  );
}

function DetailField({ label, value, mono = false }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2.5">
      <p className="text-xs uppercase tracking-wider text-zinc-500">{label}</p>
      <p className={`mt-1 break-all text-sm text-zinc-200 ${mono ? 'font-mono text-xs' : ''}`}>{value || '—'}</p>
    </div>
  );
}

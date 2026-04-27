import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useCentralData } from '../../hooks/useCentralData';
import { ScrollText, RefreshCw, AlertTriangle, ExternalLink } from 'lucide-react';

const ACTION_COLORS = {
  SYNC_OK: 'text-emerald-400 bg-emerald-500/10',
  SYNC_NO_LICENSE: 'text-amber-400 bg-amber-500/10',
  SYNC_BLOCKED: 'text-red-400 bg-red-500/10',
  DEVICE_REGISTERED: 'text-blue-400 bg-blue-500/10',
  DEVICE_REGISTRATION_FAILED: 'text-red-400 bg-red-500/10',
  DEVICE_CREATED: 'text-blue-400 bg-blue-500/10',
  DEVICE_STATUS_CHANGED: 'text-amber-400 bg-amber-500/10',
  REG_TOKEN_CREATED: 'text-cyan-400 bg-cyan-500/10',
  REG_TOKEN_USED: 'text-indigo-400 bg-indigo-500/10',
  REG_TOKEN_REVOKED: 'text-orange-400 bg-orange-500/10',
  USER_CREATED: 'text-blue-400 bg-blue-500/10',
  USER_UPDATED: 'text-zinc-400 bg-zinc-500/10',
  CUSTOMER_CREATED: 'text-purple-400 bg-purple-500/10',
  CUSTOMER_STATUS_CHANGED: 'text-amber-400 bg-amber-500/10',
  LOCATION_CREATED: 'text-teal-400 bg-teal-500/10',
  LOCATION_UPDATED: 'text-zinc-400 bg-zinc-500/10',
  LICENSE_CREATED: 'text-emerald-400 bg-emerald-500/10',
  LICENSE_UPDATED: 'text-zinc-400 bg-zinc-500/10',
  remote_action_requested: 'text-amber-300 bg-amber-500/10',
  remote_action_review_approved: 'text-emerald-300 bg-emerald-500/10',
  remote_action_review_refused: 'text-red-300 bg-red-500/10',
  remote_action_finalized: 'text-blue-300 bg-blue-500/10',
  remote_action_auto_finalized: 'text-orange-300 bg-orange-500/10',
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-red-400" data-testid="audit-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
        <p className="font-medium">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="operator-audit">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white">Aktivität</h1>
          <p className="text-sm text-zinc-500 mt-1">Letzte Ereignisse mit Audit-Drilldown</p>
        </div>
        <div className="flex items-center gap-2">
          {filterChips.length > 0 && (
            <button onClick={clearFilters} className="rounded-lg bg-zinc-800 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-700">Filter zurücksetzen</button>
          )}
          <button onClick={refetch} className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors" data-testid="audit-refresh">
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {filterChips.length > 0 && (
        <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4">
          <p className="text-xs uppercase tracking-wider text-indigo-300">Aktive Filter</p>
          <div className="flex items-center gap-2 flex-wrap mt-2">
            {filterChips.map(([label, value]) => (
              <span key={label} className="rounded-full border border-indigo-400/20 bg-indigo-500/10 px-2.5 py-1 text-xs text-indigo-100">{label}: {value}</span>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-3">
        {(!entries || entries.length === 0) && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center text-zinc-500" data-testid="audit-empty">
            <ScrollText className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p>Keine Aktivitäten vorhanden</p>
          </div>
        )}

        {entries?.map((e) => {
          const color = ACTION_COLORS[e.action] || 'text-zinc-400 bg-zinc-500/10';
          const label = ACTION_LABELS[e.action] || e.action;
          const scope = e.scope || {};

          return (
            <details key={e.id} className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 group" data-testid={`audit-${e.id}`}>
              <summary className="list-none cursor-pointer flex items-start gap-3">
                <span className={`text-xs px-2 py-0.5 rounded font-medium whitespace-nowrap mt-0.5 ${color}`}>{label}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-zinc-300 break-words">{e.message || '—'}</p>
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    {e.actor && <span className="text-xs text-indigo-400/70">von {e.actor}</span>}
                    <span className="text-xs text-zinc-600">{formatTime(e.timestamp)}</span>
                    {scope.device_name && <span className="text-xs text-zinc-500">Gerät {scope.device_name}</span>}
                    {scope.location_name && <span className="text-xs text-zinc-500">Standort {scope.location_name}</span>}
                  </div>
                </div>
                <ExternalLink className="w-4 h-4 text-zinc-600 group-open:rotate-45 transition-transform" />
              </summary>

              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <DetailField label="Action" value={e.action} mono />
                <DetailField label="Actor" value={e.actor || '—'} />
                <DetailField label="Device" value={scope.device_name || e.device_id || '—'} mono={!scope.device_name} />
                <DetailField label="License" value={scope.license_id || e.license_id || '—'} mono />
                <DetailField label="Location" value={scope.location_name || '—'} />
                <DetailField label="Customer" value={scope.customer_name || '—'} />
              </div>

              {e.details && (
                <div className="mt-4 rounded-xl border border-zinc-800 bg-black/30 p-4">
                  <p className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Details</p>
                  <pre className="text-xs text-zinc-300 whitespace-pre-wrap break-words">{compactJson(e.details)}</pre>
                </div>
              )}
            </details>
          );
        })}
      </div>
    </div>
  );
}

function DetailField({ label, value, mono = false }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2.5">
      <p className="text-xs uppercase tracking-wider text-zinc-500">{label}</p>
      <p className={`mt-1 text-sm text-zinc-200 break-all ${mono ? 'font-mono text-xs' : ''}`}>{value || '—'}</p>
    </div>
  );
}

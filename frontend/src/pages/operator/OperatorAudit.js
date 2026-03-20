import { useCentralData } from '../../hooks/useCentralData';
import { ScrollText, RefreshCw, AlertTriangle } from 'lucide-react';

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
};

function formatTime(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return `${d.toLocaleDateString('de-DE')} ${d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}`;
}

export default function OperatorAudit() {
  const { data: entries, loading, error, refetch } = useCentralData('licensing/audit-log?limit=100');

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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Aktivität</h1>
          <p className="text-sm text-zinc-500 mt-1">Letzte Ereignisse</p>
        </div>
        <button onClick={refetch} className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors" data-testid="audit-refresh">
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      <div className="space-y-2">
        {(!entries || entries.length === 0) && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center text-zinc-500" data-testid="audit-empty">
            <ScrollText className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p>Keine Aktivitäten vorhanden</p>
          </div>
        )}

        {entries?.map((e) => {
          const color = ACTION_COLORS[e.action] || 'text-zinc-400 bg-zinc-500/10';
          const label = ACTION_LABELS[e.action] || e.action;

          return (
            <div key={e.id} className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3 flex items-start gap-3" data-testid={`audit-${e.id}`}>
              <span className={`text-xs px-2 py-0.5 rounded font-medium whitespace-nowrap mt-0.5 ${color}`}>
                {label}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-zinc-300 break-words">{e.message || '—'}</p>
                <div className="flex items-center gap-3 mt-1">
                  {e.actor && <span className="text-xs text-indigo-400/70">von {e.actor}</span>}
                  <span className="text-xs text-zinc-600">{formatTime(e.timestamp)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

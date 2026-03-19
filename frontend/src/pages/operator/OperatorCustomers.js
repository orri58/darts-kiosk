import { useCentralData } from '../../hooks/useCentralData';
import { Building2, RefreshCw, AlertTriangle } from 'lucide-react';

export default function OperatorCustomers() {
  const { data: customers, loading, error, refetch } = useCentralData('licensing/customers');

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-red-400" data-testid="customers-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
        <p className="font-medium">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="operator-customers">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Kunden</h1>
          <p className="text-sm text-zinc-500 mt-1">{customers?.length || 0} Kunden</p>
        </div>
        <button onClick={refetch} className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors" data-testid="customers-refresh">
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      <div className="space-y-3">
        {customers?.length === 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center text-zinc-500" data-testid="customers-empty">
            <Building2 className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p>Keine Kunden vorhanden</p>
          </div>
        )}

        {customers?.map((c) => {
          const statusColor = c.status === 'active' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
            : c.status === 'blocked' ? 'text-red-400 bg-red-500/10 border-red-500/20'
            : 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20';
          const statusLabel = c.status === 'active' ? 'Aktiv' : c.status === 'blocked' ? 'Gesperrt' : 'Inaktiv';

          return (
            <div key={c.id} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 hover:border-zinc-700 transition-colors" data-testid={`customer-${c.id}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
                    <Building2 className="w-5 h-5 text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="text-white font-medium text-sm">{c.name}</h3>
                    <p className="text-xs text-zinc-500">{c.contact_email || 'Keine E-Mail'}</p>
                  </div>
                </div>
                <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${statusColor}`}>
                  {statusLabel}
                </span>
              </div>
              <div className="mt-3 text-xs text-zinc-500">
                <span className="text-zinc-600">Erstellt: </span>
                <span className="text-zinc-300">{c.created_at ? new Date(c.created_at).toLocaleDateString('de-DE') : '—'}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

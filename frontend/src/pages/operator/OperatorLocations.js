import { useCentralData } from '../../hooks/useCentralData';
import { MapPin, RefreshCw, AlertTriangle } from 'lucide-react';

export default function OperatorLocations() {
  const { data: locations, loading, error, refetch } = useCentralData('licensing/locations');
  const { data: customers } = useCentralData('licensing/customers');

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-red-400" data-testid="locations-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
        <p className="font-medium">{error}</p>
      </div>
    );
  }

  const customerMap = {};
  customers?.forEach(c => { customerMap[c.id] = c; });

  return (
    <div className="space-y-6" data-testid="operator-locations">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Standorte</h1>
          <p className="text-sm text-zinc-500 mt-1">{locations?.length || 0} Standorte</p>
        </div>
        <button onClick={refetch} className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors" data-testid="locations-refresh">
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      <div className="space-y-3">
        {locations?.length === 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center text-zinc-500" data-testid="locations-empty">
            <MapPin className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p>Keine Standorte vorhanden</p>
          </div>
        )}

        {locations?.map((loc) => {
          const cust = customerMap[loc.customer_id];
          const statusColor = loc.status === 'active' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
            : 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20';
          const statusLabel = loc.status === 'active' ? 'Aktiv' : 'Inaktiv';

          return (
            <div key={loc.id} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 hover:border-zinc-700 transition-colors" data-testid={`location-${loc.id}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-teal-500/10 flex items-center justify-center">
                    <MapPin className="w-5 h-5 text-teal-400" />
                  </div>
                  <div>
                    <h3 className="text-white font-medium text-sm">{loc.name}</h3>
                    <p className="text-xs text-zinc-500">{cust?.name || 'Unbekannt'}{loc.address ? ` — ${loc.address}` : ''}</p>
                  </div>
                </div>
                <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${statusColor}`}>
                  {statusLabel}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

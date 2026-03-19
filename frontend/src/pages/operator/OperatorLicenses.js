import { useCentralData } from '../../hooks/useCentralData';
import { KeyRound, CheckCircle, Clock, XCircle, AlertTriangle, RefreshCw, Ban } from 'lucide-react';

const STATUS_MAP = {
  active: { label: 'Aktiv', icon: CheckCircle, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
  grace: { label: 'Toleranzzeitraum', icon: Clock, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
  expired: { label: 'Abgelaufen', icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
  blocked: { label: 'Gesperrt', icon: Ban, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
  test: { label: 'Test', icon: KeyRound, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20' },
};

function formatDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export default function OperatorLicenses() {
  const { data: licenses, loading, error, refetch } = useCentralData('licensing/licenses');
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
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-red-400" data-testid="licenses-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
        <p className="font-medium">{error}</p>
      </div>
    );
  }

  const customerMap = {};
  customers?.forEach(c => { customerMap[c.id] = c; });

  // Group counts
  const counts = { active: 0, grace: 0, expired: 0, blocked: 0, test: 0 };
  licenses?.forEach(l => { if (counts[l.status] !== undefined) counts[l.status]++; });

  return (
    <div className="space-y-6" data-testid="operator-licenses">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Lizenzen</h1>
          <p className="text-sm text-zinc-500 mt-1">{licenses?.length || 0} Lizenzen gesamt</p>
        </div>
        <button onClick={refetch} className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors" data-testid="licenses-refresh">
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      {/* Status counts */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {Object.entries(STATUS_MAP).map(([key, cfg]) => (
          <div key={key} className={`rounded-xl border p-3 ${cfg.bg}`} data-testid={`lic-count-${key}`}>
            <div className="flex items-center gap-2">
              <cfg.icon className={`w-4 h-4 ${cfg.color}`} />
              <span className={`text-xl font-bold ${cfg.color}`}>{counts[key]}</span>
            </div>
            <p className={`text-xs mt-1 ${cfg.color} opacity-80`}>{cfg.label}</p>
          </div>
        ))}
      </div>

      {/* License List */}
      <div className="space-y-3">
        {licenses?.length === 0 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center text-zinc-500" data-testid="licenses-empty">
            <KeyRound className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p>Keine Lizenzen vorhanden</p>
          </div>
        )}

        {licenses?.map((lic) => {
          const st = STATUS_MAP[lic.status] || STATUS_MAP.expired;
          const cust = customerMap[lic.customer_id];

          return (
            <div key={lic.id} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 hover:border-zinc-700 transition-colors" data-testid={`license-${lic.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${st.bg.split(' ')[0]}`}>
                    <st.icon className={`w-5 h-5 ${st.color}`} />
                  </div>
                  <div>
                    <h3 className="text-white font-medium text-sm">{cust?.name || 'Unbekannt'}</h3>
                    <p className="text-xs text-zinc-500">Plan: {lic.plan_type || 'standard'} — Max. {lic.max_devices} Geräte</p>
                  </div>
                </div>
                <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${st.bg} ${st.color}`}>
                  {st.label}
                </span>
              </div>

              <div className="mt-3 grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs text-zinc-500">
                <div>
                  <span className="block text-zinc-600">Startdatum</span>
                  <span className="text-zinc-300">{formatDate(lic.starts_at)}</span>
                </div>
                <div>
                  <span className="block text-zinc-600">Ablaufdatum</span>
                  <span className={`${lic.status === 'expired' ? 'text-red-400' : lic.status === 'grace' ? 'text-amber-400' : 'text-zinc-300'}`}>
                    {formatDate(lic.ends_at)}
                  </span>
                </div>
                <div>
                  <span className="block text-zinc-600">Toleranz bis</span>
                  <span className="text-zinc-300">{formatDate(lic.grace_until)}</span>
                </div>
                <div>
                  <span className="block text-zinc-600">Toleranztage</span>
                  <span className="text-zinc-300">{lic.grace_days ?? '—'}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

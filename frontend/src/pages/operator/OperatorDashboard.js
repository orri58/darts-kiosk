import { useCentralData } from '../../hooks/useCentralData';
import {
  Building2, MapPin, Monitor, KeyRound,
  AlertTriangle, CheckCircle, Clock, XCircle, Wifi, WifiOff
} from 'lucide-react';

function StatCard({ icon: Icon, label, value, color, subtext, tid }) {
  return (
    <div className={`rounded-xl border p-5 ${color}`} data-testid={tid}>
      <div className="flex items-center justify-between mb-3">
        <Icon className="w-6 h-6 opacity-80" />
        <span className="text-3xl font-bold">{value}</span>
      </div>
      <p className="text-sm font-medium opacity-90">{label}</p>
      {subtext && <p className="text-xs opacity-60 mt-1">{subtext}</p>}
    </div>
  );
}

function ProblemCard({ icon: Icon, title, items, color }) {
  if (!items || items.length === 0) return null;
  return (
    <div className={`rounded-xl border p-4 ${color}`} data-testid={`problem-${title.toLowerCase().replace(/\s/g, '-')}`}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-5 h-5" />
        <h3 className="font-semibold text-sm">{title}</h3>
        <span className="ml-auto text-xs font-bold bg-white/10 px-2 py-0.5 rounded-full">{items.length}</span>
      </div>
      <div className="space-y-2">
        {items.slice(0, 5).map((item, i) => (
          <div key={i} className="text-sm opacity-90 bg-white/5 rounded-lg px-3 py-2">
            {item}
          </div>
        ))}
        {items.length > 5 && <p className="text-xs opacity-60">+ {items.length - 5} weitere</p>}
      </div>
    </div>
  );
}

export default function OperatorDashboard() {
  const { data: customers, loading: l1 } = useCentralData('licensing/customers');
  const { data: locations, loading: l2 } = useCentralData('licensing/locations');
  const { data: devices, loading: l3 } = useCentralData('licensing/devices');
  const { data: licenses, loading: l4 } = useCentralData('licensing/licenses');

  const loading = l1 || l2 || l3 || l4;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Compute stats
  const deviceCount = devices?.length || 0;
  const locationCount = locations?.length || 0;
  const customerCount = customers?.length || 0;
  const licenseCount = licenses?.length || 0;

  const activeLicenses = licenses?.filter(l => l.status === 'active') || [];
  const graceLicenses = licenses?.filter(l => l.status === 'grace') || [];
  const expiredLicenses = licenses?.filter(l => l.status === 'expired') || [];

  const onlineDevices = devices?.filter(d => {
    if (!d.last_sync_at) return false;
    const diff = Date.now() - new Date(d.last_sync_at).getTime();
    return diff < 24 * 60 * 60 * 1000; // last 24h
  }) || [];

  const offlineDevices = devices?.filter(d => {
    if (!d.last_sync_at) return true;
    const diff = Date.now() - new Date(d.last_sync_at).getTime();
    return diff >= 24 * 60 * 60 * 1000;
  }) || [];

  const mismatchDevices = devices?.filter(d => d.binding_status === 'mismatch') || [];

  // Problem lists
  const expiredProblems = expiredLicenses.map(l => {
    const c = customers?.find(c => c.id === l.customer_id);
    return `${c?.name || 'Unbekannt'} — Plan: ${l.plan_type}`;
  });

  const graceProblems = graceLicenses.map(l => {
    const c = customers?.find(c => c.id === l.customer_id);
    return `${c?.name || 'Unbekannt'} — Ablauf: ${l.ends_at ? new Date(l.ends_at).toLocaleDateString('de-DE') : '—'}`;
  });

  const offlineProblems = offlineDevices.map(d => {
    const lastSync = d.last_sync_at ? new Date(d.last_sync_at).toLocaleDateString('de-DE') : 'Nie';
    return `${d.device_name || d.id.slice(0, 8)} — Letzter Sync: ${lastSync}`;
  });

  const mismatchProblems = mismatchDevices.map(d =>
    `${d.device_name || d.id.slice(0, 8)} — Geräte-Mismatch erkannt`
  );

  const hasProblems = expiredProblems.length > 0 || graceProblems.length > 0 || offlineProblems.length > 0 || mismatchProblems.length > 0;

  return (
    <div className="space-y-8" data-testid="operator-dashboard">
      <div>
        <h1 className="text-2xl font-bold text-white">Übersicht</h1>
        <p className="text-sm text-zinc-500 mt-1">Status aller Geräte, Lizenzen und Standorte</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Building2} label="Kunden" value={customerCount} tid="stat-customers"
          color="bg-zinc-900 border-zinc-800 text-white" />
        <StatCard icon={MapPin} label="Standorte" value={locationCount} tid="stat-locations"
          color="bg-zinc-900 border-zinc-800 text-white" />
        <StatCard icon={Monitor} label="Geräte" value={deviceCount} tid="stat-devices"
          color="bg-zinc-900 border-zinc-800 text-white"
          subtext={`${onlineDevices.length} online / ${offlineDevices.length} offline`} />
        <StatCard icon={KeyRound} label="Lizenzen" value={licenseCount} tid="stat-licenses"
          color="bg-zinc-900 border-zinc-800 text-white"
          subtext={`${activeLicenses.length} aktiv`} />
      </div>

      {/* License Status Row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-emerald-400" data-testid="lic-active-count">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle className="w-5 h-5" />
            <span className="text-2xl font-bold">{activeLicenses.length}</span>
          </div>
          <p className="text-sm">Aktive Lizenzen</p>
        </div>
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-amber-400" data-testid="lic-grace-count">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-5 h-5" />
            <span className="text-2xl font-bold">{graceLicenses.length}</span>
          </div>
          <p className="text-sm">Im Toleranzzeitraum</p>
        </div>
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-red-400" data-testid="lic-expired-count">
          <div className="flex items-center gap-2 mb-1">
            <XCircle className="w-5 h-5" />
            <span className="text-2xl font-bold">{expiredLicenses.length}</span>
          </div>
          <p className="text-sm">Abgelaufen</p>
        </div>
      </div>

      {/* Problems Section */}
      {hasProblems ? (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-white">Handlungsbedarf</h2>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ProblemCard icon={XCircle} title="Abgelaufene Lizenzen" items={expiredProblems}
              color="border-red-500/20 bg-red-500/5 text-red-400" />
            <ProblemCard icon={Clock} title="Toleranzzeitraum" items={graceProblems}
              color="border-amber-500/20 bg-amber-500/5 text-amber-400" />
            <ProblemCard icon={WifiOff} title="Geräte offline" items={offlineProblems}
              color="border-zinc-600/20 bg-zinc-800/50 text-zinc-400" />
            <ProblemCard icon={AlertTriangle} title="Geräte-Mismatch" items={mismatchProblems}
              color="border-orange-500/20 bg-orange-500/5 text-orange-400" />
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6 text-center" data-testid="no-problems">
          <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
          <p className="text-emerald-400 font-medium">Alles in Ordnung</p>
          <p className="text-sm text-emerald-400/60 mt-1">Keine Probleme erkannt</p>
        </div>
      )}
    </div>
  );
}

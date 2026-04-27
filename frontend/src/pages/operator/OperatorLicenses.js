import { useState, useCallback, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useCentralAuth } from '../../context/CentralAuthContext';
import axios from 'axios';
import {
  KeyRound, Plus, CheckCircle, AlertTriangle, Ban, Shield, Clock, Archive, Filter, ChevronRight, ExternalLink,
  Gauge, Sparkles, TriangleAlert, PackageOpen, ArrowRight, BriefcaseBusiness
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';

const STATUS_CONF = {
  active: { cls: 'bg-emerald-500/10 text-emerald-400', label: 'Aktiv', icon: CheckCircle },
  grace: { cls: 'bg-amber-500/10 text-amber-400', label: 'Toleranz', icon: Clock },
  expired: { cls: 'bg-red-500/10 text-red-400', label: 'Abgelaufen', icon: AlertTriangle },
  blocked: { cls: 'bg-red-500/10 text-red-400', label: 'Gesperrt', icon: Ban },
  test: { cls: 'bg-blue-500/10 text-blue-400', label: 'Test', icon: Shield },
  deactivated: { cls: 'bg-zinc-500/10 text-zinc-400', label: 'Deaktiviert', icon: Ban },
  archived: { cls: 'bg-zinc-600/10 text-zinc-500', label: 'Archiviert', icon: Archive },
};
const STATUS_OPTIONS = [
  { value: '', label: 'Alle Status' },
  { value: 'active', label: 'Aktiv' },
  { value: 'test', label: 'Test' },
  { value: 'grace', label: 'Toleranz' },
  { value: 'expired', label: 'Abgelaufen' },
  { value: 'deactivated', label: 'Deaktiviert' },
  { value: 'archived', label: 'Archiviert' },
];

const READINESS_TONE = {
  healthy: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
  watch: 'bg-sky-500/10 text-sky-300 border-sky-500/20',
  attention: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
  urgent: 'bg-red-500/10 text-red-300 border-red-500/20',
};

const POSTURE_TONE = {
  ready: 'text-emerald-400',
  degraded: 'text-sky-300',
  review_required: 'text-amber-300',
  blocked: 'text-red-300',
};

function formatShortDate(value) {
  if (!value) return 'Unbegrenzt';
  return new Date(value).toLocaleDateString('de-DE');
}

function statusLabel(value) {
  return STATUS_CONF[value]?.label || value || '—';
}

function bucketLabel(value) {
  return {
    healthy: 'Gesund',
    watch: 'Beobachten',
    attention: 'Aktion nötig',
    urgent: 'Dringend',
  }[value] || value;
}

function capacityLabel(value) {
  return {
    unconfigured: 'Kein Limit',
    unassigned: 'Noch ungenutzt',
    available: 'Platz vorhanden',
    near_capacity: 'Fast voll',
    full: 'Voll belegt',
    over_capacity: 'Überbucht',
  }[value] || value || '—';
}

function postureLabel(value) {
  return {
    ready: 'Ready',
    degraded: 'Degraded',
    review_required: 'Review',
    blocked: 'Blocked',
  }[value] || value || '—';
}

function actionIntentLabel(action) {
  const type = action?.type;
  return {
    generate_activation_token: 'Aktivieren',
    get_activation_token: 'Token abrufen',
    renew_license: 'Renewal',
    upgrade_capacity: 'Upgrade',
    review_bound_devices: 'Geräte prüfen',
    reactivate_license: 'Reaktivieren',
    regenerate_activation_token: 'Token erneuern',
    review_archived_license: 'Archiv prüfen',
    review_contract_state: 'Status klären',
    monitor_license: 'Überblick',
  }[type] || action?.label || 'Öffnen';
}

function tokenStateLabel(value) {
  return {
    active: 'Token bereit',
    consumed: 'Token verbraucht',
    expired: 'Token abgelaufen',
    revoked: 'Token widerrufen',
    missing: 'Kein Token',
  }[value] || value || '—';
}

function tokenTone(value) {
  return {
    active: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
    consumed: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
    expired: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
    revoked: 'border-red-500/20 bg-red-500/10 text-red-300',
    missing: 'border-zinc-700 bg-zinc-800/80 text-zinc-300',
  }[value] || 'border-zinc-700 bg-zinc-800/80 text-zinc-300';
}

function TokenBadge({ summary, compact = false }) {
  const state = summary?.state;
  const expiresIn = summary?.active_expires_in_days;
  const detail = state === 'active' && expiresIn != null
    ? ` · ${expiresIn}T Restlaufzeit`
    : compact ? '' : ` · ${summary?.counts?.total || 0} gesamt`;

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${tokenTone(state)}`}>
      {tokenStateLabel(state)}{detail}
    </span>
  );
}

function StatusBadge({ status }) {
  const c = STATUS_CONF[status] || STATUS_CONF.active;
  const Icon = c.icon;
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${c.cls}`}><Icon className="w-3 h-3" />{c.label}</span>;
}

function ReadinessBadge({ readiness }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${READINESS_TONE[readiness?.action_bucket] || READINESS_TONE.watch}`}>
      <Sparkles className="w-3 h-3" /> {bucketLabel(readiness?.action_bucket)}
    </span>
  );
}

function KpiCard({ icon: Icon, label, value, hint, tone = 'zinc' }) {
  const toneCls = {
    emerald: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
    amber: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
    red: 'border-red-500/20 bg-red-500/10 text-red-300',
    blue: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
    zinc: 'border-zinc-800 bg-zinc-900/60 text-zinc-300',
  }[tone] || 'border-zinc-800 bg-zinc-900/60 text-zinc-300';

  return (
    <div className={`rounded-2xl border p-4 ${toneCls}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-current/70">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
          {hint && <p className="mt-1 text-xs text-current/75">{hint}</p>}
        </div>
        <div className="rounded-xl bg-black/20 p-2.5">
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

function FocusQueue({ title, hint, items, empty, onOpenLicense, onRunAction, accent = 'zinc' }) {
  const accentCls = {
    red: 'border-red-500/20 bg-red-500/5',
    amber: 'border-amber-500/20 bg-amber-500/5',
    blue: 'border-sky-500/20 bg-sky-500/5',
    emerald: 'border-emerald-500/20 bg-emerald-500/5',
    zinc: 'border-zinc-800 bg-zinc-900/60',
  }[accent] || 'border-zinc-800 bg-zinc-900/60';

  return (
    <div className={`rounded-2xl border p-4 ${accentCls}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{title}</p>
          <p className="mt-1 text-xs text-zinc-500">{hint}</p>
        </div>
        <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-zinc-400">{items.length}</span>
      </div>
      <div className="mt-4 space-y-2">
        {items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-800 px-3 py-4 text-sm text-zinc-500">{empty}</div>
        ) : items.map((item) => (
          <div
            key={item.license_id}
            className="rounded-xl border border-zinc-800 bg-zinc-950/70 px-3 py-3 text-left"
          >
            <button
              onClick={() => onOpenLicense(item.license_id)}
              className="w-full text-left hover:opacity-95 transition-opacity"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-white">{item.plan_type || 'Lizenz'} <span className="text-zinc-500 font-mono text-xs">{item.license_id.slice(0, 8)}</span></p>
                  <p className="mt-1 text-xs text-zinc-400">{item.primary_message}</p>
                </div>
                <ReadinessBadge readiness={item} />
              </div>
            </button>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-zinc-500">
              <span>Status: {statusLabel(item.computed_status)}</span>
              <span>Geräte: {item.device_count}/{item.max_devices || '—'}</span>
              {item.renewal_days != null && <span>Renewal: {item.renewal_days} Tage</span>}
              <span className={POSTURE_TONE[item.posture_status] || 'text-zinc-400'}>Posture: {postureLabel(item.posture_status)}</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <TokenBadge summary={item.token_summary} compact />
              {item.suggested_actions?.[0] && onRunAction && (
                <button
                  onClick={() => onRunAction(item.license_id, item.suggested_actions[0])}
                  className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 px-2.5 py-1 text-xs text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800"
                >
                  {actionIntentLabel(item.suggested_actions[0])} <ArrowRight className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function OperatorLicenses() {
  const { apiBase, authHeaders, canManage, canReviewRemoteActions } = useCentralAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [licenses, setLicenses] = useState([]);
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [createdLicenseId, setCreatedLicenseId] = useState(null);

  const fetchLicenses = useCallback(async () => {
    setLoading(true);
    try {
      const params = statusFilter ? `?status=${statusFilter}` : '';
      const [licensesRes, portfolioRes] = await Promise.all([
        axios.get(`${apiBase}/licensing/licenses${params}`, { headers: authHeaders }),
        axios.get(`${apiBase}/licensing/licenses/portfolio-summary${params}`, { headers: authHeaders }),
      ]);
      setLicenses(licensesRes.data);
      setPortfolio(portfolioRes.data);
    } catch (err) {
      toast.error('Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  }, [apiBase, authHeaders, statusFilter]);

  useEffect(() => { fetchLicenses(); }, [fetchLicenses]);

  const [form, setForm] = useState({ customer_id: '', location_id: '', plan_type: 'standard', max_devices: 1, status: 'active', notes: '' });
  const [customers, setCustomers] = useState([]);
  const [locations, setLocations] = useState([]);

  useEffect(() => {
    if (showCreate) {
      axios.get(`${apiBase}/licensing/customers`, { headers: authHeaders }).then(r => setCustomers(r.data)).catch(() => {});
    }
  }, [showCreate, apiBase, authHeaders]);

  useEffect(() => {
    if (form.customer_id) {
      axios.get(`${apiBase}/licensing/locations?customer_id=${form.customer_id}`, { headers: authHeaders }).then(r => setLocations(r.data)).catch(() => {});
    } else {
      setLocations([]);
    }
  }, [form.customer_id, apiBase, authHeaders]);

  const handleCreate = async () => {
    if (!form.customer_id) { toast.error('Kunde erforderlich'); return; }
    try {
      const payload = { ...form, max_devices: parseInt(form.max_devices) || 1 };
      if (!payload.location_id) delete payload.location_id;
      if (!payload.notes) delete payload.notes;
      const res = await axios.post(`${apiBase}/licensing/licenses`, payload, { headers: authHeaders });
      toast.success('Lizenz erstellt');
      setCreatedLicenseId(res.data.id);
      setShowCreate(false);
      fetchLicenses();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    }
  };

  const activeLicenses = licenses.filter(l => ['active', 'test', 'grace'].includes(l.status));
  const inactiveLicenses = licenses.filter(l => !['active', 'test', 'grace'].includes(l.status));
  const counts = portfolio?.counts || {};
  const focusQueues = portfolio?.focus_queues || {};
  const surfacePrefix = location.pathname.startsWith('/portal') ? '/portal' : '/operator';
  const isOperatorSurface = surfacePrefix === '/operator';

  const pressureHint = useMemo(() => {
    if (!portfolio) return 'Noch keine Portfolio-Signale';
    if ((counts.urgent || 0) > 0) return `${counts.urgent} Lizenz(en) blockieren gerade Commercial Readiness`;
    if ((counts.attention || 0) > 0) return `${counts.attention} Lizenz(en) brauchen aktive Nachverfolgung`;
    return 'Portfolio wirkt aktuell sauber';
  }, [portfolio, counts.urgent, counts.attention]);

  const openLicense = (licenseId, state) => navigate(`${surfacePrefix}/licenses/${licenseId}`, state ? { state } : undefined);
  const openLicenseIntent = (licenseId, intent, state) => {
    const search = intent ? `?intent=${encodeURIComponent(intent)}` : '';
    navigate(`${surfacePrefix}/licenses/${licenseId}${search}`, state ? { state } : undefined);
  };
  const runSuggestedAction = async (licenseId, action) => {
    if (!action) {
      openLicense(licenseId);
      return;
    }

    const execution = action.execution || {};

    if (execution.mode === 'direct' && execution.action === 'ensure_activation_token') {
      if (!canReviewRemoteActions) {
        openLicenseIntent(licenseId, action.intent);
        return;
      }
      try {
        const res = await axios.get(`${apiBase}/licensing/licenses/${licenseId}/token`, { headers: authHeaders });
        const rawToken = res.data.raw_token || null;
        toast.success(res.data.exists ? 'Aktiver Token bereit' : 'Token erstellt');
        openLicenseIntent(licenseId, action.intent, {
          rawToken,
          actionFeedback: {
            tone: 'success',
            title: res.data.exists ? 'Aktiver Token bereit' : 'Neuer Token erstellt',
            message: res.data.exists
              ? 'Den bestehenden Token jetzt am Gerät verwenden oder bei Unsicherheit im Detail einen frischen Token ausstellen.'
              : 'Nächster Schritt: Token direkt am Gerät eingeben und die erste Registrierung abschließen.',
          },
        });
        fetchLicenses();
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Fehler');
      }
      return;
    }

    if (execution.mode === 'direct' && execution.action === 'regenerate_activation_token') {
      if (!canReviewRemoteActions) {
        openLicenseIntent(licenseId, action.intent);
        return;
      }
      try {
        const res = await axios.post(`${apiBase}/licensing/licenses/${licenseId}/regenerate-token`, {}, { headers: authHeaders });
        const rawToken = res.data.raw_token || null;
        toast.success('Token erneuert');
        openLicenseIntent(licenseId, action.intent, {
          rawToken,
          actionFeedback: {
            tone: 'success',
            title: 'Frischer Token erstellt',
            message: res.data.revoked_count > 0
              ? `${res.data.revoked_count} alte(r) Token widerrufen. Jetzt nur noch den neuen Token am Gerät verwenden.`
              : 'Jetzt nur noch den neuen Token am Gerät verwenden.',
          },
        });
        fetchLicenses();
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Fehler');
      }
      return;
    }

    if (execution.mode === 'direct' && execution.action === 'reactivate_license') {
      if (!canManage) {
        openLicenseIntent(licenseId, action.intent);
        return;
      }
      try {
        await axios.put(`${apiBase}/licensing/licenses/${licenseId}`, { status: 'active' }, { headers: authHeaders });
        toast.success('Lizenz reaktiviert');
        openLicenseIntent(licenseId, action.intent, {
          actionFeedback: {
            tone: 'success',
            title: 'Lizenz wieder aktiv',
            message: 'Wenn der Standort noch kein Gerät hat, als Nächstes direkt den Aktivierungstoken prüfen.',
          },
        });
        fetchLicenses();
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Fehler');
      }
      return;
    }

    if (execution.target === 'remote_actions' && isOperatorSurface) {
      navigate(`/operator/remote-actions?license_id=${encodeURIComponent(licenseId)}`);
      return;
    }

    openLicenseIntent(licenseId, action.intent);
  };

  return (
    <div data-testid="licenses-page" className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100 flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-zinc-500" /> Lizenzen
            <span className="text-zinc-600 text-sm ml-2">({licenses.length})</span>
          </h1>
          <p className="mt-1 text-sm text-zinc-500">Commercial Readiness, Renewal-Druck und Aktivierungslücken in einer Operator-Surface.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-md px-2">
            <Filter className="w-3.5 h-3.5 text-zinc-500" />
            <select data-testid="status-filter" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
              className="bg-transparent text-zinc-300 text-sm py-1.5 outline-none cursor-pointer">
              {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          {canManage && (
            <Button data-testid="create-license-btn" onClick={() => setShowCreate(true)} size="sm" className="bg-emerald-600 hover:bg-emerald-700">
              <Plus className="w-4 h-4 mr-1.5" /> Neue Lizenz
            </Button>
          )}
        </div>
      </div>

      {createdLicenseId && (
        <div data-testid="onboarding-cta" className="bg-emerald-900/20 border border-emerald-700/30 rounded-lg p-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="text-emerald-400 font-medium text-sm">Lizenz erstellt!</p>
            <p className="text-zinc-400 text-xs mt-1">Nächster Schritt: Aktivierungstoken erstellen und Gerät verbinden.</p>
          </div>
          <Button data-testid="goto-license-detail-btn" onClick={() => navigate(`${surfacePrefix}/licenses/${createdLicenseId}`)} size="sm" className="bg-emerald-600 hover:bg-emerald-700">
            Gerät jetzt verbinden <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div data-testid="create-license-modal" className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 w-full max-w-md space-y-4">
            <h2 className="text-zinc-100 font-medium">Neue Lizenz erstellen</h2>
            <div>
              <label className="text-zinc-400 text-sm">Kunde *</label>
              <select data-testid="create-customer" value={form.customer_id} onChange={e => setForm({ ...form, customer_id: e.target.value, location_id: '' })}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1">
                <option value="">Auswählen...</option>
                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-sm">Standort</label>
              <select data-testid="create-location" value={form.location_id} onChange={e => setForm({ ...form, location_id: e.target.value })}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1">
                <option value="">Alle Standorte</option>
                {locations.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-zinc-400 text-sm">Plan</label>
                <select data-testid="create-plan" value={form.plan_type} onChange={e => setForm({ ...form, plan_type: e.target.value })}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1">
                  <option value="standard">Standard</option>
                  <option value="premium">Premium</option>
                  <option value="enterprise">Enterprise</option>
                  <option value="test">Test</option>
                </select>
              </div>
              <div>
                <label className="text-zinc-400 text-sm">Max. Geräte</label>
                <input data-testid="create-max-devices" type="number" min="1" value={form.max_devices}
                  onChange={e => setForm({ ...form, max_devices: e.target.value })}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1" />
              </div>
            </div>
            <div>
              <label className="text-zinc-400 text-sm">Notizen</label>
              <input data-testid="create-notes" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1" placeholder="Optional" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => { setShowCreate(false); setForm({ customer_id: '', location_id: '', plan_type: 'standard', max_devices: 1, status: 'active', notes: '' }); }}
                className="border-zinc-700 text-zinc-400">Abbrechen</Button>
              <Button data-testid="create-confirm-btn" size="sm" onClick={handleCreate} className="bg-emerald-600 hover:bg-emerald-700">Erstellen</Button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-zinc-500 py-8 text-center">Laden...</div>
      ) : licenses.length === 0 ? (
        <div data-testid="licenses-empty-state" className="text-center py-16">
          <KeyRound className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
          <p className="text-zinc-400">{statusFilter ? `Keine ${STATUS_OPTIONS.find(o => o.value === statusFilter)?.label || ''} Lizenzen` : 'Noch keine Lizenzen vorhanden'}</p>
          {canManage && !statusFilter && <p className="text-zinc-600 text-sm mt-1">Erstellen Sie eine erste Lizenz, um Geräte zu verbinden.</p>}
        </div>
      ) : (
        <>
          <section className="rounded-3xl border border-zinc-800 bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 p-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs text-indigo-300">
                  <BriefcaseBusiness className="w-3.5 h-3.5" /> License command surface
                </div>
                <h2 className="mt-3 text-lg font-semibold text-white">Portfolio-Druck sofort sichtbar</h2>
                <p className="mt-1 text-sm text-zinc-400 max-w-2xl">{pressureHint}</p>
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-black/20 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">Portfolio-Split</p>
                <div className="mt-2 flex items-center gap-3 text-sm">
                  <span className="text-red-300">{counts.urgent || 0} dringend</span>
                  <span className="text-amber-300">{counts.attention || 0} aktiv</span>
                  <span className="text-sky-300">{counts.watch || 0} beobachten</span>
                  <span className="text-emerald-300">{counts.healthy || 0} gesund</span>
                </div>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
              <KpiCard icon={TriangleAlert} label="Dringende Lizenzen" value={counts.urgent || 0} hint="Inaktiv, blockiert oder über Kapazität" tone={(counts.urgent || 0) > 0 ? 'red' : 'zinc'} />
              <KpiCard icon={Clock} label="Renewals / Grace" value={(counts.renewal_due || 0) + (counts.in_grace || 0)} hint={`${counts.renewal_due || 0} bald fällig · ${counts.in_grace || 0} in Grace`} tone={((counts.renewal_due || 0) + (counts.in_grace || 0)) > 0 ? 'amber' : 'zinc'} />
              <KpiCard icon={PackageOpen} label="Aktivierungslücken" value={counts.activation_gap || 0} hint="Aktive Lizenzen ohne gebundenes Gerät" tone={(counts.activation_gap || 0) > 0 ? 'blue' : 'zinc'} />
              <KpiCard icon={Sparkles} label="Token bereit" value={counts.token_ready || 0} hint={`${counts.token_attention || 0} brauchen Token-Follow-up`} tone={((counts.token_ready || 0) + (counts.token_attention || 0)) > 0 ? 'blue' : 'zinc'} />
              <KpiCard icon={Gauge} label="Kapazitätsdruck" value={counts.full_or_over_capacity || 0} hint={`${counts.near_capacity || 0} fast/voll · ${counts.blocked_devices || 0} posture-blocked`} tone={((counts.full_or_over_capacity || 0) + (counts.blocked_devices || 0)) > 0 ? 'amber' : 'zinc'} />
            </div>
          </section>

          <section className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-5 gap-4">
            <FocusQueue
              title="Jetzt eskalieren"
              hint="Die problematischsten kommerziellen Fälle zuerst."
              items={focusQueues.urgent || []}
              empty="Keine akuten Lizenzblocker im aktuellen Scope."
              onOpenLicense={openLicense}
              onRunAction={runSuggestedAction}
              accent="red"
            />
            <FocusQueue
              title="Renewal-Funnel"
              hint="Laufzeiten, Grace und Kundenansprache im Blick."
              items={focusQueues.renewals || []}
              empty="Gerade kein Renewal-Druck sichtbar."
              onOpenLicense={openLicense}
              onRunAction={runSuggestedAction}
              accent="amber"
            />
            <FocusQueue
              title="Aktivierungslücken"
              hint="Verkauft, aber noch nicht live auf einem Gerät."
              items={focusQueues.activation_gaps || []}
              empty="Keine aktiven Lizenzen ohne Gerätebindung."
              onOpenLicense={openLicense}
              onRunAction={runSuggestedAction}
              accent="blue"
            />
            <FocusQueue
              title="Token-Follow-up"
              hint="Welche Aktivierung offen, stale oder sofort versandbereit ist."
              items={focusQueues.token_follow_up || []}
              empty="Keine offenen Token-Nachfassfälle im aktuellen Scope."
              onOpenLicense={openLicense}
              onRunAction={runSuggestedAction}
              accent="blue"
            />
            <FocusQueue
              title="Geräte-Review"
              hint="Gebundene Geräte mit Advisory-Blockern oder Review-Signalen."
              items={focusQueues.device_review || []}
              empty="Keine gebundenen Geräte mit kritischer Posture."
              onOpenLicense={openLicense}
              onRunAction={runSuggestedAction}
              accent="emerald"
            />
          </section>

          <div className="space-y-4">
            {activeLicenses.length > 0 && (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 overflow-hidden">
                <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
                  <p className="text-sm font-medium text-white">Aktive Commercial Surface</p>
                  <p className="text-xs text-zinc-500">Aktive, Test- und Grace-Lizenzen mit Readiness-Signal</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-800 text-zinc-500 text-xs">
                        <th className="text-left px-4 py-2">Plan / Kunde</th>
                        <th className="text-left px-4 py-2">Commercial Readiness</th>
                        <th className="text-left px-4 py-2">Aktivierung</th>
                        <th className="text-left px-4 py-2">Geräte / Kapazität</th>
                        <th className="text-left px-4 py-2">Advisory</th>
                        <th className="text-left px-4 py-2">Status / Laufzeit</th>
                        <th className="text-left px-4 py-2">Aktion</th>
                        <th className="px-4 py-2"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeLicenses.map(lic => {
                        const readiness = lic.commercial_readiness || {};
                        const primaryAction = readiness.suggested_actions?.[0];
                        const secondaryAction = readiness.suggested_actions?.find((item) => item.type !== primaryAction?.type);
                        return (
                          <tr key={lic.id} data-testid={`license-row-${lic.id}`}
                            className="border-b border-zinc-800/50 hover:bg-zinc-800/30 cursor-pointer transition-colors"
                            onClick={() => openLicense(lic.id)}>
                            <td className="px-4 py-3 align-top">
                              <div className="text-zinc-100 font-medium capitalize">{lic.plan_type}</div>
                              <div className="mt-1 text-zinc-400">{lic.customer_name || lic.customer_id?.slice(0, 8)}</div>
                              <div className="mt-1 text-[11px] font-mono text-zinc-600">{lic.id}</div>
                            </td>
                            <td className="px-4 py-3 align-top">
                              <div className="flex items-center gap-2 flex-wrap">
                                <ReadinessBadge readiness={readiness} />
                                <StatusBadge status={lic.computed_status || lic.status} />
                              </div>
                              <p className="mt-2 text-sm text-zinc-200">{readiness.primary_message || '—'}</p>
                              <p className="mt-1 text-xs text-zinc-500 max-w-md">{readiness.recommended_action || '—'}</p>
                            </td>
                            <td className="px-4 py-3 align-top text-zinc-300">
                              <TokenBadge summary={readiness.token_summary} />
                              <div className="mt-1 text-xs text-zinc-500 max-w-44">{readiness.token_summary?.message || '—'}</div>
                            </td>
                            <td className="px-4 py-3 align-top text-zinc-300">
                              <div className="font-medium">{lic.device_count ?? 0}/{lic.max_devices}</div>
                              <div className="mt-1 text-xs text-zinc-500">{capacityLabel(readiness.capacity_state)}</div>
                              {readiness.occupancy_ratio != null && (
                                <div className="mt-2 h-1.5 w-28 rounded-full bg-zinc-800 overflow-hidden">
                                  <div className={`h-full ${readiness.occupancy_ratio > 1 ? 'bg-red-400' : readiness.occupancy_ratio >= 1 ? 'bg-amber-400' : readiness.occupancy_ratio >= 0.8 ? 'bg-sky-400' : 'bg-emerald-400'}`} style={{ width: `${Math.min(readiness.occupancy_ratio * 100, 100)}%` }} />
                                </div>
                              )}
                            </td>
                            <td className="px-4 py-3 align-top">
                              <div className={`font-medium ${POSTURE_TONE[readiness.posture_status] || 'text-zinc-300'}`}>{postureLabel(readiness.posture_status)}</div>
                              <div className="mt-1 text-xs text-zinc-500">
                                {(readiness.posture_counts?.blocked || 0) > 0 && <span>{readiness.posture_counts.blocked} blocked · </span>}
                                {(readiness.posture_counts?.review_required || 0) > 0 && <span>{readiness.posture_counts.review_required} review · </span>}
                                {(readiness.posture_counts?.degraded || 0) > 0 && <span>{readiness.posture_counts.degraded} degraded · </span>}
                                {readiness.posture_counts?.ready ?? 0} ready
                              </div>
                            </td>
                            <td className="px-4 py-3 align-top text-zinc-400">
                              <div>{formatShortDate(lic.ends_at)}</div>
                              {readiness.renewal_days != null && <div className="mt-1 text-xs text-zinc-500">{readiness.renewal_days} Tage bis Ablauf</div>}
                            </td>
                            <td className="px-4 py-3 align-top">
                              <div className="flex flex-col items-start gap-2">
                                <button
                                  onClick={(e) => { e.stopPropagation(); runSuggestedAction(lic.id, primaryAction); }}
                                  className="inline-flex items-center gap-1 rounded-lg bg-zinc-100 px-2.5 py-1.5 text-xs font-medium text-zinc-900 hover:bg-white"
                                >
                                  {actionIntentLabel(primaryAction)} <ArrowRight className="w-3.5 h-3.5" />
                                </button>
                                {secondaryAction && (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); runSuggestedAction(lic.id, secondaryAction); }}
                                    className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800"
                                  >
                                    {actionIntentLabel(secondaryAction)} <ArrowRight className="w-3.5 h-3.5" />
                                  </button>
                                )}
                                {isOperatorSurface && (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); navigate(`/operator/remote-actions?license_id=${encodeURIComponent(lic.id)}`); }}
                                    className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-indigo-300 hover:bg-indigo-500/10"
                                  >
                                    Remote Actions <ExternalLink className="w-3.5 h-3.5" />
                                  </button>
                                )}
                                <button
                                  onClick={(e) => { e.stopPropagation(); openLicense(lic.id); }}
                                  className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800"
                                >
                                  Lizenz öffnen <ArrowRight className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </td>
                            <td className="px-4 py-3 align-top"><ChevronRight className="w-4 h-4 text-zinc-600" /></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {inactiveLicenses.length > 0 && (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/30 overflow-hidden">
                <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
                  <p className="text-sm font-medium text-white">Inaktive / historische Lizenzen</p>
                  <p className="text-xs text-zinc-500">Zur Klärung, Reaktivierung oder Archivpflege</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm opacity-80">
                    <tbody>
                      {inactiveLicenses.map(lic => (
                        (() => {
                          const readiness = lic.commercial_readiness || {};
                          const primaryAction = readiness.suggested_actions?.[0];
                          return (
                        <tr key={lic.id} data-testid={`license-row-${lic.id}`}
                          className="border-b border-zinc-800/30 hover:bg-zinc-800/20 cursor-pointer transition-colors"
                          onClick={() => openLicense(lic.id)}>
                          <td className="px-4 py-3 text-zinc-300">{lic.plan_type}</td>
                          <td className="px-4 py-3 text-zinc-400">{lic.customer_name || lic.customer_id?.slice(0, 8)}</td>
                          <td className="px-4 py-3"><StatusBadge status={lic.computed_status || lic.status} /></td>
                          <td className="px-4 py-3 text-zinc-500">{lic.commercial_readiness?.primary_message || '—'}</td>
                          <td className="px-4 py-3 text-zinc-500">
                            <div>{lic.commercial_readiness?.token_summary?.message || tokenStateLabel(lic.commercial_readiness?.token_state)}</div>
                            <div className="mt-1 text-xs text-zinc-600">{lic.device_count ?? 0}/{lic.max_devices} Geräte</div>
                          </td>
                          <td className="px-4 py-3 text-zinc-600">{formatShortDate(lic.ends_at)}</td>
                          <td className="px-4 py-3">
                            <div className="flex flex-col items-start gap-2">
                            {primaryAction && (
                              <button
                                onClick={(e) => { e.stopPropagation(); runSuggestedAction(lic.id, primaryAction); }}
                                className="inline-flex items-center gap-1 rounded-lg bg-zinc-100 px-2 py-1 text-xs font-medium text-zinc-900 hover:bg-white"
                              >
                                {actionIntentLabel(primaryAction)} <ArrowRight className="w-3.5 h-3.5" />
                              </button>
                            )}
                            {isOperatorSurface ? (
                              <button
                                onClick={(e) => { e.stopPropagation(); navigate(`/operator/remote-actions?license_id=${encodeURIComponent(lic.id)}`); }}
                                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-indigo-300 hover:bg-indigo-500/10"
                              >
                                Öffnen <ExternalLink className="w-3.5 h-3.5" />
                              </button>
                            ) : (
                              <button
                                onClick={(e) => { e.stopPropagation(); openLicense(lic.id); }}
                                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800"
                              >
                                Detail <ArrowRight className="w-3.5 h-3.5" />
                              </button>
                            )}
                            </div>
                          </td>
                          <td className="px-4 py-3"><ChevronRight className="w-4 h-4 text-zinc-700" /></td>
                        </tr>
                          );
                        })()
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

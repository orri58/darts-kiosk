import { useState, useCallback, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useCentralAuth } from '../../context/CentralAuthContext';
import axios from 'axios';
import {
  KeyRound, Plus, CheckCircle, AlertTriangle, Ban, Shield, Clock, Archive, Filter, ChevronRight, ExternalLink,
  Gauge, Sparkles, TriangleAlert, PackageOpen, ArrowRight
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import { ProductDataTable, ProductFilterSummary, ProductPageState } from '../../components/shell/ProductDataDisplay';
import { ProductPageHeader, ProductSection, ProductStatCard, SurfaceBadge } from '../../components/shell/ProductShell';
import { ProductCallout, ProductFocusList, ProductInlineActions } from '../../components/shell/ProductDetail';
import { buildLicenseDetailPath, getTokenStatePresentation } from './operatorCommercialFlow';

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

function tokenStateLabel(value) {
  return getTokenStatePresentation({ state: value }, { compact: true }).label;
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

function TokenBadge({ summary, compact = false }) {
  const tokenMeta = getTokenStatePresentation(summary, { compact });

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${tokenMeta.tone}`} title={tokenMeta.detail || tokenMeta.label}>
      {compact ? tokenMeta.shortLabel : tokenMeta.label}{tokenMeta.detail ? ` · ${tokenMeta.detail}` : ''}
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

function focusMeta(item) {
  return (
    <>
      <ReadinessBadge readiness={item} />
      <TokenBadge summary={item.token_summary} compact />
      <span className="text-[11px] text-zinc-500">{statusLabel(item.computed_status)}</span>
      <span className="text-[11px] text-zinc-500">{item.device_count ?? 0}/{item.max_devices || '—'} Geräte</span>
      {item.renewal_days != null ? <span className="text-[11px] text-zinc-500">{item.renewal_days} Tage</span> : null}
      <span className={`text-[11px] ${POSTURE_TONE[item.posture_status] || 'text-zinc-400'}`}>Posture: {postureLabel(item.posture_status)}</span>
    </>
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
  const [actionLoadingId, setActionLoadingId] = useState(null);

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

  const currentListPath = `${location.pathname}${location.search || ''}`;
  const listLabel = statusFilter ? `Lizenzen · ${STATUS_OPTIONS.find((item) => item.value === statusFilter)?.label || 'Filter'}` : 'Lizenzen';
  const openLicense = (licenseId, state, options = {}) => navigate(
    buildLicenseDetailPath(surfacePrefix, licenseId, {
      intent: options.intent || '',
      returnTo: currentListPath,
      returnLabel: listLabel,
    }),
    state ? { state: { ...state, fromListPath: currentListPath, fromListLabel: listLabel } } : undefined,
  );
  const openLicenseIntent = (licenseId, intent, state) => {
    openLicense(licenseId, state, { intent });
  };
  const runSuggestedAction = async (licenseId, action) => {
    if (!action) {
      openLicense(licenseId);
      return;
    }

    const execution = action.execution || {};
    setActionLoadingId(licenseId);

    try {

    if (execution.mode === 'direct' && execution.action === 'ensure_activation_token') {
      if (!canReviewRemoteActions) {
        openLicenseIntent(licenseId, action.intent);
        return;
      }
      const res = await axios.get(`${apiBase}/licensing/licenses/${licenseId}/token`, { headers: authHeaders });
      const rawToken = res.data.raw_token || null;
      toast.success(res.data.exists ? 'Aktiver Token bereit' : 'Token erstellt');
      openLicenseIntent(licenseId, action.intent, {
        rawToken,
        actionFeedback: {
          tone: 'success',
          title: res.data.exists ? 'Aktiver Token bereit' : 'Neuer Token erstellt',
          message: res.data.exists
            ? 'Direkt am Gerät eingeben oder im Detail einen frischen Token ausstellen.'
            : 'Nächster Schritt: Token direkt am Gerät eingeben und die Registrierung abschließen.',
        },
      });
      fetchLicenses();
      return;
    }

    if (execution.mode === 'direct' && execution.action === 'regenerate_activation_token') {
      if (!canReviewRemoteActions) {
        openLicenseIntent(licenseId, action.intent);
        return;
      }
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
      return;
    }

    if (execution.mode === 'direct' && execution.action === 'reactivate_license') {
      if (!canManage) {
        openLicenseIntent(licenseId, action.intent);
        return;
      }
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
      return;
    }

    if (execution.target === 'remote_actions' && isOperatorSurface) {
      navigate(`/operator/remote-actions?license_id=${encodeURIComponent(licenseId)}`);
      return;
    }

    openLicenseIntent(licenseId, action.intent);
  } catch (err) {
    toast.error(err.response?.data?.detail || 'Fehler');
  } finally {
    setActionLoadingId(null);
  }
  };

  return (
    <div data-testid="licenses-page" className="space-y-6">
      <ProductPageHeader
        eyebrow="Commercial"
        title={`Lizenzen (${licenses.length})`}
        badge={<SurfaceBadge tone={(counts.urgent || 0) > 0 ? 'amber' : 'blue'}>Operator control surface</SurfaceBadge>}
        description="Commercial Readiness, Renewal-Druck und Aktivierungslücken in einer Operator-Surface."
        actions={
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
        }
      />

      <ProductFilterSummary
        label="Scope"
        items={[
          { key: 'Status', value: STATUS_OPTIONS.find((item) => item.value === statusFilter)?.label || 'Alle Status' },
          { key: 'Aktiv', value: String(activeLicenses.length) },
          { key: 'Historisch', value: String(inactiveLicenses.length) },
          ...(portfolio?.counts?.urgent ? [{ key: 'Dringend', value: String(portfolio.counts.urgent) }] : []),
        ]}
        data-testid="operator-licenses-scope-summary"
      />

      {createdLicenseId && (
        <ProductCallout
          tone="emerald"
          eyebrow="Activation handoff"
          title="Lizenz erstellt"
          description="Nächster Schritt: Aktivierungstoken erzeugen und das erste Gerät sauber anbinden."
          actions={(
            <ProductInlineActions
              mode="operator"
              items={[
                {
                  label: 'Gerät jetzt verbinden',
                  onClick: () => navigate(buildLicenseDetailPath(surfacePrefix, createdLicenseId, { returnTo: currentListPath, returnLabel: listLabel })),
                  trailingIcon: ChevronRight,
                  className: 'bg-emerald-600 hover:bg-emerald-700 text-white',
                },
              ]}
            />
          )}
          data-testid="onboarding-cta"
        />
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
        <ProductPageState kind="loading" title="Lizenzportfolio wird geladen" description="Commercial Readiness, Renewals und Tokenlage werden zusammengeführt." data-testid="operator-licenses-loading" />
      ) : licenses.length === 0 ? (
        <ProductPageState
          kind={statusFilter ? 'filtered' : 'empty'}
          title={statusFilter ? `Keine ${STATUS_OPTIONS.find(o => o.value === statusFilter)?.label || ''} Lizenzen` : 'Noch keine Lizenzen vorhanden'}
          description={canManage && !statusFilter ? 'Erstellen Sie eine erste Lizenz, um Geräte zu verbinden.' : 'Im aktuellen Filter gibt es gerade keine passenden Lizenzen.'}
          data-testid="licenses-empty-state"
        />
      ) : (
        <>
          <ProductSection
            eyebrow="Commercial readiness"
            title="Portfolio-Druck sofort sichtbar"
            description="Dieselbe Commercial-Lage wie im Detail-Drill-in, aber als gemeinsame Command Surface für Queue, Scope und direkte Eingriffe."
            actions={<SurfaceBadge tone={(counts.urgent || 0) > 0 ? 'amber' : 'emerald'}>{pressureHint}</SurfaceBadge>}
          >
            <div className="space-y-4 p-4">
              <ProductCallout
                tone={(counts.urgent || 0) > 0 ? 'red' : (counts.attention || 0) > 0 ? 'amber' : 'blue'}
                eyebrow="Advisory"
                title={(counts.urgent || 0) > 0 ? `${counts.urgent} Lizenz(en) brauchen jetzt Eskalation` : 'Commercial Surface im Takt'}
                description={pressureHint}
                actions={(
                  <ProductInlineActions
                    mode="operator"
                    items={[
                      ...(canReviewRemoteActions ? [{ label: 'Remote Actions', onClick: () => navigate('/operator/remote-actions'), trailingIcon: ExternalLink, className: 'border-indigo-500/20 text-indigo-300 hover:bg-indigo-500/10' }] : []),
                      ...(canManage ? [{ label: 'Neue Lizenz', onClick: () => setShowCreate(true), className: 'bg-emerald-600 hover:bg-emerald-700 text-white' }] : []),
                    ]}
                  />
                )}
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
                <ProductStatCard icon={TriangleAlert} label="Dringende Lizenzen" value={counts.urgent || 0} hint="Inaktiv, blockiert oder über Kapazität" tone={(counts.urgent || 0) > 0 ? 'red' : 'default'} />
                <ProductStatCard icon={Clock} label="Renewals / Grace" value={(counts.renewal_due || 0) + (counts.in_grace || 0)} hint={`${counts.renewal_due || 0} bald fällig · ${counts.in_grace || 0} in Grace`} tone={((counts.renewal_due || 0) + (counts.in_grace || 0)) > 0 ? 'amber' : 'default'} />
                <ProductStatCard icon={PackageOpen} label="Aktivierungslücken" value={counts.activation_gap || 0} hint="Aktive Lizenzen ohne gebundenes Gerät" tone={(counts.activation_gap || 0) > 0 ? 'blue' : 'default'} />
                <ProductStatCard icon={Sparkles} label="Token bereit" value={counts.token_ready || 0} hint={`${counts.token_attention || 0} brauchen Token-Follow-up`} tone={((counts.token_ready || 0) + (counts.token_attention || 0)) > 0 ? 'blue' : 'default'} />
                <ProductStatCard icon={Gauge} label="Kapazitätsdruck" value={counts.full_or_over_capacity || 0} hint={`${counts.near_capacity || 0} fast/voll · ${counts.blocked_devices || 0} posture-blocked`} tone={((counts.full_or_over_capacity || 0) + (counts.blocked_devices || 0)) > 0 ? 'amber' : 'default'} />
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-5 gap-4">
                <ProductFocusList
                  title="Jetzt eskalieren"
                  hint="Die problematischsten kommerziellen Fälle zuerst."
                  items={focusQueues.urgent || []}
                  empty="Keine akuten Lizenzblocker im aktuellen Scope."
                  onOpen={(item) => openLicense(item.license_id)}
                  accent="red"
                  getMeta={focusMeta}
                  onAction={(item) => item.suggested_actions?.[0] ? runSuggestedAction(item.license_id, item.suggested_actions[0]) : openLicense(item.license_id)}
                  getActionLabel={(item) => actionIntentLabel(item.suggested_actions?.[0])}
                />
                <ProductFocusList
                  title="Renewal-Funnel"
                  hint="Laufzeiten, Grace und Kundenansprache im Blick."
                  items={focusQueues.renewals || []}
                  empty="Gerade kein Renewal-Druck sichtbar."
                  onOpen={(item) => openLicense(item.license_id)}
                  accent="amber"
                  getMeta={focusMeta}
                  onAction={(item) => item.suggested_actions?.[0] ? runSuggestedAction(item.license_id, item.suggested_actions[0]) : openLicense(item.license_id)}
                  getActionLabel={(item) => actionIntentLabel(item.suggested_actions?.[0])}
                />
                <ProductFocusList
                  title="Aktivierungslücken"
                  hint="Verkauft, aber noch nicht live auf einem Gerät."
                  items={focusQueues.activation_gaps || []}
                  empty="Keine aktiven Lizenzen ohne Gerätebindung."
                  onOpen={(item) => openLicense(item.license_id)}
                  accent="blue"
                  getMeta={focusMeta}
                  onAction={(item) => item.suggested_actions?.[0] ? runSuggestedAction(item.license_id, item.suggested_actions[0]) : openLicense(item.license_id)}
                  getActionLabel={(item) => actionIntentLabel(item.suggested_actions?.[0])}
                />
                <ProductFocusList
                  title="Token-Follow-up"
                  hint="Welche Aktivierung offen, stale oder sofort versandbereit ist."
                  items={focusQueues.token_follow_up || []}
                  empty="Keine offenen Token-Nachfassfälle im aktuellen Scope."
                  onOpen={(item) => openLicense(item.license_id)}
                  accent="blue"
                  getMeta={focusMeta}
                  onAction={(item) => item.suggested_actions?.[0] ? runSuggestedAction(item.license_id, item.suggested_actions[0]) : openLicense(item.license_id)}
                  getActionLabel={(item) => actionIntentLabel(item.suggested_actions?.[0])}
                />
                <ProductFocusList
                  title="Geräte-Review"
                  hint="Gebundene Geräte mit Advisory-Blockern oder Review-Signalen."
                  items={focusQueues.device_review || []}
                  empty="Keine gebundenen Geräte mit kritischer Posture."
                  onOpen={(item) => openLicense(item.license_id)}
                  accent="emerald"
                  getMeta={focusMeta}
                  onAction={(item) => item.suggested_actions?.[0] ? runSuggestedAction(item.license_id, item.suggested_actions[0]) : openLicense(item.license_id)}
                  getActionLabel={(item) => actionIntentLabel(item.suggested_actions?.[0])}
                />
              </div>
            </div>
          </ProductSection>

          <div className="space-y-4">
            {activeLicenses.length > 0 && (
              <ProductSection title="Aktive Commercial Surface" description="Aktive, Test- und Grace-Lizenzen mit Readiness-Signal">
                <ProductDataTable columns={[
                  { key: 'plan', label: 'Plan / Kunde' },
                  { key: 'readiness', label: 'Commercial Readiness' },
                  { key: 'activation', label: 'Aktivierung' },
                  { key: 'capacity', label: 'Geräte / Kapazität' },
                  { key: 'advisory', label: 'Advisory' },
                  { key: 'status', label: 'Status / Laufzeit' },
                  { key: 'action', label: 'Aktion' },
                  { key: 'chevron', label: '' },
                ]}>
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
                                  disabled={actionLoadingId === lic.id}
                                  className="inline-flex items-center gap-1 rounded-lg bg-zinc-100 px-2.5 py-1.5 text-xs font-medium text-zinc-900 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {actionLoadingId === lic.id ? 'Läuft…' : actionIntentLabel(primaryAction)} <ArrowRight className="w-3.5 h-3.5" />
                                </button>
                                {secondaryAction && (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); runSuggestedAction(lic.id, secondaryAction); }}
                                    disabled={actionLoadingId === lic.id}
                                    className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
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
                </ProductDataTable>
              </ProductSection>
            )}

            {inactiveLicenses.length > 0 && (
              <ProductSection title="Inaktive / historische Lizenzen" description="Zur Klärung, Reaktivierung oder Archivpflege">
                <ProductDataTable className="opacity-80" columns={[
                  { key: 'plan', label: 'Plan' },
                  { key: 'customer', label: 'Kunde' },
                  { key: 'status', label: 'Status' },
                  { key: 'note', label: 'Hinweis' },
                  { key: 'token', label: 'Token / Geräte' },
                  { key: 'ends', label: 'Laufzeit' },
                  { key: 'action', label: 'Aktion' },
                  { key: 'chevron', label: '' },
                ]}>
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
                                disabled={actionLoadingId === lic.id}
                                className="inline-flex items-center gap-1 rounded-lg bg-zinc-100 px-2 py-1 text-xs font-medium text-zinc-900 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
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
                </ProductDataTable>
              </ProductSection>
            )}
          </div>
        </>
      )}
    </div>
  );
}

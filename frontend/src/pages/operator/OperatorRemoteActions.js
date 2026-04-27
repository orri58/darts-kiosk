import { useEffect, useMemo, useState, useCallback } from 'react';
import axios from 'axios';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  RefreshCw,
  ShieldCheck,
  ShieldX,
  Clock3,
  Send,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  History,
  Filter,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ExternalLink,
  Eye,
  Search,
} from 'lucide-react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

const REQUEST_STATE_OPTIONS = [
  { value: '', label: 'Alle States' },
  { value: 'pending_review', label: 'Pending Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'completed', label: 'Completed' },
  { value: 'refused', label: 'Refused' },
  { value: 'expired', label: 'Expired' },
  { value: 'failed', label: 'Failed' },
];

const APPROVAL_STATE_OPTIONS = [
  { value: '', label: 'Alle Review-States' },
  { value: 'pending', label: 'Pending Approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'refused', label: 'Refused' },
  { value: 'not_required', label: 'Ohne Review' },
];

const ACTION_TYPE_OPTIONS = [
  { value: '', label: 'Alle Aktionen' },
  { value: 'force_sync', label: 'Force Sync' },
  { value: 'reload_ui', label: 'Reload UI' },
  { value: 'restart_backend', label: 'Restart Backend (Review)' },
  { value: 'unlock_board', label: 'Unlock Board (zentral blockiert)' },
  { value: 'lock_board', label: 'Lock Board (zentral blockiert)' },
  { value: 'start_session', label: 'Start Session (zentral blockiert)' },
  { value: 'stop_session', label: 'Stop Session (zentral blockiert)' },
];

const SORT_OPTIONS = [
  { value: 'issued_desc', label: 'Neueste zuerst' },
  { value: 'issued_asc', label: 'Älteste zuerst' },
  { value: 'finalized_desc', label: 'Zuletzt finalisiert' },
  { value: 'state_priority', label: 'Nach Handlungsbedarf' },
  { value: 'device_asc', label: 'Gerät A–Z' },
];

const PAGE_SIZE_OPTIONS = [20, 25, 50, 100];

function formatDateTime(ts) {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return ts;
  }
}

function timeAgo(ts) {
  if (!ts) return '—';
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 60) return `vor ${diff}s`;
  if (diff < 3600) return `vor ${Math.floor(diff / 60)} Min.`;
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)} Std.`;
  return `vor ${Math.floor(diff / 86400)} Tagen`;
}

function MetricCard({ icon: Icon, label, value, sub, tone = 'zinc' }) {
  const tones = {
    zinc: 'border-zinc-800 text-zinc-400',
    amber: 'border-amber-500/20 text-amber-400',
    emerald: 'border-emerald-500/20 text-emerald-400',
    red: 'border-red-500/20 text-red-400',
    blue: 'border-blue-500/20 text-blue-400',
  };
  return (
    <div className={`rounded-xl border bg-zinc-900 p-4 ${tones[tone] || tones.zinc}`}>
      <div className="flex items-center justify-between mb-2">
        <Icon className="w-4 h-4 opacity-80" />
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs opacity-70 mt-0.5">{label}</p>
      {sub && <p className="text-xs opacity-50 mt-0.5">{sub}</p>}
    </div>
  );
}

function StatePill({ state, approvalState, outcomeCode }) {
  const s = String(state || '').toLowerCase();
  const a = String(approvalState || '').toLowerCase();
  const o = String(outcomeCode || '').toLowerCase();

  let cls = 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20';
  let label = state || 'unknown';

  if (a === 'pending' || s === 'pending_review') {
    cls = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    label = 'Review ausstehend';
  } else if (s === 'approved' || a === 'approved') {
    cls = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    label = 'Freigegeben';
  } else if (s === 'delivered' || s === 'pending_delivery') {
    cls = 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
    label = 'Ausgeliefert';
  } else if (s === 'completed' || o === 'succeeded' || o === 'accepted') {
    cls = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    label = 'Abgeschlossen';
  } else if (s === 'refused' || a === 'refused' || o === 'refused') {
    cls = 'bg-red-500/10 text-red-400 border-red-500/20';
    label = 'Abgelehnt';
  } else if (s === 'expired' || o === 'expired') {
    cls = 'bg-orange-500/10 text-orange-400 border-orange-500/20';
    label = 'Abgelaufen';
  } else if (s === 'failed') {
    cls = 'bg-red-500/10 text-red-400 border-red-500/20';
    label = 'Fehlgeschlagen';
  }

  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

function actionPriority(item) {
  if (!item) return 99;
  if (item.approval_state === 'pending' || item.request_state === 'pending_review') return 0;
  if (item.request_state === 'delivered') return 1;
  if (item.request_state === 'expired' || item.outcome_code === 'expired') return 2;
  if (item.request_state === 'refused' || item.approval_state === 'refused') return 3;
  if (item.request_state === 'failed') return 4;
  if (item.request_state === 'approved') return 5;
  if (item.request_state === 'completed') return 6;
  return 7;
}

function sortItems(items, sortBy) {
  const list = [...(items || [])];
  list.sort((a, b) => {
    if (sortBy === 'issued_asc') return new Date(a.issued_at || 0).getTime() - new Date(b.issued_at || 0).getTime();
    if (sortBy === 'finalized_desc') return new Date(b.finalized_at || b.issued_at || 0).getTime() - new Date(a.finalized_at || a.issued_at || 0).getTime();
    if (sortBy === 'state_priority') {
      const prio = actionPriority(a) - actionPriority(b);
      if (prio !== 0) return prio;
      return new Date(b.issued_at || 0).getTime() - new Date(a.issued_at || 0).getTime();
    }
    if (sortBy === 'device_asc') {
      const nameA = String(a.scope?.device_name || a.device_id || '').toLowerCase();
      const nameB = String(b.scope?.device_name || b.device_id || '').toLowerCase();
      return nameA.localeCompare(nameB) || (new Date(b.issued_at || 0).getTime() - new Date(a.issued_at || 0).getTime());
    }
    return new Date(b.issued_at || 0).getTime() - new Date(a.issued_at || 0).getTime();
  });
  return list;
}

function PageControls({ page, hasMore, returned, pageSize, onPrev, onNext, label, tidPrefix }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-zinc-800 bg-zinc-950/40">
      <p className="text-xs text-zinc-500">{label} · Seite {page} · {returned} sichtbar · {pageSize}/Seite</p>
      <div className="flex items-center gap-2">
        <button
          onClick={onPrev}
          disabled={page <= 1}
          className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 disabled:opacity-40"
          data-testid={`${tidPrefix}-prev`}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> Zurück
        </button>
        <button
          onClick={onNext}
          disabled={!hasMore}
          className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 disabled:opacity-40"
          data-testid={`${tidPrefix}-next`}
        >
          Weiter <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

export default function OperatorRemoteActions() {
  const navigate = useNavigate();
  const { apiBase, authHeaders, scope, canReviewRemoteActions } = useCentralAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [overview, setOverview] = useState(null);
  const [reviewQueue, setReviewQueue] = useState(null);
  const [deviceHistory, setDeviceHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [reviewingId, setReviewingId] = useState(null);
  const [selectedAction, setSelectedAction] = useState(null);

  const filters = useMemo(() => ({
    request_state: searchParams.get('request_state') || '',
    approval_state: searchParams.get('approval_state') || '',
    action_type: searchParams.get('action_type') || '',
    include_expired: searchParams.get('include_expired') !== 'false',
    customer_id: searchParams.get('customer_id') || '',
    location_id: searchParams.get('location_id') || '',
    device_id: searchParams.get('device_id') || '',
    license_id: searchParams.get('license_id') || '',
    sort: searchParams.get('sort') || 'issued_desc',
    review_page: Math.max(1, Number(searchParams.get('review_page') || '1')),
    history_page: Math.max(1, Number(searchParams.get('history_page') || '1')),
    page_size: Math.max(1, Number(searchParams.get('page_size') || '20')),
  }), [searchParams]);

  const setParamState = useCallback((updates, options = {}) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === '' || value === null || value === undefined || value === false) next.delete(key);
      else next.set(key, String(value));
    });
    if (!('review_page' in updates)) next.set('review_page', '1');
    if (!('history_page' in updates)) next.set('history_page', '1');
    setSearchParams(next, options);
  }, [searchParams, setSearchParams]);

  const overviewParams = useMemo(() => {
    const params = new URLSearchParams();
    if (filters.location_id) params.set('location_id', filters.location_id);
    else if (filters.customer_id) params.set('customer_id', filters.customer_id);
    else if (scope.locationId) params.set('location_id', scope.locationId);
    else if (scope.customerId) params.set('customer_id', scope.customerId);
    if (filters.license_id) params.set('license_id', filters.license_id);
    if (filters.request_state) params.set('request_state', filters.request_state);
    if (filters.approval_state) params.set('approval_state', filters.approval_state);
    if (filters.action_type) params.set('action_type', filters.action_type);
    params.set('include_expired', String(filters.include_expired));
    params.set('offset', String((filters.history_page - 1) * filters.page_size));
    params.set('limit', String(filters.page_size));
    params.set('recent_limit', String(filters.page_size));
    return params;
  }, [scope, filters]);

  const reviewParams = useMemo(() => {
    const params = new URLSearchParams();
    if (scope.deviceId || filters.device_id) params.set('device_id', scope.deviceId || filters.device_id);
    else if (filters.location_id) params.set('location_id', filters.location_id);
    else if (filters.customer_id) params.set('customer_id', filters.customer_id);
    else if (scope.locationId) params.set('location_id', scope.locationId);
    else if (scope.customerId) params.set('customer_id', scope.customerId);
    if (filters.license_id) params.set('license_id', filters.license_id);
    if (filters.request_state) params.set('request_state', filters.request_state);
    if (filters.approval_state || !canReviewRemoteActions) params.set('approval_state', filters.approval_state || 'pending');
    else params.set('approval_state', 'pending');
    if (filters.action_type) params.set('action_type', filters.action_type);
    params.set('include_expired', String(filters.include_expired));
    params.set('offset', String((filters.review_page - 1) * filters.page_size));
    params.set('limit', String(filters.page_size));
    return params;
  }, [scope, filters, canReviewRemoteActions]);

  const fetchAll = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setRefreshing(silent);
    setError(null);
    try {
      const requests = [
        axios.get(`${apiBase}/remote-actions/overview?${overviewParams.toString()}`, { headers: authHeaders }),
        axios.get(`${apiBase}/remote-actions/review-queue?${reviewParams.toString()}`, { headers: authHeaders }),
      ];
      if (scope.deviceId || filters.device_id) {
        requests.push(
          axios.get(`${apiBase}/remote-actions/${scope.deviceId || filters.device_id}/history?limit=${filters.page_size}`, { headers: authHeaders })
        );
      }
      const [overviewRes, reviewRes, deviceHistoryRes] = await Promise.all(requests);
      setOverview(overviewRes.data);
      setReviewQueue(reviewRes.data);
      setDeviceHistory(deviceHistoryRes?.data || null);
    } catch (err) {
      const status = err?.response?.status;
      if (status === 403) setError('Zugriff verweigert');
      else if (status === 502) setError('Zentraler Server nicht erreichbar');
      else setError(err?.response?.data?.detail || err.message || 'Laden fehlgeschlagen');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [apiBase, authHeaders, overviewParams, reviewParams, scope.deviceId, filters.device_id, filters.page_size]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    const interval = setInterval(() => fetchAll({ silent: true }), 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleReview = async (item, decision) => {
    if (!canReviewRemoteActions) return;
    const note = window.prompt(
      decision === 'approve' ? 'Freigabe-Notiz (optional)' : 'Ablehnungsgrund (optional)',
      ''
    );
    if (note === null) return;

    setReviewingId(item.id);
    try {
      await axios.post(
        `${apiBase}/remote-actions/${item.id}/review`,
        { decision, review_note: note || undefined },
        { headers: { ...authHeaders, 'Content-Type': 'application/json' } }
      );
      toast.success(decision === 'approve' ? 'Aktion freigegeben' : 'Aktion abgelehnt');
      fetchAll({ silent: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Review fehlgeschlagen');
    } finally {
      setReviewingId(null);
    }
  };

  const openFilteredRemoteActions = useCallback((nextFilters) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(nextFilters).forEach(([key, value]) => {
      if (value === '' || value == null) next.delete(key);
      else next.set(key, String(value));
    });
    next.set('review_page', '1');
    next.set('history_page', '1');
    navigate(`/operator/remote-actions?${next.toString()}`);
  }, [navigate, searchParams]);

  if (loading) {
    return <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" /></div>;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center text-red-400" data-testid="remote-actions-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
        <p>{error}</p>
      </div>
    );
  }

  const metrics = overview?.queue_metrics || reviewQueue?.queue_metrics || {};
  const summaryCounts = overview?.summary?.counts || deviceHistory?.summary?.counts || {};
  const recentSource = (scope.deviceId || filters.device_id) ? (deviceHistory?.items || []) : (overview?.recent_items || []);
  const recentItems = sortItems(recentSource, filters.sort);
  const pendingItems = sortItems(reviewQueue?.items || [], filters.sort);
  const historyWindow = overview?.window || { returned: recentItems.length, has_more: false };
  const reviewWindow = reviewQueue?.window || { returned: pendingItems.length, has_more: false };
  const activeScopeLabel = scope.deviceId || filters.device_id
    ? `Gerät ${scope.deviceId || filters.device_id}`
    : filters.license_id
      ? `Lizenz ${filters.license_id}`
      : filters.location_id
        ? `Standort ${filters.location_id}`
        : filters.customer_id
          ? `Kunde ${filters.customer_id}`
          : scope.locationId
            ? 'Aktueller Standort-Scope'
            : scope.customerId
              ? 'Aktueller Kunden-Scope'
              : 'Alle sichtbaren Standorte';

  return (
    <>
      <div className="space-y-5" data-testid="operator-remote-actions">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-bold text-white">Remote Actions</h1>
            <p className="text-sm text-zinc-500 mt-0.5">Triage, Review und Verlauf für zentrale Fernaktionen</p>
          </div>
          <button
            onClick={() => fetchAll({ silent: true })}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors text-sm"
            data-testid="remote-actions-refresh-btn"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Aktualisieren
          </button>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
          <div>
            <p className="text-xs uppercase tracking-wider text-zinc-500">Aktiver Scope</p>
            <p className="text-sm text-zinc-200 mt-1">{activeScopeLabel}</p>
          </div>
          {(filters.customer_id || filters.location_id || filters.device_id || filters.license_id || filters.request_state || filters.approval_state || filters.action_type || !filters.include_expired) && (
            <button
              onClick={() => setSearchParams(new URLSearchParams())}
              className="px-3 py-1.5 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-800"
              data-testid="remote-actions-clear-all"
            >
              Alle Deep-Links & Filter zurücksetzen
            </button>
          )}
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <MetricCard icon={Clock3} label="Pending Review" value={summaryCounts.pending_approval ?? 0} sub="manuelle Entscheidungen" tone={(summaryCounts.pending_approval ?? 0) > 0 ? 'amber' : 'zinc'} />
          <MetricCard icon={Send} label="Pending Delivery" value={summaryCounts.pending_delivery ?? 0} sub="freigegeben, wartet auf Gerät" tone={(summaryCounts.pending_delivery ?? 0) > 0 ? 'blue' : 'zinc'} />
          <MetricCard icon={CheckCircle2} label="Erfolgreich" value={summaryCounts.succeeded ?? 0} sub={`${summaryCounts.completed ?? 0} completed`} tone="emerald" />
          <MetricCard icon={XCircle} label="Blockiert / Refused" value={(summaryCounts.refused ?? 0) + (summaryCounts.failed ?? 0) + (summaryCounts.expired ?? 0)} sub={`${summaryCounts.expired ?? 0} expired`} tone={(summaryCounts.refused ?? 0) + (summaryCounts.failed ?? 0) + (summaryCounts.expired ?? 0) > 0 ? 'red' : 'zinc'} />
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3 space-y-3" data-testid="remote-actions-filters">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="inline-flex items-center gap-2 text-xs text-zinc-500"><Filter className="w-3.5 h-3.5" /> Filter & Ergonomie</div>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 px-2.5 py-1.5 text-xs text-zinc-500">
                <ArrowUpDown className="w-3.5 h-3.5" />
                <select
                  value={filters.sort}
                  onChange={(e) => setParamState({ sort: e.target.value })}
                  className="bg-transparent text-zinc-300 outline-none"
                  data-testid="remote-actions-sort"
                >
                  {SORT_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
              </div>
              <div className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 px-2.5 py-1.5 text-xs text-zinc-500">
                <select
                  value={filters.page_size}
                  onChange={(e) => setParamState({ page_size: e.target.value })}
                  className="bg-transparent text-zinc-300 outline-none"
                  data-testid="remote-actions-page-size"
                >
                  {PAGE_SIZE_OPTIONS.map((size) => <option key={size} value={size}>{size} / Seite</option>)}
                </select>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <select
              value={filters.request_state}
              onChange={(e) => setParamState({ request_state: e.target.value })}
              className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-300"
              data-testid="remote-actions-filter-state"
            >
              {REQUEST_STATE_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <select
              value={filters.approval_state}
              onChange={(e) => setParamState({ approval_state: e.target.value })}
              className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-300"
              data-testid="remote-actions-filter-approval"
            >
              {APPROVAL_STATE_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <select
              value={filters.action_type}
              onChange={(e) => setParamState({ action_type: e.target.value })}
              className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-300"
              data-testid="remote-actions-filter-type"
            >
              {ACTION_TYPE_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <label className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-zinc-800 text-sm text-zinc-300">
              <input
                type="checkbox"
                checked={filters.include_expired}
                onChange={(e) => setParamState({ include_expired: e.target.checked ? 'true' : false })}
                className="rounded border-zinc-700 bg-zinc-900"
                data-testid="remote-actions-filter-include-expired"
              />
              Expired einbeziehen
            </label>
            {(filters.request_state || filters.approval_state || filters.action_type || !filters.include_expired) && (
              <button
                onClick={() => setParamState({ request_state: '', approval_state: '', action_type: '', include_expired: 'true' })}
                className="px-3 py-1.5 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-800"
                data-testid="remote-actions-clear-filters"
              >
                Zurücksetzen
              </button>
            )}
          </div>
          {(filters.customer_id || filters.location_id || filters.device_id || filters.license_id) && (
            <div className="flex items-center gap-3 flex-wrap rounded-lg border border-indigo-500/20 bg-indigo-500/5 px-3 py-2 text-sm text-indigo-200">
              <Search className="w-4 h-4 text-indigo-400" />
              {filters.customer_id && <span>Deep-Link auf Kunde: <span className="font-mono text-xs">{filters.customer_id}</span></span>}
              {filters.location_id && <span>Deep-Link auf Standort: <span className="font-mono text-xs">{filters.location_id}</span></span>}
              {filters.device_id && <span>Deep-Link auf Gerät: <span className="font-mono text-xs">{filters.device_id}</span></span>}
              {filters.license_id && <span>Deep-Link auf Lizenz: <span className="font-mono text-xs">{filters.license_id}</span></span>}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <section className="rounded-xl border border-zinc-800 overflow-hidden" data-testid="remote-actions-review-queue">
            <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-900/60 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-white">Review Queue</h2>
                <p className="text-xs text-zinc-500 mt-0.5">Aktionen mit Freigabepflicht</p>
              </div>
              <span className="text-xs text-zinc-500">{reviewWindow.returned || pendingItems.length} Einträge</span>
            </div>
            <div className="divide-y divide-zinc-800/60">
              {pendingItems.length === 0 && (
                <div className="p-6 text-center text-zinc-500 text-sm">Keine offenen Reviews im aktuellen Scope.</div>
              )}
              {pendingItems.map((item) => (
                <div key={item.id} className="p-4 bg-zinc-950/30">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-medium text-white">{item.scope?.device_name || item.device_id?.slice(0, 8) || 'Gerät'}</p>
                        <StatePill state={item.request_state} approvalState={item.approval_state} outcomeCode={item.outcome_code} />
                      </div>
                      <p className="text-xs text-zinc-500 mt-1">{item.action_type} · von {item.issued_by || '—'} · {formatDateTime(item.issued_at)}</p>
                      {item.scope?.location_name && <p className="text-xs text-zinc-600 mt-1">{item.scope.location_name}{item.scope?.customer_name ? ` · ${item.scope.customer_name}` : ''}</p>}
                      {(item.result_message || item.outcome_detail || item.review_note) && (
                        <p className="text-xs text-zinc-400 mt-2 break-words">{item.review_note || item.result_message || item.outcome_detail}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => setSelectedAction(item)}
                        className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                        data-testid={`inspect-remote-action-${item.id}`}
                      >
                        <Eye className="w-3.5 h-3.5" /> Details
                      </button>
                      {canReviewRemoteActions && (
                        <>
                          <button
                            onClick={() => handleReview(item, 'approve')}
                            disabled={reviewingId === item.id}
                            className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-60"
                            data-testid={`approve-remote-action-${item.id}`}
                          >
                            <ShieldCheck className="w-3.5 h-3.5" /> Freigeben
                          </button>
                          <button
                            onClick={() => handleReview(item, 'refuse')}
                            disabled={reviewingId === item.id}
                            className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-60"
                            data-testid={`refuse-remote-action-${item.id}`}
                          >
                            <ShieldX className="w-3.5 h-3.5" /> Ablehnen
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <PageControls
              page={filters.review_page}
              hasMore={Boolean(reviewWindow.has_more)}
              returned={reviewWindow.returned || pendingItems.length}
              pageSize={filters.page_size}
              onPrev={() => setParamState({ review_page: Math.max(1, filters.review_page - 1), history_page: filters.history_page }, { replace: true })}
              onNext={() => setParamState({ review_page: filters.review_page + 1, history_page: filters.history_page }, { replace: true })}
              label="Review Queue"
              tidPrefix="remote-actions-review-page"
            />
          </section>

          <section className="rounded-xl border border-zinc-800 overflow-hidden" data-testid="remote-actions-history">
            <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-900/60 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-white flex items-center gap-2"><History className="w-4 h-4 text-zinc-400" />Letzte Aktionen</h2>
                <p className="text-xs text-zinc-500 mt-0.5">Operator-tauglicher Verlauf mit Scope-Kontext</p>
              </div>
              <span className="text-xs text-zinc-500">{historyWindow.returned || recentItems.length} sichtbar</span>
            </div>
            <div className="divide-y divide-zinc-800/60">
              {recentItems.length === 0 && (
                <div className="p-6 text-center text-zinc-500 text-sm">Noch keine Remote Actions im aktuellen Scope.</div>
              )}
              {recentItems.map((item) => (
                <div key={item.id} className="p-4 bg-zinc-950/20">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-medium text-white">{item.action_type}</p>
                        <StatePill state={item.request_state} approvalState={item.approval_state} outcomeCode={item.outcome_code} />
                      </div>
                      <p className="text-xs text-zinc-400 mt-1">{item.scope?.device_name || item.device_id?.slice(0, 8) || 'Gerät'} · {item.scope?.location_name || 'ohne Standort'} </p>
                      <p className="text-xs text-zinc-600 mt-1">Issued {timeAgo(item.issued_at)} · {item.issued_by || '—'}{item.reviewed_by ? ` · reviewed by ${item.reviewed_by}` : ''}</p>
                      {(item.result_message || item.outcome_detail) && (
                        <p className="text-xs text-zinc-500 mt-2 break-words">{item.result_message || item.outcome_detail}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right text-xs text-zinc-600 min-w-[120px]">
                        <div>{formatDateTime(item.issued_at)}</div>
                        {item.finalized_at && <div className="mt-1">Finalisiert: {formatDateTime(item.finalized_at)}</div>}
                      </div>
                      <button
                        onClick={() => setSelectedAction(item)}
                        className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                        data-testid={`history-remote-action-${item.id}`}
                      >
                        <Eye className="w-3.5 h-3.5" /> Details
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {!(scope.deviceId || filters.device_id) && (
              <PageControls
                page={filters.history_page}
                hasMore={Boolean(historyWindow.has_more)}
                returned={historyWindow.returned || recentItems.length}
                pageSize={filters.page_size}
                onPrev={() => setParamState({ history_page: Math.max(1, filters.history_page - 1), review_page: filters.review_page }, { replace: true })}
                onNext={() => setParamState({ history_page: filters.history_page + 1, review_page: filters.review_page }, { replace: true })}
                label="History"
                tidPrefix="remote-actions-history-page"
              />
            )}
          </section>
        </div>

        {overview?.location_summaries?.length > 0 && !(scope.deviceId || filters.device_id) && (
          <section className="rounded-xl border border-zinc-800 overflow-hidden" data-testid="remote-actions-location-summary">
            <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-900/60">
              <h2 className="text-sm font-semibold text-white">Triage nach Standort</h2>
              <p className="text-xs text-zinc-500 mt-0.5">Wo gerade Approval- oder Delivery-Druck entsteht</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-zinc-950/60 text-zinc-500 text-left text-xs uppercase tracking-wider">
                    <th className="px-4 py-2.5 font-medium">Standort</th>
                    <th className="px-4 py-2.5 font-medium">Pending Review</th>
                    <th className="px-4 py-2.5 font-medium">Pending Delivery</th>
                    <th className="px-4 py-2.5 font-medium">Expired</th>
                    <th className="px-4 py-2.5 font-medium">Refused</th>
                    <th className="px-4 py-2.5 font-medium text-right">Aktion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {overview.location_summaries.slice(0, 12).map((row) => (
                    <tr key={row.group_id} className="text-zinc-300 hover:bg-zinc-900/30">
                      <td className="px-4 py-2.5 font-medium">{row.group_name}</td>
                      <td className="px-4 py-2.5">{row.summary?.counts?.pending_approval ?? 0}</td>
                      <td className="px-4 py-2.5">{row.summary?.counts?.pending_delivery ?? 0}</td>
                      <td className="px-4 py-2.5">{row.summary?.counts?.expired ?? 0}</td>
                      <td className="px-4 py-2.5">{row.summary?.counts?.refused ?? 0}</td>
                      <td className="px-4 py-2.5 text-right">
                        <button
                          onClick={() => openFilteredRemoteActions({ location_id: row.group_id, device_id: '', license_id: '' })}
                          className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-indigo-300 hover:bg-indigo-500/10"
                        >
                          Öffnen <ExternalLink className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>

      <Dialog open={Boolean(selectedAction)} onOpenChange={(open) => !open && setSelectedAction(null)}>
        <DialogContent className="max-w-2xl border-zinc-800 bg-zinc-950 text-zinc-100">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-white">
              {selectedAction?.action_type || 'Remote Action'}
              <StatePill state={selectedAction?.request_state} approvalState={selectedAction?.approval_state} outcomeCode={selectedAction?.outcome_code} />
            </DialogTitle>
            <DialogDescription className="text-zinc-500">
              Scope, Lifecycle und Audit-Metadaten für diese Aktion.
            </DialogDescription>
          </DialogHeader>
          {selectedAction && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <DetailField label="Action ID" value={selectedAction.id} mono />
                <DetailField label="Gerät" value={selectedAction.scope?.device_name || selectedAction.device_id} mono={!selectedAction.scope?.device_name} />
                <DetailField label="Standort" value={selectedAction.scope?.location_name || '—'} />
                <DetailField label="Kunde" value={selectedAction.scope?.customer_name || '—'} />
                <DetailField label="License" value={selectedAction.scope?.license_id || '—'} mono={Boolean(selectedAction.scope?.license_id)} />
                <DetailField label="Issued by" value={selectedAction.issued_by || '—'} />
                <DetailField label="Issued at" value={formatDateTime(selectedAction.issued_at)} />
                <DetailField label="Reviewed at" value={formatDateTime(selectedAction.reviewed_at)} />
                <DetailField label="Finalized at" value={formatDateTime(selectedAction.finalized_at)} />
                <DetailField label="Expires at" value={formatDateTime(selectedAction.expires_at)} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                <DetailField label="Approval State" value={selectedAction.approval_state || '—'} />
                <DetailField label="Outcome Code" value={selectedAction.outcome_code || '—'} />
                <DetailField label="Risk" value={selectedAction.risk_level || selectedAction.detail_level || '—'} />
              </div>
              {(selectedAction.request_note || selectedAction.review_note || selectedAction.result_message || selectedAction.outcome_detail) && (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3 text-sm">
                  {selectedAction.request_note && <DetailBlock label="Request Note" value={selectedAction.request_note} />}
                  {selectedAction.review_note && <DetailBlock label="Review Note" value={selectedAction.review_note} />}
                  {selectedAction.result_message && <DetailBlock label="Result" value={selectedAction.result_message} />}
                  {selectedAction.outcome_detail && <DetailBlock label="Outcome Detail" value={selectedAction.outcome_detail} />}
                </div>
              )}
              {'params' in selectedAction && selectedAction.params != null && (
                <div className="rounded-xl border border-zinc-800 bg-black/30 p-4">
                  <p className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Params</p>
                  <pre className="text-xs text-zinc-300 whitespace-pre-wrap break-words">{JSON.stringify(selectedAction.params, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function DetailField({ label, value, mono = false }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 px-3 py-2.5">
      <p className="text-xs uppercase tracking-wider text-zinc-500">{label}</p>
      <p className={`mt-1 text-sm text-zinc-200 break-all ${mono ? 'font-mono text-xs' : ''}`}>{value || '—'}</p>
    </div>
  );
}

function DetailBlock({ label, value }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wider text-zinc-500 mb-1">{label}</p>
      <p className="text-sm text-zinc-200 break-words">{value}</p>
    </div>
  );
}

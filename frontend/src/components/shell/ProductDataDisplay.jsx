import { AlertTriangle, CircleSlash, Loader2, Search, Wifi, WifiOff, Shield, Ban, CheckCircle2, Clock3, KeyRound, Link2, Unplug, Activity } from 'lucide-react';

const BADGE_TONES = {
  neutral: 'border-zinc-700 bg-zinc-900/70 text-zinc-300',
  muted: 'border-zinc-800 bg-zinc-950/70 text-zinc-500',
  blue: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
  emerald: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
  amber: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
  red: 'border-red-500/20 bg-red-500/10 text-red-300',
  violet: 'border-violet-500/20 bg-violet-500/10 text-violet-300',
};

const STATUS_META = {
  connectivity: {
    online: { label: 'Online', tone: 'emerald', icon: Wifi },
    degraded: { label: 'Instabil', tone: 'amber', icon: Activity },
    offline: { label: 'Offline', tone: 'muted', icon: WifiOff },
  },
  device: {
    active: { label: 'Aktiv', tone: 'emerald', icon: CheckCircle2 },
    blocked: { label: 'Gesperrt', tone: 'red', icon: Ban },
    disabled: { label: 'Deaktiviert', tone: 'muted', icon: CircleSlash },
  },
  binding: {
    bound: { label: 'Gebunden', tone: 'emerald', icon: Link2 },
    mismatch: { label: 'Mismatch', tone: 'amber', icon: AlertTriangle },
    unbound: { label: 'Ungebunden', tone: 'muted', icon: Unplug },
  },
  license: {
    active: { label: 'Aktiv', tone: 'emerald', icon: CheckCircle2 },
    grace: { label: 'Toleranz', tone: 'amber', icon: Clock3 },
    expired: { label: 'Abgelaufen', tone: 'red', icon: AlertTriangle },
    blocked: { label: 'Gesperrt', tone: 'red', icon: Ban },
    test: { label: 'Test', tone: 'blue', icon: Shield },
    deactivated: { label: 'Deaktiviert', tone: 'muted', icon: CircleSlash },
    archived: { label: 'Archiviert', tone: 'muted', icon: CircleSlash },
  },
  token: {
    active: { label: 'Token aktiv', tone: 'blue', icon: KeyRound },
    missing: { label: 'Kein Token', tone: 'muted', icon: KeyRound },
    expired: { label: 'Token abgelaufen', tone: 'amber', icon: AlertTriangle },
    revoked: { label: 'Token widerrufen', tone: 'amber', icon: Ban },
    consumed: { label: 'Token verwendet', tone: 'emerald', icon: CheckCircle2 },
  },
};

export function getProductStatusMeta(kind, value, fallbackLabel = '—') {
  const normalized = value == null || value === '' ? null : String(value);
  const meta = STATUS_META[kind]?.[normalized] || null;
  if (meta) return meta;
  return { label: normalized || fallbackLabel, tone: 'neutral', icon: null };
}

export function ProductStatusBadge({ kind, value, label, className = '' }) {
  const meta = getProductStatusMeta(kind, value, label);
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${BADGE_TONES[meta.tone] || BADGE_TONES.neutral} ${className}`.trim()}>
      {Icon ? <Icon className="h-3.5 w-3.5" /> : null}
      {label || meta.label}
    </span>
  );
}

export function ProductPageState({
  kind = 'empty',
  icon: Icon,
  title,
  description,
  action,
  secondaryAction,
  compact = false,
  'data-testid': testId,
}) {
  const config = {
    loading: { icon: Loader2, tone: 'text-sky-300', card: 'border-sky-500/20 bg-sky-500/6' },
    error: { icon: AlertTriangle, tone: 'text-red-300', card: 'border-red-500/20 bg-red-500/6' },
    empty: { icon: CircleSlash, tone: 'text-zinc-500', card: 'border-zinc-800 bg-zinc-950/30' },
    filtered: { icon: Search, tone: 'text-amber-300', card: 'border-amber-500/20 bg-amber-500/6' },
  }[kind];

  const StateIcon = Icon || config.icon;

  return (
    <div data-testid={testId} className={`rounded-2xl border ${config.card} ${compact ? 'p-5' : 'p-8'} text-center`}>
      <div className={`mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-black/20 ${config.tone}`}>
        <StateIcon className={`h-6 w-6 ${kind === 'loading' ? 'animate-spin' : ''}`} />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-white">{title}</h3>
      {description ? <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-zinc-400">{description}</p> : null}
      {(action || secondaryAction) ? <div className="mt-5 flex flex-wrap items-center justify-center gap-3">{action}{secondaryAction}</div> : null}
    </div>
  );
}

export function ProductFilterSummary({ label = 'Scope', items = [], 'data-testid': testId }) {
  if (!items.length) return null;
  return (
    <div data-testid={testId} className="flex flex-wrap items-center gap-2 rounded-2xl border border-zinc-800 bg-zinc-950/40 px-3 py-2.5 text-xs text-zinc-400">
      <span className="uppercase tracking-[0.18em] text-zinc-500">{label}</span>
      {items.map((item) => (
        <span key={`${item.key}-${item.value}`} className="inline-flex items-center gap-1 rounded-full border border-zinc-700 bg-zinc-900/70 px-2.5 py-1 text-zinc-300">
          <span className="text-zinc-500">{item.key}:</span> {item.value}
        </span>
      ))}
    </div>
  );
}

export function ProductDataTable({ columns, children, className = '', 'data-testid': testId }) {
  return (
    <div className={`overflow-x-auto ${className}`.trim()}>
      <table className="w-full text-sm" data-testid={testId}>
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-950/40 text-left text-xs text-zinc-500">
            {columns.map((column) => (
              <th key={column.key} className={`px-4 py-3 font-medium ${column.className || ''}`.trim()}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/60">{children}</tbody>
      </table>
    </div>
  );
}

export function ProductSummaryRows({ rows, columns = 2, 'data-testid': testId }) {
  return (
    <div data-testid={testId} className={`grid gap-3 ${columns === 1 ? 'grid-cols-1' : columns === 3 ? 'grid-cols-1 md:grid-cols-3' : 'grid-cols-1 md:grid-cols-2'}`}>
      {rows.map((row) => (
        <div key={row.label} className="rounded-2xl border border-zinc-800 bg-zinc-950/30 px-4 py-3">
          <p className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">{row.label}</p>
          <p className="mt-1 text-sm font-medium text-white">{row.value}</p>
          {row.hint ? <p className="mt-1 text-xs text-zinc-500">{row.hint}</p> : null}
        </div>
      ))}
    </div>
  );
}

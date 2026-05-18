import { ArrowLeft, ArrowRight, Sparkles } from 'lucide-react';
import { Button } from '../ui/button';

const TONE_MAP = {
  neutral: 'border-zinc-800 bg-zinc-950/40 text-zinc-200',
  blue: 'border-sky-500/20 bg-sky-500/8 text-sky-100',
  amber: 'border-amber-500/20 bg-amber-500/8 text-amber-100',
  emerald: 'border-emerald-500/20 bg-emerald-500/8 text-emerald-100',
  red: 'border-red-500/20 bg-red-500/8 text-red-100',
  violet: 'border-violet-500/20 bg-violet-500/8 text-violet-100',
};

export function ProductBackLink({ label = 'Zurück', onClick, className = '', 'data-testid': testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`inline-flex items-center gap-2 text-sm text-zinc-400 transition hover:text-white ${className}`.trim()}
    >
      <ArrowLeft className="h-4 w-4" />
      {label}
    </button>
  );
}

export function ProductHero({ eyebrow, title, description, badge, callout, actions, backAction, tone = 'neutral', children, 'data-testid': testId }) {
  return (
    <section data-testid={testId} className={`rounded-[1.75rem] border p-5 md:p-6 ${TONE_MAP[tone] || TONE_MAP.neutral}`}>
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3">
            {backAction}
            {eyebrow ? <p className="section-eyebrow">{eyebrow}</p> : null}
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-semibold tracking-tight text-white md:text-3xl">{title}</h2>
              {badge}
            </div>
            {description ? <p className="max-w-3xl text-sm text-zinc-400 md:text-[15px]">{description}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>

        {callout ? <ProductCallout {...callout} /> : null}
        {children}
      </div>
    </section>
  );
}

export function ProductCallout({ tone = 'neutral', eyebrow = 'Advisory', title, description, actions, icon: Icon = Sparkles, 'data-testid': testId }) {
  return (
    <div data-testid={testId} className={`rounded-2xl border px-4 py-4 ${TONE_MAP[tone] || TONE_MAP.neutral}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-black/20 p-2.5">
            <Icon className="h-4 w-4" />
          </div>
          <div>
            {eyebrow ? <p className="text-[11px] uppercase tracking-[0.18em] text-current/60">{eyebrow}</p> : null}
            <p className="mt-1 text-sm font-semibold text-white">{title}</p>
            {description ? <p className="mt-1 text-sm text-current/75">{description}</p> : null}
          </div>
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}

export function ProductMetricGrid({ children, columns = 'xl:grid-cols-4', className = '' }) {
  return <div className={`grid grid-cols-1 gap-3 sm:grid-cols-2 ${columns} ${className}`.trim()}>{children}</div>;
}

export function ProductDetailCard({ title, eyebrow, description, actions, children, 'data-testid': testId }) {
  return (
    <section data-testid={testId} className="rounded-3xl border border-zinc-800 bg-zinc-900/50 overflow-hidden">
      {(title || eyebrow || description || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-800 bg-zinc-950/40 px-5 py-4">
          <div>
            {eyebrow ? <p className="section-eyebrow">{eyebrow}</p> : null}
            {title ? <h3 className="mt-1 text-base font-semibold text-white">{title}</h3> : null}
            {description ? <p className="mt-1 text-sm text-zinc-500">{description}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function ProductKeyValueList({ items, columns = 1, 'data-testid': testId }) {
  return (
    <div data-testid={testId} className={`grid gap-x-6 gap-y-1 ${columns > 1 ? 'md:grid-cols-2' : 'grid-cols-1'}`}>
      {items.map((item) => (
        <div key={item.label} className="flex items-start justify-between gap-4 border-b border-zinc-800/50 py-2.5">
          <span className="text-sm text-zinc-500">{item.label}</span>
          <span data-testid={item.tid} className="text-right text-sm font-medium text-zinc-200">{item.value || '—'}</span>
        </div>
      ))}
    </div>
  );
}

export function ProductInlineActions({ items = [], mode = 'read-only', 'data-testid': testId }) {
  const modeLabel = {
    'read-only': 'Read-only actions',
    operator: 'Operator actions',
    admin: 'Admin actions',
  }[mode] || 'Actions';

  if (!items.length) return null;

  return (
    <div data-testid={testId} className="rounded-2xl border border-zinc-800 bg-zinc-950/30 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.18em] text-zinc-500">{modeLabel}</p>
        <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-zinc-400">{items.length}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.map((item) => {
          const content = (
            <>
              {item.label}
              {item.trailingIcon ? <item.trailingIcon className="h-3.5 w-3.5" /> : null}
            </>
          );
          if (item.href) {
            return (
              <Button key={item.label} variant={item.variant || 'outline'} size="sm" className={item.className} onClick={item.onClick}>
                {content}
              </Button>
            );
          }
          return (
            <Button key={item.label} variant={item.variant || 'outline'} size="sm" onClick={item.onClick} disabled={item.disabled} className={item.className}>
              {content}
            </Button>
          );
        })}
      </div>
    </div>
  );
}

export function ProductFocusList({ title, hint, items, empty, onOpen, accent = 'neutral', getMeta, getActionLabel = () => 'Öffnen', onAction, 'data-testid': testId }) {
  return (
    <div data-testid={testId} className={`rounded-2xl border p-4 ${TONE_MAP[accent] || TONE_MAP.neutral}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{title}</p>
          {hint ? <p className="mt-1 text-xs text-zinc-500">{hint}</p> : null}
        </div>
        <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-zinc-400">{items.length}</span>
      </div>
      <div className="mt-4 space-y-2">
        {items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-800 px-3 py-4 text-sm text-zinc-500">{empty}</div>
        ) : items.map((item) => (
          <div key={item.license_id || item.id} className="rounded-xl border border-zinc-800 bg-zinc-950/70 px-3 py-3">
            <button onClick={() => onOpen(item)} className="w-full text-left">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-white">{item.title || item.plan_type || item.name || 'Eintrag'} <span className="text-zinc-500 font-mono text-xs">{(item.license_id || item.id || '').slice(0, 8)}</span></p>
                  <p className="mt-1 text-xs text-zinc-400">{item.primary_message || item.description}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-zinc-600" />
              </div>
            </button>
            {(getMeta || onAction) ? (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {getMeta ? getMeta(item) : null}
                {onAction ? (
                  <button onClick={() => onAction(item)} className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 px-2.5 py-1 text-xs text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800">
                    {getActionLabel(item)} <ArrowRight className="h-3 w-3" />
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

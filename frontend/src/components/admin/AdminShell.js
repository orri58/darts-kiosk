import { ChevronRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';

const TONE_STYLES = {
  neutral: 'border-zinc-800 bg-zinc-900/85 text-zinc-200',
  amber: 'border-amber-500/20 bg-amber-500/10 text-amber-100',
  emerald: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-100',
  blue: 'border-blue-500/20 bg-blue-500/10 text-blue-100',
  red: 'border-red-500/20 bg-red-500/10 text-red-100',
  violet: 'border-violet-500/20 bg-violet-500/10 text-violet-100',
};

const ICON_STYLES = {
  neutral: 'bg-zinc-800 text-zinc-300',
  amber: 'bg-amber-500/15 text-amber-400',
  emerald: 'bg-emerald-500/15 text-emerald-400',
  blue: 'bg-blue-500/15 text-blue-400',
  red: 'bg-red-500/15 text-red-400',
  violet: 'bg-violet-500/15 text-violet-400',
};

const PILL_STYLES = {
  neutral: 'border-zinc-800 bg-zinc-900 text-zinc-400',
  amber: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  blue: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
  red: 'border-red-500/30 bg-red-500/10 text-red-400',
  violet: 'border-violet-500/30 bg-violet-500/10 text-violet-400',
};

export function AdminPage({ eyebrow = 'Operator Console', title, description, actions, children }) {
  return (
    <div className="space-y-6" data-testid="admin-page-shell">
      <div className="rounded-3xl border border-zinc-800 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.14),transparent_30%),linear-gradient(180deg,rgba(24,24,27,0.95),rgba(9,9,11,0.98))] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.35)] md:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <span className="inline-flex items-center rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-400">
              {eyebrow}
            </span>
            <div>
              <h1 className="text-3xl font-heading uppercase tracking-[0.08em] text-white md:text-4xl">{title}</h1>
              {description && (
                <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400 md:text-base">{description}</p>
              )}
            </div>
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
        </div>
      </div>
      {children}
    </div>
  );
}

export function AdminSection({ title, description, actions, children, className, contentClassName }) {
  return (
    <Card className={cn('overflow-hidden border-zinc-800 bg-zinc-950/60 shadow-[0_16px_48px_rgba(0,0,0,0.28)]', className)}>
      {(title || description || actions) && (
        <CardHeader className="border-b border-zinc-800/80 bg-zinc-900/55">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-1">
              {title ? <CardTitle className="text-lg text-white">{title}</CardTitle> : null}
              {description ? <p className="text-sm text-zinc-500">{description}</p> : null}
            </div>
            {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
          </div>
        </CardHeader>
      )}
      <CardContent className={cn('p-5 md:p-6', contentClassName)}>{children}</CardContent>
    </Card>
  );
}

export function AdminStatsGrid({ children, className }) {
  return <div className={cn('grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4', className)}>{children}</div>;
}

export function AdminStatCard({ icon: Icon, label, value, hint, tone = 'neutral', className }) {
  return (
    <div className={cn('rounded-2xl border p-4 shadow-[0_10px_30px_rgba(0,0,0,0.24)]', TONE_STYLES[tone] || TONE_STYLES.neutral, className)}>
      <div className="flex items-start gap-4">
        {Icon ? (
          <div className={cn('flex h-11 w-11 items-center justify-center rounded-2xl', ICON_STYLES[tone] || ICON_STYLES.neutral)}>
            <Icon className="h-5 w-5" />
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-500">{label}</p>
          <p className="mt-2 truncate text-3xl font-semibold text-white">{value}</p>
          {hint ? <p className="mt-1 text-sm text-zinc-500">{hint}</p> : null}
        </div>
      </div>
    </div>
  );
}

export function AdminStatusPill({ tone = 'neutral', children, className }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em]', PILL_STYLES[tone] || PILL_STYLES.neutral, className)}>
      {children}
    </span>
  );
}

export function AdminEmptyState({ icon: Icon, title, description, action, secondaryAction, className }) {
  return (
    <div className={cn('rounded-3xl border border-dashed border-zinc-800 bg-zinc-950/50 p-10 text-center', className)}>
      {Icon ? (
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-900 text-zinc-600">
          <Icon className="h-8 w-8" />
        </div>
      ) : null}
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      {description ? <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-zinc-500">{description}</p> : null}
      {(action || secondaryAction) && (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}

export function AdminLinkTile({ icon: Icon, title, description, href, onClick, tone = 'neutral', cta = 'Öffnen' }) {
  const Comp = href ? 'a' : 'button';
  const props = href ? { href } : { type: 'button', onClick };

  return (
    <Comp
      {...props}
      className={cn(
        'group flex w-full items-start gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4 text-left transition hover:border-amber-500/30 hover:bg-zinc-900',
        href && 'no-underline'
      )}
    >
      {Icon ? (
        <div className={cn('mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl', ICON_STYLES[tone] || ICON_STYLES.neutral)}>
          <Icon className="h-5 w-5" />
        </div>
      ) : null}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="font-medium text-white">{title}</p>
          <ChevronRight className="h-4 w-4 text-zinc-600 transition group-hover:translate-x-0.5 group-hover:text-amber-400" />
        </div>
        <p className="mt-1 text-sm leading-6 text-zinc-500">{description}</p>
        <p className="mt-3 text-xs font-semibold uppercase tracking-[0.24em] text-amber-400">{cta}</p>
      </div>
    </Comp>
  );
}

export function AdminMiniAction({ icon: Icon, children, onClick, variant = 'outline', className, ...props }) {
  return (
    <Button
      type="button"
      variant={variant}
      onClick={onClick}
      className={cn('border-zinc-700 text-zinc-300 hover:text-white', className)}
      {...props}
    >
      {Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </Button>
  );
}

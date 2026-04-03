import { ChevronRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';

const TONE_STYLES = {
  neutral: 'border-[rgb(var(--color-border-rgb)/0.84)] bg-[rgb(var(--color-surface-rgb)/0.86)] text-[var(--color-text)]',
  amber: 'border-[rgb(var(--color-primary-rgb)/0.22)] bg-[rgb(var(--color-primary-rgb)/0.12)] text-[rgb(var(--color-secondary-rgb)/0.98)]',
  emerald: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-100',
  blue: 'border-blue-500/20 bg-blue-500/10 text-blue-100',
  red: 'border-[rgb(var(--color-accent-rgb)/0.24)] bg-[rgb(var(--color-accent-rgb)/0.12)] text-[rgb(var(--color-text-rgb)/0.98)]',
  violet: 'border-violet-500/20 bg-violet-500/10 text-violet-100',
};

const ICON_STYLES = {
  neutral: 'bg-[rgb(var(--color-bg-rgb)/0.62)] text-[rgb(var(--color-text-rgb)/0.72)]',
  amber: 'bg-[rgb(var(--color-primary-rgb)/0.16)] text-[var(--color-primary)]',
  emerald: 'bg-emerald-500/15 text-emerald-400',
  blue: 'bg-blue-500/15 text-blue-400',
  red: 'bg-[rgb(var(--color-accent-rgb)/0.14)] text-[var(--color-accent)]',
  violet: 'bg-violet-500/15 text-violet-400',
};

const PILL_STYLES = {
  neutral: 'border-[rgb(var(--color-border-rgb)/0.8)] bg-[rgb(var(--color-bg-rgb)/0.56)] text-[var(--color-text-secondary)]',
  amber: 'border-[rgb(var(--color-primary-rgb)/0.28)] bg-[rgb(var(--color-primary-rgb)/0.12)] text-[var(--color-primary)]',
  emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  blue: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
  red: 'border-[rgb(var(--color-accent-rgb)/0.28)] bg-[rgb(var(--color-accent-rgb)/0.12)] text-[var(--color-accent)]',
  violet: 'border-violet-500/30 bg-violet-500/10 text-violet-400',
};

export function AdminPage({ eyebrow = 'Operator Console', title, description, actions, children }) {
  return (
    <div className="space-y-5" data-testid="admin-page-shell">
      <div className="rounded-[1.5rem] border border-[rgb(var(--color-border-rgb)/0.86)] bg-[linear-gradient(180deg,rgb(var(--color-surface-rgb)/0.94),rgb(var(--color-bg-rgb)/0.98))] p-4 shadow-[0_16px_44px_rgba(0,0,0,0.22)] md:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-3">
            <span className="inline-flex items-center rounded-full border border-[rgb(var(--color-primary-rgb)/0.2)] bg-[rgb(var(--color-primary-rgb)/0.08)] px-3 py-1 text-[11px] font-medium tracking-[0.14em] text-[var(--color-primary)]">
              {eyebrow}
            </span>
            <div className="min-w-0">
              <h1 className="break-words text-2xl font-heading text-[var(--color-text)] md:text-3xl">{title}</h1>
              {description && (
                <p className="mt-1 max-w-3xl break-words text-sm leading-6 text-[var(--color-text-secondary)] md:text-[15px]">{description}</p>
              )}
            </div>
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-3 lg:justify-end">{actions}</div> : null}
        </div>
      </div>
      {children}
    </div>
  );
}

export function AdminSection({ title, description, actions, children, className, contentClassName }) {
  return (
    <Card className={cn('overflow-hidden rounded-[1.5rem] border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.56)] shadow-[0_16px_48px_rgba(0,0,0,0.28)] backdrop-blur', className)}>
      {(title || description || actions) && (
        <CardHeader className="border-b border-[rgb(var(--color-border-rgb)/0.8)] bg-[rgb(var(--color-bg-rgb)/0.3)] px-5 py-4 md:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-1">
              {title ? <CardTitle className="break-words text-lg text-[var(--color-text)]">{title}</CardTitle> : null}
              {description ? <p className="break-words text-sm text-[var(--color-text-secondary)]">{description}</p> : null}
            </div>
            {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
          </div>
        </CardHeader>
      )}
      <CardContent className={cn('p-4 md:p-5', contentClassName)}>{children}</CardContent>
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
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--color-text-secondary)]">{label}</p>
          <p className="mt-2 break-words text-2xl font-semibold text-[var(--color-text)] sm:text-3xl">{value}</p>
          {hint ? <p className="mt-1 break-words text-sm text-[var(--color-text-secondary)]">{hint}</p> : null}
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
    <div className={cn('rounded-3xl border border-dashed border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.34)] p-8 text-center', className)}>
      {Icon ? (
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-[rgb(var(--color-bg-rgb)/0.64)] text-[var(--color-text-muted)]">
          <Icon className="h-8 w-8" />
        </div>
      ) : null}
      <h3 className="text-lg font-semibold text-[var(--color-text)]">{title}</h3>
      {description ? <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-[var(--color-text-secondary)]">{description}</p> : null}
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
        'border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.66)] hover:border-[rgb(var(--color-primary-rgb)/0.3)] hover:bg-[rgb(var(--color-surface-rgb)/0.86)]',
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
          <p className="break-words font-medium text-[var(--color-text)]">{title}</p>
          <ChevronRight className="h-4 w-4 text-[var(--color-text-muted)] transition group-hover:translate-x-0.5 group-hover:text-[var(--color-primary)]" />
          </div>
        <p className="mt-1 break-words text-sm leading-6 text-[var(--color-text-secondary)]">{description}</p>
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
      className={cn('border-[rgb(var(--color-border-rgb)/0.82)] text-[var(--color-text-secondary)] hover:border-[rgb(var(--color-primary-rgb)/0.24)] hover:bg-[rgb(var(--color-primary-rgb)/0.08)] hover:text-[var(--color-text)]', className)}
      {...props}
    >
      {Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </Button>
  );
}

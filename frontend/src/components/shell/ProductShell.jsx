import { NavLink } from 'react-router-dom';
import { LogOut, Menu, X } from 'lucide-react';

function SurfaceBadge({ children, tone = 'default' }) {
  const tones = {
    default: 'border-white/10 bg-white/5 text-zinc-300',
    amber: 'border-amber-500/25 bg-amber-500/10 text-amber-300',
    blue: 'border-sky-500/25 bg-sky-500/10 text-sky-300',
    emerald: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300',
    violet: 'border-violet-500/25 bg-violet-500/10 text-violet-300',
  };

  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium ${tones[tone] || tones.default}`}>{children}</span>;
}

export function ProductPageHeader({ eyebrow, title, description, actions, badge, align = 'between' }) {
  return (
    <div className={`product-page-header ${align === 'start' ? 'lg:items-start' : 'lg:items-center'} lg:flex-row`}>
      <div className="space-y-2">
        {eyebrow ? <p className="section-eyebrow">{eyebrow}</p> : null}
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-white md:text-3xl">{title}</h1>
          {badge}
        </div>
        {description ? <p className="max-w-3xl text-sm text-zinc-400 md:text-[15px]">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function ProductStatCard({ icon: Icon, label, value, hint, tone = 'default', onClick, 'data-testid': testId }) {
  const tones = {
    default: 'border-zinc-800 text-zinc-400',
    amber: 'border-amber-500/20 text-amber-300',
    blue: 'border-sky-500/20 text-sky-300',
    emerald: 'border-emerald-500/20 text-emerald-300',
    purple: 'border-violet-500/20 text-violet-300',
    red: 'border-red-500/20 text-red-300',
  };

  const content = (
    <>
      <div className="mb-2 flex items-center justify-between">
        {Icon ? <Icon className="h-4 w-4 opacity-80" /> : <span />}
      </div>
      <p className="text-2xl font-semibold text-white md:text-[28px]">{value}</p>
      <p className="mt-1 text-xs uppercase tracking-[0.18em] opacity-80">{label}</p>
      {hint ? <p className="mt-1 text-xs text-zinc-500">{hint}</p> : null}
    </>
  );

  if (onClick) {
    return (
      <button data-testid={testId} onClick={onClick} className={`product-stat-card text-left transition hover:border-zinc-700 ${tones[tone] || tones.default}`}>
        {content}
      </button>
    );
  }

  return <div data-testid={testId} className={`product-stat-card ${tones[tone] || tones.default}`}>{content}</div>;
}

export function ProductSection({ eyebrow, title, description, actions, children, 'data-testid': testId }) {
  return (
    <section className="product-section" data-testid={testId}>
      {(eyebrow || title || description || actions) && (
        <div className="product-section-header">
          <div className="space-y-1">
            {eyebrow ? <p className="section-eyebrow">{eyebrow}</p> : null}
            {title ? <h2 className="text-base font-semibold text-white md:text-lg">{title}</h2> : null}
            {description ? <p className="text-sm text-zinc-500">{description}</p> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}

export default function ProductShell({
  sidebarOpen,
  setSidebarOpen,
  mobileTitle,
  mobileSubtitle,
  brandEyebrow,
  brandTitle,
  sidebarBadge,
  sidebarHint,
  navSections,
  footer,
  topbar,
  children,
  testId = 'product-shell',
}) {
  return (
    <div className="product-shell" data-testid={testId}>
      <div className="product-shell__bg" />

      <div className="product-shell__mobile-header lg:hidden" data-testid={`${testId}-mobile-header`}>
        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 text-zinc-400 hover:text-white" data-testid={`${testId}-mobile-menu-btn`}>
          {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <div className="text-center">
          <p className="section-eyebrow">{mobileSubtitle}</p>
          <h1 className="text-base font-semibold tracking-tight text-white">{mobileTitle}</h1>
        </div>
        <div className="w-9" />
      </div>

      <aside className={`product-shell__sidebar ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}>
        <div className="product-shell__sidebar-brand">
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="section-eyebrow">{brandEyebrow}</p>
                <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">{brandTitle}</h1>
              </div>
              {sidebarBadge}
            </div>
            {sidebarHint ? <p className="text-sm text-zinc-400">{sidebarHint}</p> : null}
          </div>
        </div>

        <nav className="product-shell__nav" data-testid={`${testId}-nav`}>
          <div className="space-y-5">
            {navSections.map((section) => (
              <div key={section.label} className="space-y-2">
                <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.28em] text-zinc-500">{section.label}</p>
                <div className="space-y-1.5">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      end={item.exact}
                      onClick={() => setSidebarOpen(false)}
                      data-testid={item.tid}
                      className={({ isActive }) => `product-shell__nav-link ${isActive ? 'product-shell__nav-link--active' : 'product-shell__nav-link--idle'}`}
                    >
                      <div className="product-shell__nav-icon">
                        <item.icon className="h-4.5 w-4.5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{item.label}</span>
                        {item.description ? <span className="block truncate text-xs text-zinc-500">{item.description}</span> : null}
                      </div>
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </nav>

        <div className="product-shell__sidebar-footer">{footer}</div>
      </aside>

      {sidebarOpen ? <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={() => setSidebarOpen(false)} /> : null}

      <main className="product-shell__main">
        {topbar ? <div className="product-shell__topbar">{topbar}</div> : null}
        <div className="product-shell__content">{children}</div>
      </main>
    </div>
  );
}

export { SurfaceBadge };

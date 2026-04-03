import clsx from 'clsx';
import { useSettings } from '../../context/SettingsContext';

const SIZE_MAP = {
  sm: 'h-10 max-w-[96px] lg:h-12 lg:max-w-[120px]',
  md: 'h-14 max-w-[128px] lg:h-16 lg:max-w-[160px]',
  lg: 'h-20 max-w-[168px] lg:h-24 lg:max-w-[220px]',
};

export default function KioskHeader({ branding, eyebrow, title, subtitle, right, compact = false }) {
  const { kioskLayout } = useSettings();
  const header = kioskLayout?.header || {};
  const align = header.align === 'center' ? 'center' : 'left';
  const showLogo = header.show_logo !== false && Boolean(branding?.logo_url);
  const showTitle = header.show_title !== false;
  const showSubtitle = header.show_subtitle !== false;
  const sizeClass = SIZE_MAP[header.logo_size] || SIZE_MAP.md;

  return (
    <div className={clsx(
      'mx-auto flex w-full max-w-7xl rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.66)] backdrop-blur',
      compact ? 'px-4 py-3 lg:px-5' : 'px-4 py-4 lg:px-6'
    )}>
      <div className={clsx('flex w-full gap-4', align === 'center' ? 'flex-col items-center text-center' : 'items-center justify-between')}>
        <div className={clsx('min-w-0', align === 'center' ? 'flex flex-col items-center' : '')}>
          {eyebrow ? <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">{eyebrow}</p> : null}
          <div className={clsx('mt-1 flex min-w-0 gap-4', align === 'center' ? 'flex-col items-center' : 'items-center')}>
            {showLogo ? (
              <img
                src={branding.logo_url}
                alt={branding?.cafe_name || 'Venue logo'}
                className={clsx('w-auto object-contain drop-shadow-[0_8px_24px_rgba(0,0,0,0.28)]', sizeClass)}
              />
            ) : null}
            <div className="min-w-0">
              {showTitle ? (
                <h1 className="break-words text-xl font-heading tracking-[0.08em] text-[var(--color-text)] lg:text-2xl">
                  {title || branding?.cafe_name}
                </h1>
              ) : null}
              {showSubtitle && (subtitle || branding?.subtitle) ? (
                <p className="mt-1 break-words text-sm text-[var(--color-text-secondary)]">{subtitle || branding?.subtitle}</p>
              ) : null}
            </div>
          </div>
        </div>
        {right ? <div className={clsx('shrink-0', align === 'center' ? 'w-full flex justify-center' : '')}>{right}</div> : null}
      </div>
    </div>
  );
}

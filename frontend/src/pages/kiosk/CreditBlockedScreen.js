import { AlertTriangle, Coins, Phone, Users } from 'lucide-react';
import { Button } from '../../components/ui/button';

export default function CreditBlockedScreen({ branding, session, onCallStaff }) {
  const requiredUnits = Math.max(1, Number(session?.players_count || session?.players?.length || 1));
  const creditsAvailable = Math.max(0, Number(session?.credits_remaining || 0));
  const shortage = Math.max(0, requiredUnits - creditsAvailable);

  return (
    <div className="relative h-full w-full overflow-hidden bg-[var(--color-bg)]" data-testid="credit-blocked-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgb(var(--color-accent-rgb)/0.18),transparent_32%),linear-gradient(180deg,rgb(var(--color-bg-rgb)/0.96),var(--color-bg))]" />
      <div className="relative z-10 flex h-full items-center justify-center p-8">
        <div className="w-full max-w-4xl rounded-[2rem] border border-[rgb(var(--color-accent-rgb)/0.3)] bg-[rgb(var(--color-bg-rgb)/0.85)] p-8 shadow-[0_24px_80px_rgba(0,0,0,0.42)] backdrop-blur">
          <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-3xl border border-[rgb(var(--color-accent-rgb)/0.3)] bg-[rgb(var(--color-accent-rgb)/0.12)] text-[var(--color-accent)]">
            <AlertTriangle className="h-12 w-12" />
          </div>

          <div className="mt-8 text-center">
            <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-accent)]">Match pausiert</p>
            <h1 className="mt-3 text-4xl font-heading uppercase tracking-[0.08em] text-[var(--color-text)] md:text-5xl">
              Zu wenig Credits für dieses Match
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-[var(--color-text-secondary)] lg:text-lg lg:leading-8">
              Das Board bleibt lokal freigeschaltet. Der Matchstart wartet nur darauf, dass genug Credits nachgeladen werden.
            </p>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.66)] p-5">
              <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                <Users className="h-4 w-4 text-[var(--color-text-secondary)]" /> Autoritative Spieler
              </div>
              <p className="mt-4 text-5xl font-semibold text-[var(--color-text)]" data-testid="blocked-required-players">{requiredUnits}</p>
              <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Aus dem laufenden Match erkannt.</p>
            </div>

            <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.66)] p-5">
              <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                <Coins className="h-4 w-4 text-[var(--color-text-secondary)]" /> Verfügbare Credits
              </div>
              <p className="mt-4 text-5xl font-semibold text-[var(--color-text)]" data-testid="blocked-credits-available">{creditsAvailable}</p>
              <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Sobald genug Credits da sind, geht es automatisch weiter.</p>
            </div>

            <div className="rounded-3xl border border-[rgb(var(--color-accent-rgb)/0.3)] bg-[rgb(var(--color-accent-rgb)/0.12)] p-5">
              <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                <AlertTriangle className="h-4 w-4 text-[var(--color-accent)]" /> Fehlende Credits
              </div>
              <p className="mt-4 text-5xl font-semibold text-[var(--color-text)]" data-testid="blocked-credit-shortage">{shortage}</p>
              <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Bitte Personal informieren, damit die Session aufgeladen wird.</p>
            </div>
          </div>

          <div className="mt-8 rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.54)] px-6 py-5 text-center text-sm leading-7 text-[var(--color-text-secondary)]">
            {branding?.cafe_name || 'DartsKiosk'} wartet auf eine Freigabe am Tresen. Kein automatischer Abbruch,
            keine Doppelbelastung — der Start wird erst akzeptiert, wenn die Credits reichen.
          </div>

          {onCallStaff && (
            <div className="mt-6 flex justify-center">
              <Button
                onClick={onCallStaff}
                data-testid="blocked-call-staff-btn"
                className="h-16 rounded-3xl bg-[var(--color-primary)] px-8 text-lg text-[hsl(var(--primary-foreground))] hover:opacity-90"
              >
                <Phone className="mr-3 h-5 w-5" /> Personal rufen
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { AlertTriangle, Coins, Phone, ShieldAlert, Users } from 'lucide-react';
import { Button } from '../../components/ui/button';

export default function CreditBlockedScreen({ branding, session, onCallStaff }) {
  const requiredUnits = Math.max(1, Number(session?.players_count || session?.players?.length || 1));
  const creditsAvailable = Math.max(0, Number(session?.credits_remaining || 0));
  const shortage = Math.max(0, requiredUnits - creditsAvailable);
  const players = session?.players?.length ? session.players : [];

  return (
    <div className="relative h-full w-full overflow-hidden bg-[var(--color-bg)]" data-testid="credit-blocked-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgb(var(--color-accent-rgb)/0.18),transparent_32%),linear-gradient(180deg,rgb(var(--color-bg-rgb)/0.96),var(--color-bg))]" />
      <div className="relative z-10 flex h-full items-center justify-center p-6 lg:p-8">
        <div className="w-full max-w-6xl rounded-[2.25rem] border border-[rgb(var(--color-accent-rgb)/0.28)] bg-[rgb(var(--color-bg-rgb)/0.82)] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.42)] backdrop-blur lg:p-8">
          <div className="grid gap-6 lg:grid-cols-[1.1fr,0.9fr] lg:items-start">
            <div className="space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--color-accent-rgb)/0.28)] bg-[rgb(var(--color-accent-rgb)/0.12)] px-4 py-2 text-sm text-[var(--color-accent)]">
                <ShieldAlert className="h-4 w-4" /> Match wartet auf Freigabe
              </div>

              <div>
                <div className="flex items-center gap-4">
                  <div className="flex h-20 w-20 items-center justify-center rounded-[2rem] border border-[rgb(var(--color-accent-rgb)/0.28)] bg-[rgb(var(--color-accent-rgb)/0.12)] text-[var(--color-accent)]">
                    <AlertTriangle className="h-10 w-10" />
                  </div>
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Credit Guard</p>
                    <h1 className="text-4xl font-heading uppercase tracking-[0.08em] text-[var(--color-text)] md:text-5xl lg:text-6xl">
                      Zu wenig Credits
                    </h1>
                  </div>
                </div>
                <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--color-text-secondary)] lg:text-lg lg:leading-8">
                  Das Spiel wird nicht falsch gestartet und auch nicht doppelt belastet. Der Matchstart bleibt einfach sauber pausiert, bis genug Credits am Tresen nachgeladen wurden.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.66)] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.22)]">
                  <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                    <Users className="h-4 w-4" /> Autoritative Spieler
                  </div>
                  <p className="mt-4 text-5xl font-semibold text-[var(--color-text)]" data-testid="blocked-required-players">{requiredUnits}</p>
                  <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Erkannt aus dem laufenden Match.</p>
                </div>

                <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.66)] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.22)]">
                  <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                    <Coins className="h-4 w-4" /> Verfügbare Credits
                  </div>
                  <p className="mt-4 text-5xl font-semibold text-[var(--color-text)]" data-testid="blocked-credits-available">{creditsAvailable}</p>
                  <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Sobald genug Credits da sind, läuft es weiter.</p>
                </div>

                <div className="rounded-3xl border border-[rgb(var(--color-accent-rgb)/0.3)] bg-[rgb(var(--color-accent-rgb)/0.12)] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.22)]">
                  <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                    <AlertTriangle className="h-4 w-4 text-[var(--color-accent)]" /> Fehlende Credits
                  </div>
                  <p className="mt-4 text-5xl font-semibold text-[var(--color-text)]" data-testid="blocked-credit-shortage">{shortage}</p>
                  <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Das ist die noch nötige Nachbuchung.</p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-[2rem] border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.58)] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.22)]">
                <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Nächster sinnvoller Schritt</p>
                <p className="mt-3 text-base leading-7 text-[var(--color-text-secondary)]">
                  {branding?.cafe_name || 'DartsKiosk'} wartet auf eine Freigabe am Tresen. Keine Panik, kein Abbruch — nur eine saubere Nachladung.
                </p>
              </div>

              <div className="rounded-[2rem] border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.42)] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.18)]">
                <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Match-Kontext</p>
                {players.length > 0 ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {players.map((player, index) => (
                      <span key={`${player}-${index}`} className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.74)] bg-[rgb(var(--color-surface-rgb)/0.74)] px-4 py-2 text-sm font-medium text-[var(--color-text)]">
                        {player}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Spieler werden vom Matchstatus geliefert.</p>
                )}
              </div>

              {onCallStaff && (
                <Button
                  onClick={onCallStaff}
                  data-testid="blocked-call-staff-btn"
                  className="h-16 w-full rounded-3xl bg-[var(--color-primary)] text-lg text-[hsl(var(--primary-foreground))] hover:opacity-90"
                >
                  <Phone className="mr-3 h-5 w-5" /> Personal rufen
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

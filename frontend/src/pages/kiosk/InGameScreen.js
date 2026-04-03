import { useState, useEffect } from 'react';
import { Clock, Coins, Phone, StopCircle, Target, Users, Wallet } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { useSettings } from '../../context/SettingsContext';
import KioskHeader from '../../components/kiosk/KioskHeader';

export default function InGameScreen({ branding, session, onEndGame, onCallStaff }) {
  const [timeLeft, setTimeLeft] = useState(null);
  const [showConfirmEnd, setShowConfirmEnd] = useState(false);
  const { kioskTexts } = useSettings();

  useEffect(() => {
    if (session?.pricing_mode === 'per_time' && session?.expires_at) {
      const updateTime = () => {
        const expiresAt = new Date(session.expires_at);
        const now = new Date();
        const diff = Math.max(0, expiresAt - now);

        if (diff <= 0) {
          setTimeLeft({ minutes: 0, seconds: 0 });
          onEndGame();
          return;
        }

        setTimeLeft({
          minutes: Math.floor(diff / 60000),
          seconds: Math.floor((diff % 60000) / 1000),
        });
      };

      updateTime();
      const interval = setInterval(updateTime, 1000);
      return () => clearInterval(interval);
    }
  }, [session, onEndGame]);

  const formatTime = (time) => {
    if (!time) return '--:--';
    return `${String(time.minutes).padStart(2, '0')}:${String(time.seconds).padStart(2, '0')}`;
  };

  const dangerTime = timeLeft?.minutes < 5;
  const isTimeMode = session?.pricing_mode === 'per_time';
  const isCreditsMode = !isTimeMode;

  return (
    <div className="relative h-full w-full overflow-hidden bg-[var(--color-bg)]" data-testid="in-game-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.16),transparent_30%),linear-gradient(180deg,rgb(var(--color-bg-rgb)/0.96),var(--color-bg))]" />
      <div className="relative z-10 flex h-full flex-col px-4 py-4 lg:px-8 lg:py-6">
        <KioskHeader
          branding={branding}
          eyebrow="Live session"
          compact
          right={(
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
              <div className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
              {kioskTexts.game_running || 'SPIEL LÄUFT'}
            </div>
          )}
        />

        <div className="mx-auto grid w-full max-w-7xl flex-1 gap-5 py-5 lg:grid-cols-[1.2fr,0.8fr] lg:items-center lg:py-7">
          <div className="space-y-5">
            <div>
              <div className="flex items-center gap-3">
                <div className="flex h-14 w-14 items-center justify-center rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.72)] text-[var(--color-primary)] lg:h-16 lg:w-16">
                  <Target className="h-8 w-8" />
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Aktives Spiel</p>
                  <h2 className="text-4xl font-heading uppercase tracking-[0.08em] text-[var(--color-text)] md:text-5xl lg:text-6xl">{session?.game_type || 'DART'}</h2>
                </div>
              </div>
              <p className="mt-3 max-w-2xl text-base leading-7 text-[var(--color-text-secondary)] lg:text-lg lg:leading-8">
                Session läuft lokal auf diesem Board. Credits oder Zeit gehen erst bei echten Match-Events runter.
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.66)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                  <Users className="h-4 w-4 text-[var(--color-text-secondary)]" /> Spieler
                </div>
                <div className="mt-4 space-y-2">
                  {session?.players?.map((player, index) => (
                    <p key={index} className="truncate text-lg font-medium text-[var(--color-text)]">{player}</p>
                  )) || <p className="text-[var(--color-text-muted)]">-</p>}
                </div>
              </div>

              {isCreditsMode ? (
                <div className="rounded-3xl border border-[rgb(var(--color-primary-rgb)/0.28)] bg-[rgb(var(--color-primary-rgb)/0.12)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
                  <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                    <Coins className="h-4 w-4 text-[var(--color-primary)]" /> {kioskTexts.credits_label || 'Credits verfügbar'}
                  </div>
                  <p className="mt-3 text-4xl font-semibold text-[var(--color-text)] lg:text-5xl" data-testid="credits-remaining">{session?.credits_remaining || 0}</p>
                  <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
                    {session?.pricing_mode === 'per_player'
                      ? 'Matchstarts ziehen später je nach echter Spielerzahl Credits ab'
                      : `von ${session?.credits_total || 0} gekauft`}
                  </p>
                </div>
              ) : (
                <div className={`rounded-3xl border p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)] ${dangerTime ? 'border-red-500/30 bg-red-500/10' : 'border-amber-500/30 bg-amber-500/10'}`}>
                  <div className="flex items-center gap-2 text-sm text-zinc-200/70">
                    <Clock className={`h-4 w-4 ${dangerTime ? 'text-red-400' : 'text-amber-400'}`} /> {kioskTexts.time_label || 'Zeit übrig'}
                  </div>
                  <p className={`mt-4 text-5xl font-semibold text-white ${dangerTime ? 'animate-pulse' : ''}`} data-testid="time-remaining">{formatTime(timeLeft)}</p>
                  <p className="mt-2 text-sm text-zinc-300/70">Automatisches Session-Ende bei 00:00</p>
                </div>
              )}

              <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.66)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                  <Wallet className="h-4 w-4 text-[var(--color-text-secondary)]" /> Tarif
                </div>
                <p className="mt-3 text-3xl font-semibold text-[var(--color-text)]">{isTimeMode ? `${session?.minutes_total || 0} min` : `${session?.credits_total || 0} Credits`}</p>
                <p className="mt-1 text-lg text-[var(--color-text-secondary)]">{session?.price_total?.toFixed(2)} €</p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.58)] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
              <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Lokale Aktionen</p>
              <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                Alles hier greift nur lokal und nachvollziehbar ein.
              </p>
            </div>

            {onCallStaff && (
              <Button
                onClick={onCallStaff}
                data-testid="call-staff-btn"
                variant="outline"
                className="h-20 w-full rounded-3xl border-2 border-[rgb(var(--color-border-rgb)/0.82)] bg-transparent text-lg text-[var(--color-text)] hover:border-[rgb(var(--color-primary-rgb)/0.34)] hover:text-[var(--color-primary)]"
              >
                <Phone className="w-6 h-6 mr-3" />
                {kioskTexts.call_staff || 'Personal rufen'}
              </Button>
            )}

            {!showConfirmEnd ? (
              <Button
                onClick={() => setShowConfirmEnd(true)}
                data-testid="end-game-btn"
                className="h-20 w-full rounded-3xl border-2 border-[rgb(var(--color-accent-rgb)/0.35)] bg-[rgb(var(--color-accent-rgb)/0.12)] text-lg text-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-[hsl(var(--destructive-foreground))]"
              >
                <StopCircle className="w-6 h-6 mr-3" /> Spiel beenden
              </Button>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <Button onClick={() => setShowConfirmEnd(false)} variant="outline" className="h-20 rounded-3xl border-[rgb(var(--color-border-rgb)/0.82)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">Abbrechen</Button>
                <Button onClick={onEndGame} data-testid="confirm-end-game-btn" className="h-20 rounded-3xl bg-[var(--color-accent)] text-[hsl(var(--destructive-foreground))] hover:opacity-90">Bestätigen</Button>
              </div>
            )}
          </div>
        </div>

        <div className="mx-auto w-full max-w-7xl rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.56)] px-5 py-3 text-sm text-[var(--color-text-secondary)] backdrop-blur">
          Session endet automatisch bei 0 Zeit oder 0 Credits. Manuelles Beenden bleibt bewusst sichtbar.
        </div>
      </div>
    </div>
  );
}

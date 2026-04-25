import { useState, useEffect } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Clock, Crown, Share2, Sparkles, Target, Trophy, Users, Wallet } from 'lucide-react';
import KioskHeader from '../../components/kiosk/KioskHeader';

const QR_DISPLAY_SECONDS = 60;

export default function MatchResultScreen({ branding, matchToken, session, onTimeout }) {
  const [secondsLeft, setSecondsLeft] = useState(QR_DISPLAY_SECONDS);

  const matchUrl = `${window.location.origin}/match/${matchToken}`;

  useEffect(() => {
    const iv = setInterval(() => {
      setSecondsLeft((value) => {
        if (value <= 1) {
          clearInterval(iv);
          onTimeout();
          return 0;
        }
        return value - 1;
      });
    }, 1000);
    return () => clearInterval(iv);
  }, [onTimeout]);

  const pct = (secondsLeft / QR_DISPLAY_SECONDS) * 100;
  const winner = session?.players?.[0];

  return (
    <div className="relative h-full w-full overflow-hidden bg-[var(--color-bg)]" data-testid="match-result-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(245,158,11,0.18),transparent_28%),linear-gradient(180deg,rgb(var(--color-bg-rgb)/0.96),var(--color-bg))]" />
      <div className="relative z-10 flex h-full flex-col px-6 py-6 lg:px-10 lg:py-8">
        <KioskHeader
          branding={branding}
          eyebrow="Match result"
          compact
          right={(
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-300">
              <Trophy className="h-4 w-4" /> Spiel beendet
            </div>
          )}
        />

        <div className="mx-auto grid w-full max-w-7xl flex-1 gap-6 py-8 lg:grid-cols-[1fr,0.88fr] lg:items-center">
          <div className="space-y-6">
            <div>
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-3xl border border-[rgb(var(--color-primary-rgb)/0.28)] bg-[rgb(var(--color-primary-rgb)/0.12)] text-[var(--color-primary)]">
                  <Target className="h-8 w-8" />
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Abgeschlossenes Spiel</p>
                  <h2 className="text-5xl font-heading uppercase tracking-[0.08em] text-[var(--color-text)] md:text-6xl" data-testid="match-game-type">
                    {session?.game_type || 'DART'}
                  </h2>
                </div>
              </div>
              <p className="mt-4 max-w-2xl text-lg leading-8 text-[var(--color-text-secondary)]">
                Ergebnis kurz teilen, dann geht der Kiosk automatisch wieder in den Startzustand. Schnell, sauber, venue-tauglich.
              </p>
            </div>

            {winner && (
              <div className="rounded-[2rem] border border-[rgb(var(--color-primary-rgb)/0.26)] bg-[rgb(var(--color-primary-rgb)/0.12)] p-5 shadow-[0_18px_48px_rgba(0,0,0,0.22)]">
                <div className="flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[rgb(var(--color-bg-rgb)/0.4)] text-[var(--color-primary)]">
                    <Crown className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-primary)]">Top Ergebnis</p>
                    <p className="mt-1 text-xl font-semibold text-[var(--color-text)]">{winner} vorne im Ergebnis</p>
                  </div>
                </div>
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.22)]">
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                  <Users className="h-4 w-4" /> Spieler
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  {session?.players?.map((player, index) => (
                    <span
                      key={index}
                      className={`rounded-2xl border px-4 py-2 text-base font-medium ${index === 0 ? 'border-[rgb(var(--color-primary-rgb)/0.3)] bg-[rgb(var(--color-primary-rgb)/0.12)] text-[var(--color-text)]' : 'border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-bg-rgb)/0.4)] text-[var(--color-text)]'}`}
                      data-testid={`match-player-${index}`}
                    >
                      {index === 0 && <Trophy className="mr-2 inline h-4 w-4 text-[var(--color-primary)]" />}
                      {player}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.22)]">
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                  <Wallet className="h-4 w-4" /> Session
                </div>
                <p className="mt-4 text-3xl font-semibold text-[var(--color-text)]">
                  {session?.pricing_mode === 'per_time'
                    ? `${session?.minutes_total || 0} min`
                    : `${session?.credits_remaining ?? 0} Credits übrig`}
                </p>
                <p className="mt-2 text-lg text-[var(--color-text-secondary)]">
                  {session?.pricing_mode === 'per_time'
                    ? `${session?.price_total?.toFixed(2)} €`
                    : `von ${session?.credits_total || 0} freigeschaltet`}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[2rem] border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-6 shadow-[0_24px_60px_rgba(0,0,0,0.28)]">
            <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
              <Share2 className="h-4 w-4 text-[var(--color-primary)]" /> Ergebnis teilen
            </div>
            <div className="mt-5 flex flex-col items-center gap-4">
              <div className="rounded-[1.75rem] border border-white/10 bg-white p-5 shadow-[0_16px_40px_rgba(0,0,0,0.24)]" data-testid="match-qr-code">
                <QRCodeSVG value={matchUrl} size={220} level="M" bgColor="#ffffff" fgColor="#000000" />
              </div>
              <div className="inline-flex items-center rounded-full border border-[rgb(var(--color-primary-rgb)/0.22)] bg-[rgb(var(--color-primary-rgb)/0.08)] px-3 py-1 text-xs uppercase tracking-[0.22em] text-[var(--color-primary)]">
                <Sparkles className="mr-1 h-3 w-3" /> 24h gültig
              </div>
              <p className="text-center text-sm leading-6 text-[var(--color-text-secondary)]">
                QR scannen, Match online öffnen und direkt weiterleiten.
              </p>
              <p className="max-w-[320px] break-all text-center font-mono text-xs text-[var(--color-text-muted)]">{matchUrl}</p>
            </div>
          </div>
        </div>

        <div className="mx-auto w-full max-w-7xl rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.56)] px-5 py-4 backdrop-blur">
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="flex items-center gap-1 text-xs uppercase tracking-[0.22em] text-[var(--color-text-muted)]">
              <Clock className="h-3 w-3" /> Zurück zum Startscreen in
            </span>
            <span className="text-sm font-mono text-[var(--color-text)]" data-testid="match-countdown">{secondsLeft}s</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[rgb(var(--color-border-rgb)/0.62)]">
            <div className="h-full bg-[var(--color-primary)] transition-all duration-1000 ease-linear" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
    </div>
  );
}

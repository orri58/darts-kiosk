import { useState, useEffect } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Clock, Share2, Target, Trophy, Users, Wallet } from 'lucide-react';

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

  return (
    <div className="relative h-full w-full overflow-hidden bg-zinc-950" data-testid="match-result-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(245,158,11,0.16),transparent_28%),linear-gradient(180deg,rgba(9,9,11,0.96),rgba(9,9,11,1))]" />
      <div className="relative z-10 flex h-full flex-col px-6 py-6 lg:px-10 lg:py-8">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between rounded-3xl border border-zinc-800 bg-zinc-950/70 px-5 py-4 backdrop-blur">
          <div>
            <p className="text-[11px] uppercase tracking-[0.28em] text-zinc-500">Match result</p>
            <h1 className="mt-1 text-2xl font-heading uppercase tracking-[0.08em] text-white">{branding?.cafe_name || 'Dart Zone'}</h1>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-300">
            <Trophy className="w-4 h-4" /> Spiel beendet
          </div>
        </div>

        <div className="mx-auto grid w-full max-w-7xl flex-1 gap-6 py-8 lg:grid-cols-[1fr,0.85fr] lg:items-center">
          <div className="space-y-6">
            <div>
              <div className="flex items-center gap-3">
                <div className="flex h-16 w-16 items-center justify-center rounded-3xl border border-zinc-800 bg-zinc-900/80 text-amber-400">
                  <Target className="h-8 w-8" />
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-zinc-500">Abgeschlossenes Spiel</p>
                  <h2 className="text-5xl font-heading uppercase tracking-[0.08em] text-white md:text-6xl" data-testid="match-game-type">{session?.game_type || 'DART'}</h2>
                </div>
              </div>
              <p className="mt-4 max-w-2xl text-lg leading-8 text-zinc-400">
                Ergebnis teilen, bevor der Screen automatisch zurück auf Locked fällt. Lokal, schnell, ohne unnötige Schritte.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-3xl border border-zinc-800 bg-zinc-950/80 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
                <div className="flex items-center gap-2 text-sm text-zinc-500">
                  <Users className="h-4 w-4 text-zinc-400" /> Spieler
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  {session?.players?.map((player, index) => (
                    <span
                      key={index}
                      className={`rounded-2xl border px-4 py-2 text-base font-medium ${index === 0 ? 'border-amber-500/30 bg-amber-500/10 text-amber-200' : 'border-zinc-700 bg-zinc-900 text-zinc-200'}`}
                      data-testid={`match-player-${index}`}
                    >
                      {index === 0 && <Trophy className="mr-2 inline h-4 w-4" />}
                      {player}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-3xl border border-zinc-800 bg-zinc-950/80 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
                <div className="flex items-center gap-2 text-sm text-zinc-500">
                  <Wallet className="h-4 w-4 text-zinc-400" /> Session
                </div>
                <p className="mt-4 text-3xl font-semibold text-white">{session?.pricing_mode === 'per_time' ? `${session?.minutes_total || 0} min` : `${session?.credits_total || 0} Credits`}</p>
                <p className="mt-2 text-lg text-zinc-400">{session?.price_total?.toFixed(2)} €</p>
              </div>
            </div>
          </div>

          <div className="rounded-[2rem] border border-zinc-800 bg-zinc-950/75 p-6 shadow-[0_24px_60px_rgba(0,0,0,0.28)]">
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <Share2 className="h-4 w-4 text-amber-400" /> Ergebnis teilen
            </div>
            <div className="mt-5 flex flex-col items-center gap-4">
              <div className="rounded-[1.75rem] bg-white p-5" data-testid="match-qr-code">
                <QRCodeSVG value={matchUrl} size={220} level="M" bgColor="#ffffff" fgColor="#000000" />
              </div>
              <p className="text-center text-sm leading-6 text-zinc-400">QR scannen, um das Match online zu öffnen oder weiterzuleiten.</p>
              <p className="max-w-[320px] break-all text-center font-mono text-xs text-zinc-600">{matchUrl}</p>
              <div className="inline-flex items-center rounded-full border border-zinc-800 bg-zinc-900 px-3 py-1 text-xs uppercase tracking-[0.22em] text-zinc-500">24h gültig</div>
            </div>
          </div>
        </div>

        <div className="mx-auto w-full max-w-7xl rounded-3xl border border-zinc-800 bg-zinc-950/70 px-5 py-4 backdrop-blur">
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1 text-xs uppercase tracking-[0.22em] text-zinc-500">
              <Clock className="w-3 h-3" /> Zurück zum Startscreen in
            </span>
            <span className="text-sm font-mono text-zinc-300" data-testid="match-countdown">{secondsLeft}s</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
            <div className="h-full bg-amber-500 transition-all duration-1000 ease-linear" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { Clock, Coins, Phone, StopCircle, Target, Users, Wallet } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { useSettings } from '../../context/SettingsContext';

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

  return (
    <div className="relative h-full w-full overflow-hidden bg-zinc-950" data-testid="in-game-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.16),transparent_30%),linear-gradient(180deg,rgba(9,9,11,0.96),rgba(9,9,11,1))]" />
      <div className="relative z-10 flex h-full flex-col px-6 py-6 lg:px-10 lg:py-8">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between rounded-3xl border border-zinc-800 bg-zinc-950/70 px-5 py-4 backdrop-blur">
          <div>
            <p className="text-[11px] uppercase tracking-[0.28em] text-zinc-500">Live session</p>
            <h1 className="mt-1 text-2xl font-heading uppercase tracking-[0.08em] text-white">{branding.cafe_name}</h1>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
            {kioskTexts.game_running || 'SPIEL LÄUFT'}
          </div>
        </div>

        <div className="mx-auto grid w-full max-w-7xl flex-1 gap-6 py-8 lg:grid-cols-[1.2fr,0.8fr] lg:items-center">
          <div className="space-y-6">
            <div>
              <div className="flex items-center gap-3">
                <div className="flex h-16 w-16 items-center justify-center rounded-3xl border border-zinc-800 bg-zinc-900/80 text-amber-400">
                  <Target className="h-8 w-8" />
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-zinc-500">Aktives Spiel</p>
                  <h2 className="text-5xl font-heading uppercase tracking-[0.08em] text-white md:text-6xl">{session?.game_type || 'DART'}</h2>
                </div>
              </div>
              <p className="mt-4 max-w-2xl text-lg leading-8 text-zinc-400">
                Session läuft lokal auf diesem Board. Credits/Zeit werden erst durch echte Match-Events oder Timer aufgebraucht — nicht durch bloße Assistenzhinweise.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-3xl border border-zinc-800 bg-zinc-950/80 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
                <div className="flex items-center gap-2 text-sm text-zinc-500">
                  <Users className="h-4 w-4 text-zinc-400" /> Spieler
                </div>
                <div className="mt-4 space-y-2">
                  {session?.players?.map((player, index) => (
                    <p key={index} className="truncate text-lg font-medium text-white">{player}</p>
                  )) || <p className="text-zinc-600">-</p>}
                </div>
              </div>

              {session?.pricing_mode === 'per_game' ? (
                <div className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
                  <div className="flex items-center gap-2 text-sm text-amber-100/70">
                    <Coins className="h-4 w-4 text-amber-400" /> {kioskTexts.credits_label || 'Spiele übrig'}
                  </div>
                  <p className="mt-4 text-5xl font-semibold text-white" data-testid="credits-remaining">{session?.credits_remaining || 0}</p>
                  <p className="mt-2 text-sm text-amber-100/70">von {session?.credits_total || 0} gekauft</p>
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

              <div className="rounded-3xl border border-zinc-800 bg-zinc-950/80 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
                <div className="flex items-center gap-2 text-sm text-zinc-500">
                  <Wallet className="h-4 w-4 text-zinc-400" /> Tarif
                </div>
                <p className="mt-4 text-3xl font-semibold text-white">{session?.pricing_mode === 'per_game' ? `${session?.credits_total || 0} Credits` : `${session?.minutes_total || 0} min`}</p>
                <p className="mt-2 text-lg text-zinc-400">{session?.price_total?.toFixed(2)} €</p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl border border-zinc-800 bg-zinc-950/75 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
              <p className="text-[11px] uppercase tracking-[0.28em] text-zinc-500">Operator-safe actions</p>
              <p className="mt-2 text-sm leading-6 text-zinc-400">
                Diese Buttons greifen bewusst nur lokal und nachvollziehbar ein. Kein versteckter Sync, keine Magie.
              </p>
            </div>

            {onCallStaff && (
              <Button
                onClick={onCallStaff}
                data-testid="call-staff-btn"
                variant="outline"
                className="h-20 w-full rounded-3xl border-2 border-zinc-700 bg-transparent text-lg text-zinc-200 hover:border-amber-500 hover:text-amber-300"
              >
                <Phone className="w-6 h-6 mr-3" />
                {kioskTexts.call_staff || 'Personal rufen'}
              </Button>
            )}

            {!showConfirmEnd ? (
              <Button
                onClick={() => setShowConfirmEnd(true)}
                data-testid="end-game-btn"
                className="h-20 w-full rounded-3xl border-2 border-red-500/40 bg-red-500/10 text-lg text-red-300 hover:bg-red-500 hover:text-white"
              >
                <StopCircle className="w-6 h-6 mr-3" /> Spiel beenden
              </Button>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <Button onClick={() => setShowConfirmEnd(false)} variant="outline" className="h-20 rounded-3xl border-zinc-700 text-zinc-300 hover:text-white">Abbrechen</Button>
                <Button onClick={onEndGame} data-testid="confirm-end-game-btn" className="h-20 rounded-3xl bg-red-500 text-white hover:bg-red-400">Bestätigen</Button>
              </div>
            )}
          </div>
        </div>

        <div className="mx-auto w-full max-w-7xl rounded-3xl border border-zinc-800 bg-zinc-950/70 px-5 py-4 text-sm text-zinc-400 backdrop-blur">
          Spiel wird automatisch beendet, sobald Zeit oder Credits erschöpft sind. Manuelles Beenden bleibt bewusst sichtbar, aber bestätigt sich nicht heimlich im Hintergrund.
        </div>
      </div>
    </div>
  );
}

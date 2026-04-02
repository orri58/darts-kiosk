import { AlertTriangle, Coins, Phone, Users } from 'lucide-react';
import { Button } from '../../components/ui/button';

export default function CreditBlockedScreen({ branding, session, onCallStaff }) {
  const requiredUnits = Math.max(1, Number(session?.players_count || session?.players?.length || 1));
  const creditsAvailable = Math.max(0, Number(session?.credits_remaining || 0));
  const shortage = Math.max(0, requiredUnits - creditsAvailable);

  return (
    <div className="relative h-full w-full overflow-hidden bg-zinc-950" data-testid="credit-blocked-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(239,68,68,0.16),transparent_32%),linear-gradient(180deg,rgba(9,9,11,0.96),rgba(9,9,11,1))]" />
      <div className="relative z-10 flex h-full items-center justify-center p-8">
        <div className="w-full max-w-4xl rounded-[2rem] border border-red-500/30 bg-zinc-950/85 p-8 shadow-[0_24px_80px_rgba(0,0,0,0.42)] backdrop-blur">
          <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-3xl border border-red-500/30 bg-red-500/10 text-red-300">
            <AlertTriangle className="h-12 w-12" />
          </div>

          <div className="mt-8 text-center">
            <p className="text-[11px] uppercase tracking-[0.28em] text-red-300/70">Match pausiert</p>
            <h1 className="mt-3 text-4xl font-heading uppercase tracking-[0.08em] text-white md:text-5xl">
              Zu wenig Credits für dieses Match
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg leading-8 text-zinc-300">
              Autodarts hat das Match mit der echten Spielerzahl gestartet. Das Board bleibt lokal freigeschaltet,
              aber der Match-Start ist solange blockiert, bis genug Credits nachgelegt wurden.
            </p>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl border border-zinc-800 bg-zinc-900/70 p-5">
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <Users className="h-4 w-4 text-zinc-400" /> Autoritative Spieler
              </div>
              <p className="mt-4 text-5xl font-semibold text-white" data-testid="blocked-required-players">{requiredUnits}</p>
              <p className="mt-2 text-sm text-zinc-400">Aus dem laufenden Autodarts-Match erkannt.</p>
            </div>

            <div className="rounded-3xl border border-zinc-800 bg-zinc-900/70 p-5">
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <Coins className="h-4 w-4 text-zinc-400" /> Verfügbare Credits
              </div>
              <p className="mt-4 text-5xl font-semibold text-white" data-testid="blocked-credits-available">{creditsAvailable}</p>
              <p className="mt-2 text-sm text-zinc-400">Sobald genug Credits da sind, geht es automatisch weiter.</p>
            </div>

            <div className="rounded-3xl border border-red-500/30 bg-red-500/10 p-5">
              <div className="flex items-center gap-2 text-sm text-red-100/70">
                <AlertTriangle className="h-4 w-4 text-red-300" /> Fehlende Credits
              </div>
              <p className="mt-4 text-5xl font-semibold text-white" data-testid="blocked-credit-shortage">{shortage}</p>
              <p className="mt-2 text-sm text-red-100/70">Bitte Personal informieren, damit die Session aufgeladen wird.</p>
            </div>
          </div>

          <div className="mt-8 rounded-3xl border border-zinc-800 bg-zinc-900/60 px-6 py-5 text-center text-sm leading-7 text-zinc-400">
            {branding?.cafe_name || 'DartsKiosk'} wartet auf eine Freigabe am Tresen. Kein automatischer Abbruch,
            keine Doppelbelastung — der Start wird erst akzeptiert, wenn die Credits reichen.
          </div>

          {onCallStaff && (
            <div className="mt-6 flex justify-center">
              <Button
                onClick={onCallStaff}
                data-testid="blocked-call-staff-btn"
                className="h-16 rounded-3xl bg-amber-500 px-8 text-lg text-black hover:bg-amber-400"
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

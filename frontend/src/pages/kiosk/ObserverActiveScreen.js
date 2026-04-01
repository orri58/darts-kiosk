import { useState } from 'react';
import { AlertTriangle, Phone, RefreshCw, StopCircle } from 'lucide-react';
import { Button } from '../../components/ui/button';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ObserverActiveScreen({ observerBrowserOpen, observerState, observerError, boardId, onEndGame, onCallStaff }) {
  const [retrying, setRetrying] = useState(false);
  const [showConfirmEnd, setShowConfirmEnd] = useState(false);

  const handleRetryObserver = async () => {
    setRetrying(true);
    try {
      await axios.post(`${API}/kiosk/${boardId}/observer-reset`);
    } catch {
      /* ignore */
    }
    setTimeout(() => setRetrying(false), 5000);
  };

  if (observerBrowserOpen) {
    return <div className="h-full w-full bg-black" data-testid="observer-handoff-screen" />;
  }

  return (
    <div className="relative h-full w-full overflow-hidden bg-zinc-950" data-testid="observer-fallback-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(245,158,11,0.14),transparent_28%),linear-gradient(180deg,rgba(9,9,11,0.96),rgba(9,9,11,1))]" />
      <div className="relative z-10 flex h-full items-center justify-center p-8">
        <div className="w-full max-w-2xl rounded-[2rem] border border-zinc-800 bg-zinc-950/80 p-8 text-center shadow-[0_24px_80px_rgba(0,0,0,0.4)] backdrop-blur">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-amber-500/20 bg-amber-500/10 text-amber-400">
            <AlertTriangle className="h-10 w-10" />
          </div>

          <h2 className="mt-6 text-3xl font-heading uppercase tracking-[0.08em] text-white">Autodarts gerade nicht verfügbar</h2>
          <p className="mt-4 text-lg leading-8 text-zinc-400">
            {observerState === 'error' || observerState === 'closed'
              ? 'Der lokale Autodarts-Browser konnte nicht sauber gestartet oder gehalten werden.'
              : 'Die Verbindung zu Autodarts wird aufgebaut. Wenn das hängen bleibt, kann der Operator lokal neu anstoßen.'}
          </p>

          {observerError && (
            <div className="mt-5 rounded-3xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-left text-sm text-red-100" data-testid="observer-error-message">
              {observerError.split('\n')[0].substring(0, 180)}
            </div>
          )}

          <div className="mt-8 grid gap-3 sm:grid-cols-2">
            <Button onClick={handleRetryObserver} disabled={retrying} className="h-16 rounded-3xl bg-amber-500 text-black hover:bg-amber-400" data-testid="observer-retry-btn">
              {retrying ? <><RefreshCw className="mr-2 h-5 w-5 animate-spin" /> Wird gestartet…</> : <><RefreshCw className="mr-2 h-5 w-5" /> Autodarts neu starten</>}
            </Button>
            {onCallStaff ? (
              <Button onClick={onCallStaff} variant="outline" className="h-16 rounded-3xl border-zinc-700 text-zinc-200 hover:text-amber-300" data-testid="fallback-call-staff-btn">
                <Phone className="mr-2 h-5 w-5" /> Personal rufen
              </Button>
            ) : (
              <div className="hidden sm:block" />
            )}
          </div>

          {!showConfirmEnd ? (
            <Button onClick={() => setShowConfirmEnd(true)} variant="ghost" className="mt-5 text-zinc-500 hover:text-red-300" data-testid="fallback-end-session-btn">
              <StopCircle className="mr-2 h-4 w-4" /> Session beenden
            </Button>
          ) : (
            <div className="mt-5 grid grid-cols-2 gap-3">
              <Button onClick={() => setShowConfirmEnd(false)} variant="outline" className="h-14 rounded-3xl border-zinc-700 text-zinc-300">Abbrechen</Button>
              <Button onClick={onEndGame} className="h-14 rounded-3xl bg-red-500 text-white hover:bg-red-400" data-testid="fallback-confirm-end-btn">Bestätigen</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { AlertTriangle, Phone, RefreshCw, StopCircle } from 'lucide-react';
import { Button } from '../../components/ui/button';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ObserverActiveScreen({ observerBrowserOpen, observerHeadless, observerState, observerError, boardId, onEndGame, onCallStaff }) {
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

  if (observerBrowserOpen && !observerHeadless) {
    return <div className="h-full w-full bg-black" data-testid="observer-handoff-screen" />;
  }

  return (
    <div className="relative h-full w-full overflow-hidden bg-[var(--color-bg)]" data-testid="observer-fallback-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgb(var(--color-primary-rgb)/0.14),transparent_28%),linear-gradient(180deg,rgb(var(--color-bg-rgb)/0.96),var(--color-bg))]" />
      <div className="relative z-10 flex h-full items-center justify-center p-8">
        <div className="w-full max-w-2xl rounded-[2rem] border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.8)] p-8 text-center shadow-[0_24px_80px_rgba(0,0,0,0.4)] backdrop-blur">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-[rgb(var(--color-primary-rgb)/0.24)] bg-[rgb(var(--color-primary-rgb)/0.12)] text-[var(--color-primary)]">
            <AlertTriangle className="h-10 w-10" />
          </div>

          <h2 className="mt-6 text-3xl font-heading uppercase tracking-[0.08em] text-[var(--color-text)]">Autodarts gerade nicht verfügbar</h2>
          <p className="mt-4 text-base leading-7 text-[var(--color-text-secondary)] lg:text-lg lg:leading-8">
            {observerHeadless
              ? 'Autodarts läuft in dieser Umgebung headless im Hintergrund. Für Browser-Smokes bleibt der Kiosk sichtbar, statt auf einen externen Observer-Bildschirm zu wechseln.'
              : observerState === 'error' || observerState === 'closed'
                ? 'Der lokale Autodarts-Browser konnte nicht sauber gestartet oder gehalten werden.'
                : 'Die Verbindung zu Autodarts wird aufgebaut. Wenn das hängen bleibt, kann der Operator lokal neu anstoßen.'}
          </p>

          {observerError && (
            <div className="mt-5 rounded-3xl border border-[rgb(var(--color-accent-rgb)/0.24)] bg-[rgb(var(--color-accent-rgb)/0.12)] px-4 py-3 text-left text-sm text-[var(--color-text)]" data-testid="observer-error-message">
              {observerError.split('\n')[0].substring(0, 180)}
            </div>
          )}

          <div className="mt-8 grid gap-3 sm:grid-cols-2">
            <Button onClick={handleRetryObserver} disabled={retrying} className="h-16 rounded-3xl bg-[var(--color-primary)] text-[hsl(var(--primary-foreground))] hover:opacity-90" data-testid="observer-retry-btn">
              {retrying ? <><RefreshCw className="mr-2 h-5 w-5 animate-spin" /> Wird gestartet…</> : <><RefreshCw className="mr-2 h-5 w-5" /> Autodarts neu starten</>}
            </Button>
            {onCallStaff ? (
              <Button onClick={onCallStaff} variant="outline" className="h-16 rounded-3xl border-[rgb(var(--color-border-rgb)/0.82)] text-[var(--color-text)] hover:border-[rgb(var(--color-primary-rgb)/0.34)] hover:text-[var(--color-primary)]" data-testid="fallback-call-staff-btn">
                <Phone className="mr-2 h-5 w-5" /> Personal rufen
              </Button>
            ) : (
              <div className="hidden sm:block" />
            )}
          </div>

          {!showConfirmEnd ? (
            <Button onClick={() => setShowConfirmEnd(true)} variant="ghost" className="mt-5 text-[var(--color-text-secondary)] hover:text-[var(--color-accent)]" data-testid="fallback-end-session-btn">
              <StopCircle className="mr-2 h-4 w-4" /> Session beenden
            </Button>
          ) : (
            <div className="mt-5 grid grid-cols-2 gap-3">
              <Button onClick={() => setShowConfirmEnd(false)} variant="outline" className="h-14 rounded-3xl border-[rgb(var(--color-border-rgb)/0.82)] text-[var(--color-text-secondary)]">Abbrechen</Button>
              <Button onClick={onEndGame} className="h-14 rounded-3xl bg-[var(--color-accent)] text-[hsl(var(--destructive-foreground))] hover:opacity-90" data-testid="fallback-confirm-end-btn">Bestätigen</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

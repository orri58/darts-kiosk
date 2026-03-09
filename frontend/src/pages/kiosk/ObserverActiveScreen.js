import { useState } from 'react';
import { AlertTriangle, RefreshCw, StopCircle, Phone } from 'lucide-react';
import { Button } from '../../components/ui/button';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Observer Active Screen
 *
 * Two modes:
 *   HANDOFF: Autodarts Chrome is fullscreen on top. This is a pure black
 *            backdrop invisible behind it. Only seen if user alt-tabs back.
 *
 *   FALLBACK: Browser launch failed. Error screen with retry + end session.
 */
export default function ObserverActiveScreen({
  branding,
  session,
  boardId,
  observerBrowserOpen,
  observerState,
  observerError,
  onEndGame,
  onCallStaff,
}) {
  const [retrying, setRetrying] = useState(false);
  const [showConfirmEnd, setShowConfirmEnd] = useState(false);

  const handleRetryObserver = async () => {
    setRetrying(true);
    try {
      await axios.post(`${API}/kiosk/${boardId}/observer-reset`);
    } catch { /* silent */ }
    setTimeout(() => setRetrying(false), 5000);
  };

  // ─── HANDOFF: Pure black backdrop (Autodarts Chrome is on top) ───
  if (observerBrowserOpen) {
    return (
      <div
        className="h-full w-full bg-black"
        data-testid="observer-handoff-screen"
      />
    );
  }

  // ─── FALLBACK: Browser launch failed ───
  return (
    <div
      className="h-full w-full bg-zinc-950 flex flex-col items-center justify-center p-8"
      data-testid="observer-fallback-screen"
    >
      <div className="text-center max-w-md">
        <AlertTriangle className="w-16 h-16 text-amber-500 mx-auto mb-6" />

        <h2 className="text-2xl font-heading uppercase tracking-wider text-white mb-3">
          Autodarts nicht verfuegbar
        </h2>

        <p className="text-zinc-400 mb-2">
          {observerState === 'error' || observerState === 'closed'
            ? 'Der Autodarts-Browser konnte nicht gestartet werden.'
            : 'Verbindung zu Autodarts wird hergestellt...'}
        </p>

        {observerError && (
          <p className="text-sm text-red-400/70 mb-6 max-w-md" data-testid="observer-error-message">
            {observerError.split('\n')[0].substring(0, 120)}
          </p>
        )}

        {/* Action buttons */}
        <div className="flex flex-col gap-3 w-full max-w-xs mx-auto mt-8">
          <Button
            onClick={handleRetryObserver}
            disabled={retrying}
            className="w-full h-14 text-lg bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading tracking-wider"
            data-testid="observer-retry-btn"
          >
            {retrying ? (
              <><RefreshCw className="w-5 h-5 mr-2 animate-spin" /> Wird gestartet...</>
            ) : (
              <><RefreshCw className="w-5 h-5 mr-2" /> Autodarts starten</>
            )}
          </Button>

          <Button
            onClick={onCallStaff}
            variant="outline"
            className="w-full h-12 border-2 border-zinc-700 text-zinc-300 hover:border-amber-500 hover:text-amber-500 uppercase font-heading tracking-wider"
            data-testid="fallback-call-staff-btn"
          >
            <Phone className="w-5 h-5 mr-2" /> Personal rufen
          </Button>

          {!showConfirmEnd ? (
            <Button
              onClick={() => setShowConfirmEnd(true)}
              variant="ghost"
              className="w-full text-zinc-600 hover:text-red-400 uppercase text-sm"
              data-testid="fallback-end-session-btn"
            >
              <StopCircle className="w-4 h-4 mr-2" /> Session beenden
            </Button>
          ) : (
            <div className="flex gap-2">
              <Button
                onClick={() => setShowConfirmEnd(false)}
                variant="outline"
                className="flex-1 border-zinc-700 text-zinc-400"
              >
                Abbrechen
              </Button>
              <Button
                onClick={onEndGame}
                className="flex-1 bg-red-500 text-white hover:bg-red-400"
                data-testid="fallback-confirm-end-btn"
              >
                Bestaetigen
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

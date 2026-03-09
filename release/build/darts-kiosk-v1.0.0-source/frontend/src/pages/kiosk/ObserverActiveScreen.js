import { useState, useEffect, useCallback } from 'react';
import { Clock, Coins, AlertTriangle, RefreshCw, StopCircle, Phone } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { useI18n } from '../../context/I18nContext';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Observer Active Screen — shown behind the Autodarts browser window.
 *
 * Two modes:
 *   1. HANDOFF (default): Autodarts is fullscreen on top. This screen is a
 *      dark minimal backdrop the user normally never sees. Shows a tiny
 *      status line at the bottom in case the user alt-tabs back.
 *
 *   2. FALLBACK: Autodarts browser failed to open. Shows a clear error
 *      state with retry and end-session actions.
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
  const { t } = useI18n();
  const [retrying, setRetrying] = useState(false);
  const [showConfirmEnd, setShowConfirmEnd] = useState(false);

  const handleRetryObserver = async () => {
    setRetrying(true);
    try {
      await axios.post(`${API}/kiosk/${boardId}/observer-reset`);
    } catch { /* silent */ }
    setTimeout(() => setRetrying(false), 5000);
  };

  // ───────────────────────────────────────────────────────────────
  // HANDOFF MODE — Autodarts is on top, this is the dark backdrop
  // ───────────────────────────────────────────────────────────────
  if (observerBrowserOpen) {
    return (
      <div
        className="h-full w-full bg-black flex flex-col justify-end"
        data-testid="observer-handoff-screen"
      >
        {/* Minimal info bar at the very bottom — barely visible behind Autodarts */}
        <div className="p-4 flex items-center justify-between bg-black/80 border-t border-zinc-900">
          <div className="flex items-center gap-4">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs text-zinc-600 uppercase tracking-wider font-heading">
              Autodarts aktiv — {branding?.cafe_name}
            </span>
          </div>
          <div className="flex items-center gap-4">
            {session?.pricing_mode === 'per_game' && (
              <span className="text-xs text-zinc-600 font-mono" data-testid="handoff-credits">
                {session.credits_remaining} {session.credits_remaining === 1 ? 'Spiel' : 'Spiele'}
              </span>
            )}
            <button
              onClick={onCallStaff}
              className="text-xs text-zinc-700 hover:text-zinc-400 uppercase tracking-wider"
              data-testid="handoff-call-staff"
            >
              Personal
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ───────────────────────────────────────────────────────────────
  // FALLBACK MODE — Autodarts browser not open, show error/retry
  // ───────────────────────────────────────────────────────────────
  const isError = observerState === 'error' || observerState === 'closed';

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
          {isError
            ? 'Der Autodarts-Browser konnte nicht gestartet werden.'
            : 'Verbindung zu Autodarts wird hergestellt...'}
        </p>

        {isError && (
          <p className="text-sm text-red-400/70 mb-6 max-w-md">
            {observerError
              ? observerError.split('\n')[0].substring(0, 120)
              : 'Pruefen Sie die Autodarts-URL und starten Sie erneut.'}
          </p>
        )}

        {/* Session Info */}
        <div className="flex justify-center gap-6 mb-8 mt-6">
          {session?.pricing_mode === 'per_game' ? (
            <div className="text-center">
              <Coins className="w-6 h-6 text-amber-500 mx-auto mb-1" />
              <p className="text-3xl font-mono font-bold text-amber-500" data-testid="fallback-credits">
                {session.credits_remaining}
              </p>
              <p className="text-xs text-zinc-500 uppercase">Spiele</p>
            </div>
          ) : session?.pricing_mode === 'per_time' ? (
            <div className="text-center">
              <Clock className="w-6 h-6 text-amber-500 mx-auto mb-1" />
              <p className="text-xs text-zinc-500 uppercase">Zeit aktiv</p>
            </div>
          ) : null}
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-3 w-full max-w-xs mx-auto">
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

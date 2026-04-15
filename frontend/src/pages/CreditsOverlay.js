import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useBoardWS } from '../hooks/useBoardWS';
import { useSettings } from '../context/SettingsContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Credits Overlay — lightweight always-on-top display.
 * Opens in a small separate browser window positioned bottom-left.
 * Receives real-time updates via WebSocket + polling fallback.
 * Route: /overlay/:boardId
 */
export default function CreditsOverlay() {
  const { boardId } = useParams();
  const { theme } = useSettings();
  const [data, setData] = useState(null);
  const [flash, setFlash] = useState(false);
  const intervalRef = useRef(null);
  const prevCreditsRef = useRef(null);

  // WebSocket handler for real-time credit updates
  const handleWsEvent = useCallback((event, wsData) => {
    if (!wsData || wsData.board_id !== boardId) return;

    if (event === 'credit_update') {
      setData(prev => {
        if (!prev) return prev;
        const wasHigher = prev.credits_remaining > wsData.credits_remaining;
        if (wasHigher) setFlash(true);
        return {
          ...prev,
          credits_remaining: wsData.credits_remaining,
          is_last_game: wsData.is_last_game,
        };
      });
    }

    if (event === 'board_status') {
      if (wsData.status === 'locked') {
        setData(null); // Hide overlay when board locks
      }
    }
  }, [boardId]);

  const { connected } = useBoardWS(handleWsEvent);

  // Polling fallback (every 3s)
  useEffect(() => {
    const fetchOverlay = async () => {
      try {
        const res = await fetch(`${API}/kiosk/${boardId}/overlay`);
        if (res.ok) {
          const d = await res.json();
          setData(prev => {
            // Detect credit change for flash animation
            if (prev && prev.credits_remaining > d.credits_remaining) {
              setFlash(true);
            }
            return d;
          });
        }
      } catch { /* silent */ }
    };
    fetchOverlay();
    intervalRef.current = setInterval(fetchOverlay, 3000);
    return () => clearInterval(intervalRef.current);
  }, [boardId]);

  // Clear flash after animation
  useEffect(() => {
    if (flash) {
      const t = setTimeout(() => setFlash(false), 800);
      return () => clearTimeout(t);
    }
  }, [flash]);

  // Track previous credits for transition
  useEffect(() => {
    if (data?.credits_remaining !== undefined) {
      prevCreditsRef.current = data.credits_remaining;
    }
  }, [data?.credits_remaining]);

  // Hidden state: transparent full page
  if (!data || !data.visible) {
    return (
      <div style={{
        background: 'transparent',
        width: '100vw',
        height: '100vh',
      }} />
    );
  }

  const isLastGame = data.is_last_game;
  const isTimeMode = data.pricing_mode === 'per_time';
  const isPendingGate = data.pending_credit_gate;
  const credits = data.credits_remaining ?? 0;
  const timeLeft = data.time_remaining_seconds;

  const formatTime = (seconds) => {
    if (seconds == null) return '--:--';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const isTimeLow = isTimeMode && timeLeft != null && timeLeft < 300;

  return (
    <div style={{
      position: 'fixed',
      bottom: 20,
      left: 20,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      zIndex: 99999,
      pointerEvents: 'none',
    }}>
      <div
        data-testid="credits-overlay"
        style={{
          background: isPendingGate
            ? 'rgb(var(--color-accent-rgb) / 0.2)'
            : isLastGame
            ? 'rgb(var(--color-accent-rgb) / 0.18)'
            : 'rgb(var(--color-bg-rgb) / 0.88)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderRadius: 16,
          padding: isLastGame ? '14px 20px' : '12px 18px',
          color: 'var(--color-text)',
          minWidth: 160,
          border: isPendingGate
            ? '1.5px solid rgb(var(--color-accent-rgb) / 0.55)'
            : isLastGame
            ? '1.5px solid rgb(var(--color-accent-rgb) / 0.45)'
            : '1px solid rgb(var(--color-border-rgb) / 0.82)',
          boxShadow: isPendingGate
            ? '0 4px 24px rgb(var(--color-accent-rgb) / 0.28), 0 0 0 1px rgb(var(--color-accent-rgb) / 0.12)'
            : isLastGame
            ? '0 4px 24px rgb(var(--color-accent-rgb) / 0.24), 0 0 0 1px rgb(var(--color-accent-rgb) / 0.12)'
            : '0 4px 24px rgba(0, 0, 0, 0.5)',
          transition: 'all 0.3s ease',
          transform: flash ? 'scale(1.05)' : 'scale(1)',
        }}
      >
        {isPendingGate ? (
          <div data-testid="pending-credit-warning">
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              marginBottom: 6,
            }}>
              <span style={{ fontSize: 18 }}>&#9888;</span>
              <span style={{
                fontSize: 14,
                fontWeight: 800,
                textTransform: 'uppercase',
                letterSpacing: 1.8,
                color: theme.accentForeground,
              }}>
                Credits fehlen
              </span>
            </div>
            <div style={{ fontSize: 11, color: theme.text, textAlign: 'center', lineHeight: 1.45 }}>
              Für {data.players_count ?? 0} Spieler fehlen noch {data.credits_shortage ?? 0}. Verfügbar: {credits}.
            </div>
          </div>
        ) : isLastGame ? (
          /* === LETZTES SPIEL WARNING + UPSELL === */
          <div data-testid="last-game-warning">
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              marginBottom: (data.upsell_message || data.upsell_pricing) ? 8 : 2,
            }}>
              <span style={{ fontSize: 18 }}>&#9888;</span>
              <span style={{
                fontSize: 15,
                fontWeight: 800,
                textTransform: 'uppercase',
                letterSpacing: 2,
                color: 'var(--color-accent)',
              }}>
                LETZTES SPIEL
              </span>
            </div>
            {data.upsell_message && (
              <div data-testid="upsell-message" style={{
                fontSize: 11,
                color: 'var(--color-text)',
                textAlign: 'center',
                lineHeight: 1.4,
                opacity: 0.9,
              }}>
                {data.upsell_message}
              </div>
            )}
            {data.upsell_pricing && (
              <div data-testid="upsell-pricing" style={{
                fontSize: 10,
                color: 'var(--color-primary)',
                textAlign: 'center',
                marginTop: 4,
                fontWeight: 600,
                letterSpacing: 0.5,
                opacity: 0.8,
              }}>
                {data.upsell_pricing}
              </div>
            )}
          </div>
        ) : isTimeMode ? (
          /* === TIME MODE === */
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={isTimeLow ? 'var(--color-primary)' : 'var(--color-text-muted)'} strokeWidth="2.5" strokeLinecap="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v6l4 2" />
            </svg>
            <div>
              <div style={{
                fontSize: 10,
                color: 'var(--color-text-muted)',
                textTransform: 'uppercase',
                letterSpacing: 1.5,
                marginBottom: 2,
              }}>
                Zeit übrig
              </div>
              <div style={{
                fontSize: 22,
                fontWeight: 700,
                fontVariantNumeric: 'tabular-nums',
                color: isTimeLow ? 'var(--color-primary)' : 'var(--color-text)',
                lineHeight: 1,
              }}>
                {formatTime(timeLeft)}
              </div>
            </div>
          </div>
        ) : (
          /* === CREDIT MODE === */
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={credits <= 1 ? 'var(--color-primary)' : 'var(--color-text-muted)'} strokeWidth="2.5" strokeLinecap="round">
              <circle cx="12" cy="5" r="3" />
              <line x1="12" y1="8" x2="12" y2="16" />
              <path d="M9 20l3-4 3 4" />
            </svg>
            <div>
              <div style={{
                fontSize: 10,
                color: 'var(--color-text-muted)',
                textTransform: 'uppercase',
                letterSpacing: 1.5,
                marginBottom: 2,
              }}>
                Credits verfügbar
              </div>
              <div style={{
                fontSize: 22,
                fontWeight: 700,
                fontVariantNumeric: 'tabular-nums',
                color: credits <= 1 ? 'var(--color-primary)' : 'var(--color-text)',
                lineHeight: 1,
                transition: 'color 0.3s ease',
              }}>
                {credits}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Connection indicator (tiny dot) */}
      <div style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: connected ? '#22c55e' : theme.error,
        marginTop: 6,
        marginLeft: 8,
        opacity: 0.6,
      }} />
    </div>
  );
}

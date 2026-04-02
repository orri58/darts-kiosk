import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useBoardWS } from '../hooks/useBoardWS';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Credits Overlay — lightweight always-on-top display.
 * Opens in a small separate browser window positioned bottom-left.
 * Receives real-time updates via WebSocket + polling fallback.
 * Route: /overlay/:boardId
 */
export default function CreditsOverlay() {
  const { boardId } = useParams();
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
            ? 'rgba(127, 29, 29, 0.94)'
            : isLastGame
            ? 'rgba(127, 29, 29, 0.92)'
            : 'rgba(9, 9, 11, 0.88)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderRadius: 10,
          padding: isLastGame ? '14px 20px' : '12px 18px',
          color: '#fff',
          minWidth: 160,
          border: isPendingGate
            ? '1.5px solid rgba(248, 113, 113, 0.7)'
            : isLastGame
            ? '1.5px solid rgba(239, 68, 68, 0.6)'
            : '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: isPendingGate
            ? '0 4px 24px rgba(248, 113, 113, 0.35), 0 0 0 1px rgba(248, 113, 113, 0.14)'
            : isLastGame
            ? '0 4px 24px rgba(239, 68, 68, 0.3), 0 0 0 1px rgba(239, 68, 68, 0.1)'
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
                color: '#fecaca',
              }}>
                Credits fehlen
              </span>
            </div>
            <div style={{ fontSize: 11, color: '#fee2e2', textAlign: 'center', lineHeight: 1.45 }}>
              Match braucht {data.required_units ?? 0}, verfügbar {credits}. Es fehlen {data.credits_shortage ?? 0}.
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
                color: '#fca5a5',
              }}>
                LETZTES SPIEL
              </span>
            </div>
            {data.upsell_message && (
              <div data-testid="upsell-message" style={{
                fontSize: 11,
                color: '#fecaca',
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
                color: '#fca5a5',
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
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={isTimeLow ? '#f59e0b' : '#71717a'} strokeWidth="2.5" strokeLinecap="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v6l4 2" />
            </svg>
            <div>
              <div style={{
                fontSize: 10,
                color: '#71717a',
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
                color: isTimeLow ? '#f59e0b' : '#fff',
                lineHeight: 1,
              }}>
                {formatTime(timeLeft)}
              </div>
            </div>
          </div>
        ) : (
          /* === CREDIT MODE === */
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={credits <= 1 ? '#f59e0b' : '#71717a'} strokeWidth="2.5" strokeLinecap="round">
              <circle cx="12" cy="5" r="3" />
              <line x1="12" y1="8" x2="12" y2="16" />
              <path d="M9 20l3-4 3 4" />
            </svg>
            <div>
              <div style={{
                fontSize: 10,
                color: '#71717a',
                textTransform: 'uppercase',
                letterSpacing: 1.5,
                marginBottom: 2,
              }}>
                Spiele übrig
              </div>
              <div style={{
                fontSize: 22,
                fontWeight: 700,
                fontVariantNumeric: 'tabular-nums',
                color: credits <= 1 ? '#f59e0b' : '#fff',
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
        background: connected ? '#22c55e' : '#ef4444',
        marginTop: 6,
        marginLeft: 8,
        opacity: 0.6,
      }} />
    </div>
  );
}

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Lightweight credits overlay — opens in a small separate window.
 * Polls /api/kiosk/{board_id}/overlay every 3 seconds.
 * Route: /overlay/:boardId
 */
export default function CreditsOverlay() {
  const { boardId } = useParams();
  const [data, setData] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const fetchOverlay = async () => {
      try {
        const res = await axios.get(`${API}/kiosk/${boardId}/overlay`);
        setData(res.data);
      } catch {
        setData(null);
      }
    };
    fetchOverlay();
    intervalRef.current = setInterval(fetchOverlay, 3000);
    return () => clearInterval(intervalRef.current);
  }, [boardId]);

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

  const formatTime = (seconds) => {
    if (!seconds) return '--:--';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div style={{
      position: 'fixed',
      bottom: 16,
      left: 16,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      zIndex: 99999,
    }}>
      <div
        data-testid="credits-overlay"
        style={{
          background: 'rgba(0, 0, 0, 0.85)',
          backdropFilter: 'blur(8px)',
          borderRadius: 8,
          padding: '10px 16px',
          color: '#fff',
          minWidth: 140,
          border: isLastGame ? '1px solid rgba(239, 68, 68, 0.5)' : '1px solid rgba(255, 255, 255, 0.1)',
          boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
        }}
      >
        {isTimeMode ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, color: '#999', textTransform: 'uppercase', letterSpacing: 1 }}>
              Zeit
            </span>
            <span style={{
              fontSize: 20,
              fontWeight: 700,
              fontVariantNumeric: 'tabular-nums',
              color: data.time_remaining_seconds < 300 ? '#f59e0b' : '#fff',
            }}>
              {formatTime(data.time_remaining_seconds)}
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, color: '#999', textTransform: 'uppercase', letterSpacing: 1 }}>
              Spiele
            </span>
            <span style={{
              fontSize: 20,
              fontWeight: 700,
              fontVariantNumeric: 'tabular-nums',
              color: data.credits_remaining <= 1 ? '#f59e0b' : '#fff',
            }}>
              {data.credits_remaining}
            </span>
          </div>
        )}
        {isLastGame && (
          <div style={{
            fontSize: 10,
            color: '#ef4444',
            textTransform: 'uppercase',
            letterSpacing: 1,
            marginTop: 2,
          }}>
            Letztes Spiel
          </div>
        )}
      </div>
    </div>
  );
}

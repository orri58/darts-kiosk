import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { useSettings } from '../../context/SettingsContext';
import { useSoundManager } from '../../hooks/useSoundManager';
import { useBoardWS } from '../../hooks/useBoardWS';
import LockedScreen from './LockedScreen';
import SetupScreen from './SetupScreen';
import ObserverActiveScreen from './ObserverActiveScreen';
import InGameScreen from './InGameScreen';
import MatchResultScreen from './MatchResultScreen';
import ErrorScreen from './ErrorScreen';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATES = {
  LOCKED: 'locked',
  SETUP: 'setup',
  IN_GAME: 'in_game',
  OBSERVER_ACTIVE: 'observer_active',
  FINISHED: 'finished',
  ERROR: 'error'
};

export default function KioskLayout() {
  const { boardId = 'BOARD-1' } = useParams();
  const { branding, pricing, loading: settingsLoading } = useSettings();
  const { play: playSound } = useSoundManager(boardId);

  const handleWsEvent = useCallback((event, data) => {
    if (event === 'sound_event' && data?.board_id === boardId) {
      playSound(data.event);
    }
  }, [boardId, playSound]);
  useBoardWS(handleWsEvent);
  
  const [kioskState, setKioskState] = useState(STATES.LOCKED);
  const [session, setSession] = useState(null);
  const [autodartsMode, setAutodartsMode] = useState(null);
  const [observerBrowserOpen, setObserverBrowserOpen] = useState(false);
  const [observerState, setObserverState] = useState('closed');
  const [observerError, setObserverError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);
  const [matchToken, setMatchToken] = useState(null);
  const showingQrRef = useRef(false);

  const fetchBoardStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/boards/${boardId}/session`);
      const d = response.data;
      setSession(d.session);
      setAutodartsMode(d.autodarts_mode || null);
      setObserverBrowserOpen(d.observer_browser_open || false);
      setObserverState(d.observer_state || 'closed');
      setObserverError(d.observer_error || null);

      if (showingQrRef.current) return;

      const isObserver = d.autodarts_mode === 'observer';

      switch (d.board_status) {
        case 'locked':
          setKioskState(STATES.LOCKED);
          break;
        case 'unlocked':
          setKioskState(isObserver ? STATES.OBSERVER_ACTIVE : STATES.SETUP);
          break;
        case 'in_game':
          setKioskState(isObserver ? STATES.OBSERVER_ACTIVE : STATES.IN_GAME);
          break;
        default:
          setKioskState(STATES.LOCKED);
      }
    } catch (error) {
      console.error('Failed to fetch board status:', error);
      setKioskState(STATES.LOCKED);
    } finally {
      setLoading(false);
    }
  }, [boardId]);

  useEffect(() => {
    fetchBoardStatus();
    const interval = setInterval(fetchBoardStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchBoardStatus]);

  // Stable window title for Win32 window manager identification
  // Must run AFTER settings load to override branding title
  useEffect(() => {
    if (!settingsLoading) {
      document.title = 'DartsKiosk';
    }
  }, [settingsLoading]);

  // Fallback window management (non-kiosk-mode or non-Windows)
  // The real hiding is done by backend window_manager.py via Win32 API
  const prevBrowserOpenRef = useRef(false);
  useEffect(() => {
    if (observerBrowserOpen && !prevBrowserOpenRef.current) {
      try { window.blur(); } catch {}
    } else if (!observerBrowserOpen && prevBrowserOpenRef.current) {
      try { window.focus(); } catch {}
    }
    prevBrowserOpenRef.current = observerBrowserOpen;
  }, [observerBrowserOpen]);

  const handleStartGame = async (gameType, players) => {
    try {
      await axios.post(`${API}/kiosk/${boardId}/start-game`, {
        game_type: gameType,
        players: players
      });
      setKioskState(STATES.IN_GAME);
      playSound('start');
      toast.success('SPIEL GESTARTET!');
      fetchBoardStatus();
    } catch (error) {
      const msg = error.response?.data?.detail || 'Fehler beim Starten des Spiels';
      setErrorMessage(msg);
      setKioskState(STATES.ERROR);
      toast.error(msg);
    }
  };

  const handleEndGame = async () => {
    try {
      const response = await axios.post(`${API}/kiosk/${boardId}/end-game`);
      const { match_token } = response.data;

      if (match_token) {
        showingQrRef.current = true;
        setMatchToken(match_token);
        setKioskState(STATES.FINISHED);
        playSound('win');
      } else if (response.data.should_lock) {
        setKioskState(STATES.LOCKED);
        playSound('checkout');
        toast.info('Session beendet');
      } else {
        // Credits remaining — stay in observer active
        if (autodartsMode === 'observer') {
          setKioskState(STATES.OBSERVER_ACTIVE);
        } else {
          setKioskState(STATES.SETUP);
        }
        playSound('checkout');
        toast.success(`Noch ${response.data.credits_remaining} Spiele uebrig`);
      }
      fetchBoardStatus();
    } catch (error) {
      console.error('Failed to end game:', error);
    }
  };

  const handleMatchTimeout = useCallback(() => {
    showingQrRef.current = false;
    setMatchToken(null);
    setKioskState(STATES.LOCKED);
    fetchBoardStatus();
  }, [fetchBoardStatus]);

  const handleCallStaff = async () => {
    try {
      await axios.post(`${API}/kiosk/${boardId}/call-staff`);
      toast.success('Personal wurde benachrichtigt');
    } catch {
      toast.error('Fehler beim Benachrichtigen');
    }
  };

  const handleReturnToLocked = () => {
    setErrorMessage(null);
    setKioskState(STATES.LOCKED);
    fetchBoardStatus();
  };

  const handleRetry = () => {
    setErrorMessage(null);
    fetchBoardStatus();
  };

  if (loading || settingsLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[var(--color-bg)]" data-testid="kiosk-loading">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-zinc-400 font-heading uppercase tracking-wider">Lade...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-hidden bg-[var(--color-bg)] text-[var(--color-text)]" data-testid="kiosk-container">
      {kioskState === STATES.LOCKED && (
        <LockedScreen 
          branding={branding} 
          pricing={pricing}
          boardId={boardId}
        />
      )}

      {kioskState === STATES.OBSERVER_ACTIVE && (
        <ObserverActiveScreen
          branding={branding}
          session={session}
          boardId={boardId}
          observerBrowserOpen={observerBrowserOpen}
          observerState={observerState}
          observerError={observerError}
          onEndGame={handleEndGame}
          onCallStaff={handleCallStaff}
        />
      )}

      {kioskState === STATES.SETUP && (
        <SetupScreen 
          branding={branding}
          pricing={pricing}
          session={session}
          onStartGame={handleStartGame}
        />
      )}

      {kioskState === STATES.IN_GAME && (
        <InGameScreen 
          branding={branding}
          session={session}
          onEndGame={handleEndGame}
          onCallStaff={handleCallStaff}
        />
      )}

      {kioskState === STATES.ERROR && (
        <ErrorScreen
          message={errorMessage}
          onRetry={handleRetry}
          onLock={handleReturnToLocked}
          onCallStaff={handleCallStaff}
        />
      )}

      {kioskState === STATES.FINISHED && matchToken && (
        <MatchResultScreen
          branding={branding}
          matchToken={matchToken}
          session={session}
          onTimeout={handleMatchTimeout}
        />
      )}
    </div>
  );
}

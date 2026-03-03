import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { useSettings } from '../../context/SettingsContext';
import LockedScreen from './LockedScreen';
import SetupScreen from './SetupScreen';
import InGameScreen from './InGameScreen';
import ErrorScreen from './ErrorScreen';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Kiosk states
const STATES = {
  LOCKED: 'locked',
  SETUP: 'setup',
  IN_GAME: 'in_game',
  FINISHED: 'finished',
  ERROR: 'error'
};

export default function KioskLayout() {
  const { boardId = 'BOARD-1' } = useParams();
  const { branding, pricing, loading: settingsLoading } = useSettings();
  
  const [kioskState, setKioskState] = useState(STATES.LOCKED);
  const [session, setSession] = useState(null);
  const [boardStatus, setBoardStatus] = useState('locked');
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);

  // Fetch board session status
  const fetchBoardStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/boards/${boardId}/session`);
      setBoardStatus(response.data.board_status);
      setSession(response.data.session);
      
      // Determine kiosk state based on board status
      switch (response.data.board_status) {
        case 'locked':
          setKioskState(STATES.LOCKED);
          break;
        case 'unlocked':
          setKioskState(STATES.SETUP);
          break;
        case 'in_game':
          setKioskState(STATES.IN_GAME);
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

  // Poll for status updates
  useEffect(() => {
    fetchBoardStatus();
    const interval = setInterval(fetchBoardStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchBoardStatus]);

  // Handle game start
  const handleStartGame = async (gameType, players) => {
    try {
      await axios.post(`${API}/kiosk/${boardId}/start-game`, {
        game_type: gameType,
        players: players
      });
      setKioskState(STATES.IN_GAME);
      toast.success('SPIEL GESTARTET!');
      fetchBoardStatus();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Fehler beim Starten des Spiels';
      setErrorMessage(errorMsg);
      setKioskState(STATES.ERROR);
      toast.error(errorMsg);
    }
  };

  // Handle game end
  const handleEndGame = async () => {
    try {
      const response = await axios.post(`${API}/kiosk/${boardId}/end-game`);
      if (response.data.should_lock) {
        setKioskState(STATES.LOCKED);
        toast.info('Session beendet');
      } else {
        setKioskState(STATES.SETUP);
        toast.success(`Noch ${response.data.credits_remaining} Spiele übrig`);
      }
      fetchBoardStatus();
    } catch (error) {
      console.error('Failed to end game:', error);
    }
  };

  // Handle call staff
  const handleCallStaff = async () => {
    try {
      await axios.post(`${API}/kiosk/${boardId}/call-staff`);
      toast.success('Personal wurde benachrichtigt');
    } catch (error) {
      toast.error('Fehler beim Benachrichtigen');
    }
  };

  // Handle return to locked from error state
  const handleReturnToLocked = () => {
    setErrorMessage(null);
    setKioskState(STATES.LOCKED);
    fetchBoardStatus();
  };

  // Handle retry from error state
  const handleRetry = () => {
    setErrorMessage(null);
    fetchBoardStatus();
  };

  if (loading || settingsLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[var(--color-bg)]" data-testid="kiosk-loading">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
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
    </div>
  );
}

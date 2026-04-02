import { useState, useRef, useEffect, useCallback } from 'react';
import { Target, Users, Play, ChevronRight, Delete, Clock, Coins, ShieldCheck, Lock, UserPlus, X, CheckCircle } from 'lucide-react';
import Keyboard from 'react-simple-keyboard';
import 'react-simple-keyboard/build/css/index.css';
import { Button } from '../../components/ui/button';
import { useI18n } from '../../context/I18nContext';
import axios from 'axios';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const GAME_TYPES = [
  { id: '301', name: '301', description: 'Klassisch' },
  { id: '501', name: '501', description: 'Standard' },
  { id: 'Cricket', name: 'CRICKET', description: 'Strategie' },
  { id: 'Training', name: 'TRAINING', description: 'Übungsmodus' },
];

// PIN Pad component for Stammkunde authentication
function PinPad({ title, subtitle, onSubmit, onCancel, error, loading }) {
  const [pin, setPin] = useState('');

  // Reset pin when title changes (e.g., switching from "Stammkunde werden" to "PIN bestätigen")
  useEffect(() => {
    setPin('');
  }, [title]);

  const handleDigit = (d) => {
    if (pin.length < 6) setPin(pin + d);
  };
  const handleDelete = () => setPin(pin.slice(0, -1));
  const handleOk = () => { if (pin.length >= 4) onSubmit(pin); };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm" data-testid="pin-modal">
      <div className="bg-zinc-900 border border-zinc-700 rounded-sm p-8 w-full max-w-md">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Lock className="w-6 h-6 text-amber-500" />
            <h3 className="text-xl font-heading uppercase tracking-wider text-white">{title}</h3>
          </div>
          <button onClick={onCancel} className="text-zinc-500 hover:text-white" data-testid="pin-modal-close">
            <X className="w-6 h-6" />
          </button>
        </div>
        {subtitle && <p className="text-zinc-400 text-sm mb-6">{subtitle}</p>}

        {/* PIN dots */}
        <div className="flex justify-center gap-3 mb-6" data-testid="pin-dots">
          {[0,1,2,3,4,5].map(i => (
            <div key={i} className={`w-5 h-5 rounded-full border-2 transition-all ${
              i < pin.length ? 'bg-amber-500 border-amber-500' : 'border-zinc-600'
            }`} />
          ))}
        </div>

        {error && <p className="text-red-500 text-center text-sm mb-4" data-testid="pin-error">{error}</p>}

        {/* Digit grid */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          {[1,2,3,4,5,6,7,8,9].map(d => (
            <button key={d} onClick={() => handleDigit(String(d))} data-testid={`pin-digit-${d}`}
              className="h-16 bg-zinc-800 hover:bg-zinc-700 text-white text-2xl font-mono rounded-sm border border-zinc-700 transition-colors">
              {d}
            </button>
          ))}
          <button onClick={handleDelete} data-testid="pin-delete"
            className="h-16 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-lg rounded-sm border border-zinc-700">
            <Delete className="w-6 h-6 mx-auto" />
          </button>
          <button onClick={() => handleDigit('0')} data-testid="pin-digit-0"
            className="h-16 bg-zinc-800 hover:bg-zinc-700 text-white text-2xl font-mono rounded-sm border border-zinc-700">
            0
          </button>
          <button onClick={handleOk} disabled={pin.length < 4 || loading} data-testid="pin-submit"
            className={`h-16 rounded-sm border text-lg font-heading uppercase ${
              pin.length >= 4 ? 'bg-amber-500 hover:bg-amber-400 text-black border-amber-400' : 'bg-zinc-800 text-zinc-600 border-zinc-700'
            }`}>
            {loading ? '...' : 'OK'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SetupScreen({ branding, pricing, session, onStartGame }) {
  const [step, setStep] = useState(1);
  const { t } = useI18n();
  const [selectedGame, setSelectedGame] = useState(null);
  const [players, setPlayers] = useState(['']);
  const [activePlayerIndex, setActivePlayerIndex] = useState(0);
  const [showKeyboard, setShowKeyboard] = useState(false);
  const keyboardRef = useRef(null);

  // Stammkunde state
  const [playerAuth, setPlayerAuth] = useState({}); // index -> { status: 'guest'|'needs_pin'|'verified'|'checking', nickname, player_id }
  const [pinModalIndex, setPinModalIndex] = useState(null); // which player index needs PIN
  const [pinModalMode, setPinModalMode] = useState('login'); // 'login' or 'register'
  const [pinError, setPinError] = useState('');
  const [pinLoading, setPinLoading] = useState(false);
  const [registerStep, setRegisterStep] = useState(0); // 0=none, 1=first pin, 2=confirm pin
  const [firstPin, setFirstPin] = useState('');

  const maxPlayers = pricing?.max_players || 4;

  const getRemainingInfo = () => {
    if (!session) return null;
    if (session.pricing_mode === 'per_game' || session.pricing_mode === 'per_player') {
      const credits = session.credits_remaining;
      if (session.pricing_mode === 'per_player') {
        return { type: 'credits', value: credits, label: 'Credits verfügbar' };
      }
      if (credits === 1) {
        return { type: 'credits', value: credits, label: t('last_game') };
      }
      return { type: 'credits', value: credits, label: t('games_remaining') };
    }
    if (session.pricing_mode === 'per_time' && session.expires_at) {
      const minutesLeft = Math.max(0, Math.round((new Date(session.expires_at) - new Date()) / 60000));
      return { type: 'time', value: minutesLeft, label: t('minutes_remaining') };
    }
    return null;
  };
  const remainingInfo = getRemainingInfo();

  // Check if nickname is registered
  const checkPlayer = useCallback(async (index) => {
    const name = players[index]?.trim();
    if (!name || name.length < 2) return;

    setPlayerAuth(prev => ({ ...prev, [index]: { status: 'checking', nickname: name } }));
    try {
      const { data } = await axios.post(`${API}/players/check`, { nickname: name });
      if (data.is_registered) {
        setPlayerAuth(prev => ({ ...prev, [index]: { status: 'needs_pin', nickname: data.nickname, player_id: data.player_id } }));
        setPinModalIndex(index);
        setPinModalMode('login');
        setPinError('');
      } else {
        setPlayerAuth(prev => ({ ...prev, [index]: { status: 'guest', nickname: name } }));
      }
    } catch {
      setPlayerAuth(prev => ({ ...prev, [index]: { status: 'guest', nickname: name } }));
    }
  }, [players]);

  // Handle keyboard input
  const handleKeyboardChange = (input) => {
    const newPlayers = [...players];
    newPlayers[activePlayerIndex] = input;
    setPlayers(newPlayers);
    // Clear auth state when name changes
    if (playerAuth[activePlayerIndex]?.nickname?.toLowerCase() !== input.trim().toLowerCase()) {
      setPlayerAuth(prev => { const n = {...prev}; delete n[activePlayerIndex]; return n; });
    }
  };

  const handleKeyPress = (button) => {
    if (button === '{bksp}') {
      const newPlayers = [...players];
      newPlayers[activePlayerIndex] = newPlayers[activePlayerIndex].slice(0, -1);
      setPlayers(newPlayers);
    }
    if (button === '{enter}') {
      const name = players[activePlayerIndex]?.trim();
      if (name && name.length >= 2) {
        checkPlayer(activePlayerIndex);
        setShowKeyboard(false);
      }
      if (activePlayerIndex < players.length - 1) {
        setActivePlayerIndex(activePlayerIndex + 1);
        if (keyboardRef.current) {
          keyboardRef.current.setInput(players[activePlayerIndex + 1] || '');
        }
      } else {
        setShowKeyboard(false);
      }
    }
  };

  const addPlayer = () => {
    if (players.length < maxPlayers) {
      setPlayers([...players, '']);
      setActivePlayerIndex(players.length);
      setShowKeyboard(true);
      setTimeout(() => { if (keyboardRef.current) keyboardRef.current.setInput(''); }, 50);
    }
  };

  const removePlayer = (index) => {
    if (players.length > 1) {
      const newPlayers = players.filter((_, i) => i !== index);
      setPlayers(newPlayers);
      // Clean up auth state
      setPlayerAuth(prev => {
        const n = {};
        Object.entries(prev).forEach(([k, v]) => {
          const ki = parseInt(k);
          if (ki < index) n[ki] = v;
          else if (ki > index) n[ki - 1] = v;
        });
        return n;
      });
      if (activePlayerIndex >= newPlayers.length) setActivePlayerIndex(newPlayers.length - 1);
    }
  };

  const focusPlayer = (index) => {
    setActivePlayerIndex(index);
    setShowKeyboard(true);
    setTimeout(() => { if (keyboardRef.current) keyboardRef.current.setInput(players[index] || ''); }, 50);
  };

  // PIN login for registered player
  const handlePinLogin = async (pin) => {
    if (pinModalIndex === null) return;
    setPinLoading(true);
    setPinError('');
    try {
      const nickname = players[pinModalIndex]?.trim();
      const { data } = await axios.post(`${API}/players/pin-login`, { nickname, pin });
      setPlayerAuth(prev => ({ ...prev, [pinModalIndex]: { status: 'verified', nickname: data.nickname, player_id: data.player_id } }));
      setPinModalIndex(null);
      toast.success(t('welcome_back', { name: data.nickname }));
    } catch (err) {
      setPinError(err.response?.data?.detail || t('wrong_pin'));
    } finally {
      setPinLoading(false);
    }
  };

  // Registration flow
  const handleStartRegister = (index) => {
    setPinModalIndex(index);
    setPinModalMode('register');
    setRegisterStep(1);
    setFirstPin('');
    setPinError('');
  };

  const handleRegisterPin = async (pin) => {
    if (registerStep === 1) {
      setFirstPin(pin);
      setRegisterStep(2);
      setPinError('');
      return;
    }
    // Step 2: confirm PIN
    if (pin !== firstPin) {
      setPinError(t('pins_dont_match'));
      setRegisterStep(1);
      setFirstPin('');
      return;
    }
    setPinLoading(true);
    setPinError('');
    try {
      const nickname = players[pinModalIndex]?.trim();
      const { data } = await axios.post(`${API}/players/register`, { nickname, pin });
      setPlayerAuth(prev => ({ ...prev, [pinModalIndex]: { status: 'verified', nickname: data.nickname, player_id: data.player_id, qr_token: data.qr_token } }));
      setPinModalIndex(null);
      setRegisterStep(0);
      toast.success(t('registered_as_stammkunde', { name: data.nickname }));
    } catch (err) {
      setPinError(err.response?.data?.detail || 'Registrierung fehlgeschlagen');
    } finally {
      setPinLoading(false);
    }
  };

  const closePinModal = () => {
    if (pinModalMode === 'login') {
      // If they cancel login, mark as guest to allow playing without auth
      setPlayerAuth(prev => ({ ...prev, [pinModalIndex]: { status: 'guest', nickname: players[pinModalIndex]?.trim() } }));
    }
    setPinModalIndex(null);
    setRegisterStep(0);
    setFirstPin('');
    setPinError('');
  };

  // Check if all players with needs_pin have been verified or dismissed
  const canStart = selectedGame && players.some(p => p.trim().length > 0) &&
    !Object.values(playerAuth).some(a => a.status === 'needs_pin' || a.status === 'checking');

  const handleStart = () => {
    const validPlayers = players.filter(p => p.trim().length > 0);
    if (validPlayers.length > 0 && selectedGame) {
      onStartGame(selectedGame, validPlayers);
    }
  };

  useEffect(() => {
    if (keyboardRef.current && showKeyboard) {
      keyboardRef.current.setInput(players[activePlayerIndex] || '');
    }
  }, [activePlayerIndex, showKeyboard, players]);

  // Get auth badge for a player
  const getPlayerBadge = (index) => {
    const auth = playerAuth[index];
    if (!auth) return null;
    if (auth.status === 'verified') {
      return (
        <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-sm" data-testid={`player-verified-${index}`}>
          <ShieldCheck className="w-3.5 h-3.5" /> {t('stammkunde')}
        </span>
      );
    }
    if (auth.status === 'needs_pin') {
      return (
        <span className="flex items-center gap-1 text-xs text-amber-400 bg-amber-400/10 px-2 py-1 rounded-sm animate-pulse" data-testid={`player-needs-pin-${index}`}>
          <Lock className="w-3.5 h-3.5" /> {t('pin_required')}
        </span>
      );
    }
    if (auth.status === 'checking') {
      return <span className="text-xs text-zinc-500">{t('checking')}</span>;
    }
    return null;
  };

  return (
    <div className="h-full w-full flex flex-col" data-testid="setup-screen">
      {/* Header */}
      <div className="border-b border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.88)] px-4 py-4 backdrop-blur lg:px-6">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-heading font-bold uppercase tracking-wider text-[var(--color-text)] lg:text-2xl">
              {branding.cafe_name}
            </h1>
            <p className="text-sm text-[var(--color-text-secondary)]">{t('game_preparation')}</p>
          </div>
          {remainingInfo && (
            <div className="flex items-center gap-3 rounded-2xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.72)] px-4 py-2.5">
              {remainingInfo.type === 'credits' ? <Coins className="w-5 h-5 text-[var(--color-primary)]" /> : <Clock className="w-5 h-5 text-[var(--color-primary)]" />}
              <div className="text-right">
                <p className="text-2xl font-mono font-bold text-[var(--color-text)]">{remainingInfo.value}</p>
                <p className="text-xs uppercase text-[var(--color-text-secondary)]">{remainingInfo.label}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto px-4 py-5 lg:px-6 lg:py-6">
        <div className="max-w-6xl mx-auto">
          <div className="mb-6 grid gap-4 lg:grid-cols-[1.15fr,0.85fr]">
            <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.68)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
              <p className="mb-3 text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Setup flow</p>
              <div className="grid gap-3 md:grid-cols-2">
                <div className={`rounded-2xl border px-4 py-3 ${step === 1 ? 'border-[rgb(var(--color-primary-rgb)/0.4)] bg-[rgb(var(--color-primary-rgb)/0.1)]' : 'border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.46)]'}`}>
                  <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Schritt 1</p>
                  <p className="mt-1 font-medium text-[var(--color-text)]">Spiel wählen</p>
                  <p className="mt-1 text-sm text-[var(--color-text-secondary)]">301, 501, Cricket oder Training.</p>
                </div>
                <div className={`rounded-2xl border px-4 py-3 ${step === 2 ? 'border-[rgb(var(--color-primary-rgb)/0.4)] bg-[rgb(var(--color-primary-rgb)/0.1)]' : 'border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.46)]'}`}>
                  <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Schritt 2</p>
                  <p className="mt-1 font-medium text-[var(--color-text)]">Spieler vorbereiten</p>
                  <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Namen, PIN, Start.</p>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.68)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]">
              <p className="mb-3 text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Session summary</p>
              <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.46)] px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Modus</p>
                  <p className="mt-1 font-medium text-[var(--color-text)]">{session?.pricing_mode === 'per_time' ? 'Zeitbasiert' : session?.pricing_mode === 'per_player' ? 'Credits / Matchstart' : 'Spielbasiert (Legacy)'}</p>
                </div>
                <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.46)] px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Spiel</p>
                  <p className="mt-1 font-medium text-[var(--color-text)]">{selectedGame || 'Noch nicht gewählt'}</p>
                </div>
                <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.46)] px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Spieler</p>
                  <p className="mt-1 font-medium text-[var(--color-text)]">{players.filter(p => p.trim().length > 0).length} / {maxPlayers}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Step 1: Game Type */}
          {step === 1 && (
            <div className="animate-slide-up" data-testid="step-game-type">
              <div className="mb-6 flex items-center gap-3">
                <Target className="w-7 h-7 text-[var(--color-primary)]" />
                <h2 className="text-2xl font-heading uppercase tracking-wider text-[var(--color-text)] lg:text-3xl">{t('choose_game_type')}</h2>
              </div>
              <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4 lg:gap-5">
                {GAME_TYPES.map((game) => (
                  <button key={game.id} onClick={() => setSelectedGame(game.id)} data-testid={`game-type-${game.id.toLowerCase()}`}
                    className={`btn-kiosk flex min-h-[104px] flex-col items-center justify-center rounded-3xl p-5 ${
                      selectedGame === game.id ? 'animate-pulse-glow border-[rgb(var(--color-primary-rgb)/0.35)] bg-[var(--color-primary)] text-[hsl(var(--primary-foreground))]' : 'border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.72)] text-[var(--color-text)] hover:border-[rgb(var(--color-primary-rgb)/0.35)]'
                    }`}>
                    <span className="mb-1 text-4xl font-heading font-bold lg:text-5xl">{game.name}</span>
                    <span className={`text-xs uppercase tracking-wider ${selectedGame === game.id ? 'text-black/70' : 'text-[var(--color-text-secondary)]'}`}>{game.description}</span>
                  </button>
                ))}
              </div>
              {selectedGame && (
                <div className="flex justify-center">
                  <Button onClick={() => setStep(2)} data-testid="next-to-players-btn"
                    className="btn-industrial h-16 rounded-3xl bg-[var(--color-primary)] px-10 text-xl text-[hsl(var(--primary-foreground))] hover:opacity-90 lg:h-20 lg:px-16 lg:text-2xl">
                    <span>{t('next')}</span>
                    <ChevronRight className="w-8 h-8 ml-2" />
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Step 2: Player Names + Stammkunde Auth */}
          {step === 2 && (
            <div className="animate-slide-up" data-testid="step-players">
              <button onClick={() => setStep(1)} className="mb-5 flex items-center gap-2 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text)]">
                <ChevronRight className="w-5 h-5 rotate-180" />
                <span className="uppercase tracking-wider text-sm">{t('back')}</span>
              </button>

              <div className="mb-6 flex flex-wrap items-center gap-3">
                <Users className="w-7 h-7 text-[var(--color-primary)]" />
                <h2 className="text-2xl font-heading uppercase tracking-wider text-[var(--color-text)] lg:text-3xl">{t('enter_player_names')}</h2>
                <span className="ml-auto text-lg text-[var(--color-text-secondary)]">
                  {t('game_type')}: <span className="font-heading text-[var(--color-primary)]">{selectedGame}</span>
                </span>
              </div>

              {/* Player Inputs */}
              <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-2">
                {players.map((player, index) => (
                  <div key={index} onClick={() => focusPlayer(index)}
                    className={`relative flex cursor-pointer items-center rounded-2xl border-2 bg-[rgb(var(--color-surface-rgb)/0.7)] p-4 transition-all ${
                      activePlayerIndex === index && showKeyboard ? 'border-[rgb(var(--color-primary-rgb)/0.45)] ring-2 ring-[rgb(var(--color-primary-rgb)/0.24)]' : 'border-[rgb(var(--color-border-rgb)/0.82)] hover:border-[rgb(var(--color-primary-rgb)/0.28)]'
                    } ${playerAuth[index]?.status === 'verified' ? 'border-emerald-500/50' : ''}`}>
                    <div className={`mr-4 flex h-12 w-12 items-center justify-center rounded-2xl ${
                      playerAuth[index]?.status === 'verified' ? 'bg-emerald-500/20' : 'bg-[rgb(var(--color-bg-rgb)/0.58)]'
                    }`}>
                      {playerAuth[index]?.status === 'verified'
                        ? <CheckCircle className="w-6 h-6 text-emerald-400" />
                        : <span className="text-xl font-heading text-[var(--color-primary)]">{index + 1}</span>
                      }
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-xs uppercase text-[var(--color-text-muted)]">{t('player')} {index + 1}</p>
                        {getPlayerBadge(index)}
                      </div>
                      <p className="min-h-[28px] text-xl font-mono text-[var(--color-text)]">
                        {player || <span className="text-[var(--color-text-muted)]">{t('enter_name')}</span>}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* Register as Stammkunde button */}
                      {player.trim().length >= 2 && playerAuth[index]?.status === 'guest' && (
                        <button onClick={(e) => { e.stopPropagation(); handleStartRegister(index); }}
                          className="p-2 text-zinc-500 hover:text-amber-500 transition-colors" title="Als Stammkunde registrieren"
                          data-testid={`register-player-${index}`}>
                          <UserPlus className="w-5 h-5" />
                        </button>
                      )}
                      {/* PIN re-enter for needs_pin */}
                      {playerAuth[index]?.status === 'needs_pin' && (
                        <button onClick={(e) => { e.stopPropagation(); setPinModalIndex(index); setPinModalMode('login'); setPinError(''); }}
                          className="p-2 text-amber-400 hover:text-amber-300 transition-colors animate-pulse" title="PIN eingeben"
                          data-testid={`pin-retry-${index}`}>
                          <Lock className="w-5 h-5" />
                        </button>
                      )}
                      {players.length > 1 && (
                        <button onClick={(e) => { e.stopPropagation(); removePlayer(index); }}
                          className="p-2 text-zinc-600 hover:text-red-500 transition-colors" data-testid={`remove-player-${index}`}>
                          <Delete className="w-6 h-6" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                {players.length < maxPlayers && (
                  <button onClick={addPlayer} data-testid="add-player-btn"
                    className="flex min-h-[96px] items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.42)] p-4 text-[var(--color-text-secondary)] transition-all hover:border-[rgb(var(--color-primary-rgb)/0.4)] hover:text-[var(--color-primary)]">
                    <Users className="w-6 h-6" />
                    <span className="uppercase tracking-wider">{t('add_player')}</span>
                  </button>
                )}
              </div>

              {/* Virtual Keyboard */}
              {showKeyboard && (
                <div className="mb-8" data-testid="virtual-keyboard">
                  <Keyboard
                    keyboardRef={(r) => (keyboardRef.current = r)}
                    onChange={handleKeyboardChange}
                    onKeyPress={handleKeyPress}
                    layout={{
                      default: [
                        '1 2 3 4 5 6 7 8 9 0',
                        'Q W E R T Z U I O P',
                        'A S D F G H J K L',
                        'Y X C V B N M {bksp}',
                        '{space} {enter}'
                      ]
                    }}
                    display={{ '{bksp}': '\u232b', '{enter}': 'OK', '{space}': 'SPACE' }}
                    theme="hg-theme-default"
                  />
                </div>
              )}

              {/* Start Button */}
              <div className="flex justify-center">
                <Button onClick={handleStart} disabled={!canStart} data-testid="start-game-btn"
                  className={`btn-industrial h-16 rounded-3xl px-10 text-xl lg:h-20 lg:px-16 lg:text-2xl ${
                    canStart ? 'animate-pulse-glow bg-emerald-500 text-black hover:bg-emerald-400' : 'cursor-not-allowed bg-[rgb(var(--color-border-rgb)/0.8)] text-[var(--color-text-muted)]'
                  }`}>
                  <Play className="mr-3 h-8 w-8 lg:h-9 lg:w-9" />
                  <span>{t('start')}</span>
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* PIN Modal */}
      {pinModalIndex !== null && pinModalMode === 'login' && (
        <PinPad
          title={t('stammkunde_login')}
          subtitle={t('enter_pin_for', { name: players[pinModalIndex]?.trim() })}
          onSubmit={handlePinLogin}
          onCancel={closePinModal}
          error={pinError}
          loading={pinLoading}
        />
      )}

      {/* Register PIN Modal */}
      {pinModalIndex !== null && pinModalMode === 'register' && (
        <PinPad
          title={registerStep === 1 ? t('become_stammkunde_title') : t('confirm_pin')}
          subtitle={registerStep === 1
            ? t('choose_pin', { name: players[pinModalIndex]?.trim() })
            : t('confirm_pin_desc')
          }
          onSubmit={handleRegisterPin}
          onCancel={closePinModal}
          error={pinError}
          loading={pinLoading}
        />
      )}
    </div>
  );
}

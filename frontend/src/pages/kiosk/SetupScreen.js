import { useState, useRef, useEffect, useCallback } from 'react';
import { Target, Users, Play, ChevronRight, Delete, Clock, Coins, ShieldCheck, Lock, UserPlus, X, CheckCircle } from 'lucide-react';
import Keyboard from 'react-simple-keyboard';
import 'react-simple-keyboard/build/css/index.css';
import { Button } from '../../components/ui/button';
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
    if (session.pricing_mode === 'per_game') {
      return { type: 'credits', value: session.credits_remaining, label: 'Spiele übrig' };
    }
    if (session.pricing_mode === 'per_time' && session.expires_at) {
      const minutesLeft = Math.max(0, Math.round((new Date(session.expires_at) - new Date()) / 60000));
      return { type: 'time', value: minutesLeft, label: 'Minuten übrig' };
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
      toast.success(`Willkommen zurück, ${data.nickname}!`);
    } catch (err) {
      setPinError(err.response?.data?.detail || 'Falscher PIN');
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
      setPinError('PINs stimmen nicht überein');
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
      toast.success(`${data.nickname} als Stammkunde registriert!`);
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
          <ShieldCheck className="w-3.5 h-3.5" /> Stammkunde
        </span>
      );
    }
    if (auth.status === 'needs_pin') {
      return (
        <span className="flex items-center gap-1 text-xs text-amber-400 bg-amber-400/10 px-2 py-1 rounded-sm animate-pulse" data-testid={`player-needs-pin-${index}`}>
          <Lock className="w-3.5 h-3.5" /> PIN erforderlich
        </span>
      );
    }
    if (auth.status === 'checking') {
      return <span className="text-xs text-zinc-500">Prüfe...</span>;
    }
    return null;
  };

  return (
    <div className="h-full w-full flex flex-col" data-testid="setup-screen">
      {/* Header */}
      <div className="p-6 border-b border-zinc-800 bg-zinc-950">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <div>
            <h1 className="text-2xl font-heading font-bold uppercase tracking-wider text-white">
              {branding.cafe_name}
            </h1>
            <p className="text-zinc-500 text-sm">Spielvorbereitung</p>
          </div>
          {remainingInfo && (
            <div className="flex items-center gap-3 bg-zinc-900 border border-zinc-700 rounded-sm px-4 py-2">
              {remainingInfo.type === 'credits' ? <Coins className="w-5 h-5 text-amber-500" /> : <Clock className="w-5 h-5 text-amber-500" />}
              <div className="text-right">
                <p className="text-2xl font-mono font-bold text-white">{remainingInfo.value}</p>
                <p className="text-xs text-zinc-500 uppercase">{remainingInfo.label}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-6xl mx-auto">
          {/* Step 1: Game Type */}
          {step === 1 && (
            <div className="animate-slide-up" data-testid="step-game-type">
              <div className="flex items-center gap-3 mb-8">
                <Target className="w-8 h-8 text-amber-500" />
                <h2 className="text-3xl font-heading uppercase tracking-wider text-white">Spielart wählen</h2>
              </div>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
                {GAME_TYPES.map((game) => (
                  <button key={game.id} onClick={() => setSelectedGame(game.id)} data-testid={`game-type-${game.id.toLowerCase()}`}
                    className={`btn-kiosk flex flex-col items-center justify-center p-8 rounded-sm ${
                      selectedGame === game.id ? 'bg-amber-500 text-black border-amber-400 animate-pulse-glow' : 'bg-zinc-900 text-white border-zinc-700 hover:border-amber-500/50'
                    }`}>
                    <span className="text-5xl font-heading font-bold mb-2">{game.name}</span>
                    <span className={`text-sm uppercase tracking-wider ${selectedGame === game.id ? 'text-black/70' : 'text-zinc-500'}`}>{game.description}</span>
                  </button>
                ))}
              </div>
              {selectedGame && (
                <div className="flex justify-center">
                  <Button onClick={() => setStep(2)} data-testid="next-to-players-btn"
                    className="btn-industrial h-20 px-16 text-2xl bg-amber-500 hover:bg-amber-400 text-black">
                    <span>WEITER</span>
                    <ChevronRight className="w-8 h-8 ml-2" />
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Step 2: Player Names + Stammkunde Auth */}
          {step === 2 && (
            <div className="animate-slide-up" data-testid="step-players">
              <button onClick={() => setStep(1)} className="flex items-center gap-2 text-zinc-500 hover:text-white mb-6 transition-colors">
                <ChevronRight className="w-5 h-5 rotate-180" />
                <span className="uppercase tracking-wider text-sm">Zurück</span>
              </button>

              <div className="flex items-center gap-3 mb-8">
                <Users className="w-8 h-8 text-amber-500" />
                <h2 className="text-3xl font-heading uppercase tracking-wider text-white">Spielernamen eingeben</h2>
                <span className="text-xl text-zinc-500 ml-auto">
                  Spielart: <span className="text-amber-500 font-heading">{selectedGame}</span>
                </span>
              </div>

              {/* Player Inputs */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                {players.map((player, index) => (
                  <div key={index} onClick={() => focusPlayer(index)}
                    className={`relative flex items-center bg-zinc-900 border-2 rounded-sm p-4 cursor-pointer transition-all ${
                      activePlayerIndex === index && showKeyboard ? 'border-amber-500 ring-2 ring-amber-500/30' : 'border-zinc-700 hover:border-zinc-600'
                    } ${playerAuth[index]?.status === 'verified' ? 'border-emerald-500/50' : ''}`}>
                    <div className={`w-12 h-12 rounded-sm flex items-center justify-center mr-4 ${
                      playerAuth[index]?.status === 'verified' ? 'bg-emerald-500/20' : 'bg-zinc-800'
                    }`}>
                      {playerAuth[index]?.status === 'verified'
                        ? <CheckCircle className="w-6 h-6 text-emerald-400" />
                        : <span className="text-xl font-heading text-amber-500">{index + 1}</span>
                      }
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-xs text-zinc-500 uppercase">Spieler {index + 1}</p>
                        {getPlayerBadge(index)}
                      </div>
                      <p className="text-xl font-mono text-white min-h-[28px]">
                        {player || <span className="text-zinc-600">Name eingeben...</span>}
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
                    className="flex items-center justify-center gap-3 bg-zinc-900/50 border-2 border-dashed border-zinc-700 rounded-sm p-4 text-zinc-500 hover:border-amber-500/50 hover:text-amber-500 transition-all min-h-[96px]">
                    <Users className="w-6 h-6" />
                    <span className="uppercase tracking-wider">Spieler hinzufügen</span>
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
                  className={`btn-industrial h-24 px-20 text-3xl ${
                    canStart ? 'bg-emerald-500 hover:bg-emerald-400 text-black animate-pulse-glow' : 'bg-zinc-700 text-zinc-500 cursor-not-allowed'
                  }`}>
                  <Play className="w-10 h-10 mr-3" />
                  <span>START</span>
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* PIN Modal */}
      {pinModalIndex !== null && pinModalMode === 'login' && (
        <PinPad
          title="Stammkunde Login"
          subtitle={`PIN für "${players[pinModalIndex]?.trim()}" eingeben`}
          onSubmit={handlePinLogin}
          onCancel={closePinModal}
          error={pinError}
          loading={pinLoading}
        />
      )}

      {/* Register PIN Modal */}
      {pinModalIndex !== null && pinModalMode === 'register' && (
        <PinPad
          title={registerStep === 1 ? 'Stammkunde werden' : 'PIN bestätigen'}
          subtitle={registerStep === 1
            ? `Wähle einen 4-6 stelligen PIN für "${players[pinModalIndex]?.trim()}"`
            : 'PIN zur Bestätigung erneut eingeben'
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

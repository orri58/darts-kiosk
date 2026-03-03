import { useState, useRef, useEffect } from 'react';
import { Target, Users, Play, ChevronRight, Delete, Clock, Coins } from 'lucide-react';
import Keyboard from 'react-simple-keyboard';
import 'react-simple-keyboard/build/css/index.css';
import { Button } from '../../components/ui/button';

const GAME_TYPES = [
  { id: '301', name: '301', description: 'Klassisch' },
  { id: '501', name: '501', description: 'Standard' },
  { id: 'Cricket', name: 'CRICKET', description: 'Strategie' },
  { id: 'Training', name: 'TRAINING', description: 'Übungsmodus' },
];

export default function SetupScreen({ branding, pricing, session, onStartGame }) {
  const [step, setStep] = useState(1); // 1 = game type, 2 = player names
  const [selectedGame, setSelectedGame] = useState(null);
  const [players, setPlayers] = useState(['']);
  const [activePlayerIndex, setActivePlayerIndex] = useState(0);
  const [showKeyboard, setShowKeyboard] = useState(false);
  const keyboardRef = useRef(null);

  const maxPlayers = pricing?.max_players || 4;

  // Calculate remaining info
  const getRemainingInfo = () => {
    if (!session) return null;
    
    if (session.pricing_mode === 'per_game') {
      return {
        type: 'credits',
        value: session.credits_remaining,
        label: 'Spiele übrig'
      };
    }
    
    if (session.pricing_mode === 'per_time' && session.expires_at) {
      const expiresAt = new Date(session.expires_at);
      const now = new Date();
      const minutesLeft = Math.max(0, Math.round((expiresAt - now) / 60000));
      return {
        type: 'time',
        value: minutesLeft,
        label: 'Minuten übrig'
      };
    }
    
    return null;
  };

  const remainingInfo = getRemainingInfo();

  // Handle keyboard input
  const handleKeyboardChange = (input) => {
    const newPlayers = [...players];
    newPlayers[activePlayerIndex] = input;
    setPlayers(newPlayers);
  };

  const handleKeyPress = (button) => {
    if (button === '{bksp}') {
      const newPlayers = [...players];
      newPlayers[activePlayerIndex] = newPlayers[activePlayerIndex].slice(0, -1);
      setPlayers(newPlayers);
    }
    if (button === '{enter}') {
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

  // Add player slot
  const addPlayer = () => {
    if (players.length < maxPlayers) {
      setPlayers([...players, '']);
      setActivePlayerIndex(players.length);
      setShowKeyboard(true);
      setTimeout(() => {
        if (keyboardRef.current) {
          keyboardRef.current.setInput('');
        }
      }, 50);
    }
  };

  // Remove player slot
  const removePlayer = (index) => {
    if (players.length > 1) {
      const newPlayers = players.filter((_, i) => i !== index);
      setPlayers(newPlayers);
      if (activePlayerIndex >= newPlayers.length) {
        setActivePlayerIndex(newPlayers.length - 1);
      }
    }
  };

  // Focus player input
  const focusPlayer = (index) => {
    setActivePlayerIndex(index);
    setShowKeyboard(true);
    setTimeout(() => {
      if (keyboardRef.current) {
        keyboardRef.current.setInput(players[index] || '');
      }
    }, 50);
  };

  // Can start game?
  const canStart = selectedGame && players.some(p => p.trim().length > 0);

  // Handle start
  const handleStart = () => {
    const validPlayers = players.filter(p => p.trim().length > 0);
    if (validPlayers.length > 0 && selectedGame) {
      onStartGame(selectedGame, validPlayers);
    }
  };

  // Reset keyboard when switching active player
  useEffect(() => {
    if (keyboardRef.current && showKeyboard) {
      keyboardRef.current.setInput(players[activePlayerIndex] || '');
    }
  }, [activePlayerIndex, showKeyboard, players]);

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
          
          {/* Remaining Credits/Time */}
          {remainingInfo && (
            <div className="flex items-center gap-3 bg-zinc-900 border border-zinc-700 rounded-sm px-4 py-2">
              {remainingInfo.type === 'credits' ? (
                <Coins className="w-5 h-5 text-amber-500" />
              ) : (
                <Clock className="w-5 h-5 text-amber-500" />
              )}
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
          {/* Step 1: Game Type Selection */}
          {step === 1 && (
            <div className="animate-slide-up" data-testid="step-game-type">
              <div className="flex items-center gap-3 mb-8">
                <Target className="w-8 h-8 text-amber-500" />
                <h2 className="text-3xl font-heading uppercase tracking-wider text-white">
                  Spielart wählen
                </h2>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
                {GAME_TYPES.map((game) => (
                  <button
                    key={game.id}
                    onClick={() => setSelectedGame(game.id)}
                    data-testid={`game-type-${game.id.toLowerCase()}`}
                    className={`
                      btn-kiosk flex flex-col items-center justify-center p-8 rounded-sm
                      ${selectedGame === game.id 
                        ? 'bg-amber-500 text-black border-amber-400 animate-pulse-glow' 
                        : 'bg-zinc-900 text-white border-zinc-700 hover:border-amber-500/50'
                      }
                    `}
                  >
                    <span className="text-5xl font-heading font-bold mb-2">{game.name}</span>
                    <span className={`text-sm uppercase tracking-wider ${selectedGame === game.id ? 'text-black/70' : 'text-zinc-500'}`}>
                      {game.description}
                    </span>
                  </button>
                ))}
              </div>

              {selectedGame && (
                <div className="flex justify-center">
                  <Button 
                    onClick={() => setStep(2)}
                    data-testid="next-to-players-btn"
                    className="btn-industrial h-20 px-16 text-2xl bg-amber-500 hover:bg-amber-400 text-black"
                  >
                    <span>WEITER</span>
                    <ChevronRight className="w-8 h-8 ml-2" />
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Step 2: Player Names */}
          {step === 2 && (
            <div className="animate-slide-up" data-testid="step-players">
              <button 
                onClick={() => setStep(1)}
                className="flex items-center gap-2 text-zinc-500 hover:text-white mb-6 transition-colors"
              >
                <ChevronRight className="w-5 h-5 rotate-180" />
                <span className="uppercase tracking-wider text-sm">Zurück</span>
              </button>

              <div className="flex items-center gap-3 mb-8">
                <Users className="w-8 h-8 text-amber-500" />
                <h2 className="text-3xl font-heading uppercase tracking-wider text-white">
                  Spielernamen eingeben
                </h2>
                <span className="text-xl text-zinc-500 ml-auto">
                  Spielart: <span className="text-amber-500 font-heading">{selectedGame}</span>
                </span>
              </div>

              {/* Player Inputs */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                {players.map((player, index) => (
                  <div 
                    key={index}
                    onClick={() => focusPlayer(index)}
                    className={`
                      relative flex items-center bg-zinc-900 border-2 rounded-sm p-4 cursor-pointer transition-all
                      ${activePlayerIndex === index && showKeyboard
                        ? 'border-amber-500 ring-2 ring-amber-500/30'
                        : 'border-zinc-700 hover:border-zinc-600'
                      }
                    `}
                  >
                    <div className="w-12 h-12 rounded-sm bg-zinc-800 flex items-center justify-center mr-4">
                      <span className="text-xl font-heading text-amber-500">{index + 1}</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs text-zinc-500 uppercase mb-1">Spieler {index + 1}</p>
                      <p className="text-xl font-mono text-white min-h-[28px]">
                        {player || <span className="text-zinc-600">Name eingeben...</span>}
                      </p>
                    </div>
                    {players.length > 1 && (
                      <button
                        onClick={(e) => { e.stopPropagation(); removePlayer(index); }}
                        className="p-2 text-zinc-600 hover:text-red-500 transition-colors"
                        data-testid={`remove-player-${index}`}
                      >
                        <Delete className="w-6 h-6" />
                      </button>
                    )}
                  </div>
                ))}

                {/* Add Player Button */}
                {players.length < maxPlayers && (
                  <button
                    onClick={addPlayer}
                    data-testid="add-player-btn"
                    className="flex items-center justify-center gap-3 bg-zinc-900/50 border-2 border-dashed border-zinc-700 rounded-sm p-4 text-zinc-500 hover:border-amber-500/50 hover:text-amber-500 transition-all min-h-[96px]"
                  >
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
                    display={{
                      '{bksp}': '⌫',
                      '{enter}': 'OK',
                      '{space}': 'SPACE'
                    }}
                    theme="hg-theme-default"
                  />
                </div>
              )}

              {/* Start Button */}
              <div className="flex justify-center">
                <Button
                  onClick={handleStart}
                  disabled={!canStart}
                  data-testid="start-game-btn"
                  className={`
                    btn-industrial h-24 px-20 text-3xl
                    ${canStart 
                      ? 'bg-emerald-500 hover:bg-emerald-400 text-black animate-pulse-glow' 
                      : 'bg-zinc-700 text-zinc-500 cursor-not-allowed'
                    }
                  `}
                >
                  <Play className="w-10 h-10 mr-3" />
                  <span>START</span>
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

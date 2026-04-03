import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import axios from 'axios';
import { Lock, User, KeyRound, Eye, EyeOff } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { useAuth } from '../../context/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminLogin() {
  const navigate = useNavigate();
  const { login, pinLogin } = useAuth();
  
  const [mode, setMode] = useState('password'); // 'password' or 'pin'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;

    const checkSetupStatus = async () => {
      try {
        const response = await axios.get(`${API}/setup/status`);
        if (active && response.data && !response.data.is_complete) {
          navigate('/setup', { replace: true });
        }
      } catch {
        // If setup status cannot be loaded we stay on login and let auth/backend errors surface normally.
      }
    };

    checkSetupStatus();
    return () => {
      active = false;
    };
  }, [navigate]);

  const handlePasswordLogin = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      toast.error('Bitte alle Felder ausfüllen');
      return;
    }

    setLoading(true);
    try {
      await login(username, password);
      toast.success('Anmeldung erfolgreich');
      navigate('/admin');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Anmeldung fehlgeschlagen');
    } finally {
      setLoading(false);
    }
  };

  const handlePinLogin = async (e) => {
    e.preventDefault();
    if (pin.length !== 4) {
      toast.error('PIN muss 4 Ziffern haben');
      return;
    }

    setLoading(true);
    try {
      await pinLogin(pin);
      toast.success('PIN akzeptiert');
      navigate('/admin');
    } catch (error) {
      toast.error('Ungültiger PIN');
      setPin('');
    } finally {
      setLoading(false);
    }
  };

  const handlePinInput = (digit) => {
    if (pin.length < 4) {
      const newPin = pin + digit;
      setPin(newPin);
      if (newPin.length === 4) {
        // Auto-submit when 4 digits entered
        setTimeout(() => {
          pinLogin(newPin)
            .then(() => {
              toast.success('PIN akzeptiert');
              navigate('/admin');
            })
            .catch(() => {
              toast.error('Ungültiger PIN');
              setPin('');
            });
        }, 200);
      }
    }
  };

  const handlePinBackspace = () => {
    setPin(pin.slice(0, -1));
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4" data-testid="admin-login-page">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 rounded-full bg-zinc-900 border-2 border-zinc-800 flex items-center justify-center mx-auto mb-4">
            <Lock className="w-10 h-10 text-amber-500" />
          </div>
          <h1 className="text-3xl font-heading font-bold uppercase tracking-wider text-white">
            Admin Panel
          </h1>
          <p className="text-zinc-500 mt-2">Anmeldung erforderlich</p>
        </div>

        {/* Mode Toggle */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setMode('password')}
            className={`flex-1 py-3 rounded-sm font-heading uppercase tracking-wider text-sm transition-all ${
              mode === 'password'
                ? 'bg-amber-500 text-black'
                : 'bg-zinc-900 text-zinc-400 border border-zinc-800 hover:text-white'
            }`}
          >
            <User className="w-4 h-4 inline mr-2" />
            Passwort
          </button>
          <button
            onClick={() => setMode('pin')}
            data-testid="pin-mode-btn"
            className={`flex-1 py-3 rounded-sm font-heading uppercase tracking-wider text-sm transition-all ${
              mode === 'pin'
                ? 'bg-amber-500 text-black'
                : 'bg-zinc-900 text-zinc-400 border border-zinc-800 hover:text-white'
            }`}
          >
            <KeyRound className="w-4 h-4 inline mr-2" />
            Quick PIN
          </button>
        </div>

        {/* Password Login Form */}
        {mode === 'password' && (
          <form onSubmit={handlePasswordLogin} className="space-y-4" data-testid="password-login-form">
            <div>
              <label className="block text-sm text-zinc-500 uppercase tracking-wider mb-2">
                Benutzername
              </label>
              <Input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                data-testid="username-input"
                className="input-industrial w-full"
              />
            </div>

            <div>
              <label className="block text-sm text-zinc-500 uppercase tracking-wider mb-2">
                Passwort
              </label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  data-testid="password-input"
                  className="input-industrial w-full pr-12"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              data-testid="login-submit-btn"
              className="w-full h-14 btn-industrial bg-amber-500 hover:bg-amber-400 text-black text-lg"
            >
              {loading ? 'Wird angemeldet...' : 'ANMELDEN'}
            </Button>
          </form>
        )}

        {/* PIN Login */}
        {mode === 'pin' && (
          <div className="space-y-6" data-testid="pin-login-form">
            {/* PIN Display */}
            <div className="flex justify-center gap-3 mb-8">
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  className={`w-14 h-14 rounded-sm border-2 flex items-center justify-center text-2xl font-mono ${
                    pin[i]
                      ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                      : 'border-zinc-700 bg-zinc-900 text-zinc-600'
                  }`}
                >
                  {pin[i] ? '•' : ''}
                </div>
              ))}
            </div>

            {/* Number Pad */}
            <div className="grid grid-cols-3 gap-3">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((digit) => (
                <button
                  key={digit}
                  onClick={() => handlePinInput(String(digit))}
                  data-testid={`pin-digit-${digit}`}
                  className="h-16 bg-zinc-900 border border-zinc-800 rounded-sm text-2xl font-mono text-white hover:bg-zinc-800 hover:border-amber-500/50 active:bg-amber-500 active:text-black transition-all"
                >
                  {digit}
                </button>
              ))}
              <div></div>
              <button
                onClick={() => handlePinInput('0')}
                data-testid="pin-digit-0"
                className="h-16 bg-zinc-900 border border-zinc-800 rounded-sm text-2xl font-mono text-white hover:bg-zinc-800 hover:border-amber-500/50 active:bg-amber-500 active:text-black transition-all"
              >
                0
              </button>
              <button
                onClick={handlePinBackspace}
                data-testid="pin-backspace"
                className="h-16 bg-zinc-900 border border-zinc-800 rounded-sm text-xl text-zinc-500 hover:text-red-500 hover:border-red-500/50 transition-all"
              >
                ⌫
              </button>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-zinc-600 text-sm">
            Default: admin / admin123 | PIN: 1234
          </p>
        </div>
      </div>
    </div>
  );
}

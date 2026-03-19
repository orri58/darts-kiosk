import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { KeyRound, LogIn, AlertCircle } from 'lucide-react';
import { Button } from '../../components/ui/button';

export default function OperatorLogin() {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useCentralAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Redirect if already authenticated (in useEffect to avoid setState during render)
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/operator', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  if (isAuthenticated) {
    return null;
  }

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/operator', { replace: true });
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.message;
      if (err?.response?.status === 502) {
        setError('Zentraler Server nicht erreichbar. Bitte prüfen Sie die Verbindung.');
      } else {
        setError(msg || 'Anmeldung fehlgeschlagen');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-6" data-testid="operator-login-page">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-4">
            <KeyRound className="w-8 h-8 text-indigo-400" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Betreiber-Portal</h1>
          <p className="text-sm text-zinc-500 mt-1">Melden Sie sich mit Ihrem Betreiber-Konto an</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm" data-testid="login-error">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-sm text-zinc-400 mb-1.5">Benutzername</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-indigo-500 transition-colors"
              placeholder="benutzername"
              required
              autoFocus
              data-testid="operator-login-username"
            />
          </div>
          <div>
            <label className="block text-sm text-zinc-400 mb-1.5">Passwort</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-indigo-500 transition-colors"
              placeholder="••••••••"
              required
              data-testid="operator-login-password"
            />
          </div>

          <Button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-2.5 rounded-lg transition-colors"
            data-testid="operator-login-submit"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <><LogIn className="w-4 h-4 mr-2" /> Anmelden</>
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}

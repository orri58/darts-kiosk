import { useState, useEffect } from 'react';
import { Shield, Loader2, CheckCircle, AlertTriangle, Copy, Monitor } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Registration Overlay for Kiosk (v3.5.1)
 *
 * Shows a blocking overlay when the device is not registered.
 * Provides a token input field for one-time registration.
 * This is SEPARATE from the license overlay — own clear state.
 *
 * Props:
 *   kioskState: current kiosk state ('locked', 'setup', etc.)
 */
export default function RegistrationOverlay({ kioskState }) {
  const [regStatus, setRegStatus] = useState(null);
  const [token, setToken] = useState('');
  const [deviceName, setDeviceName] = useState('');
  const [serverUrl, setServerUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const res = await axios.get(`${API}/licensing/registration-status`, { timeout: 5000 });
        if (mounted) setRegStatus(res.data);
      } catch {
        // Fail silently on network errors
      }
    };
    check();
    const interval = setInterval(check, 30 * 1000); // recheck every 30s
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  if (!regStatus) return null;
  if (regStatus.status === 'registered') return null;

  // Don't show during active games
  const isInGame = kioskState === 'in_game' || kioskState === 'observer_active' || kioskState === 'finished';
  if (isInGame) return null;

  const handleRegister = async () => {
    if (!token.trim()) {
      setError('Bitte Registrierungscode eingeben');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess(null);

    try {
      const body = { token: token.trim() };
      if (deviceName.trim()) body.device_name = deviceName.trim();
      if (serverUrl.trim()) body.server_url = serverUrl.trim();

      const res = await axios.post(`${API}/licensing/register-device`, body);
      if (res.data.success) {
        setSuccess(res.data);
        // Refresh status after short delay
        setTimeout(() => window.location.reload(), 3000);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'Registrierung fehlgeschlagen';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !loading) handleRegister();
  };

  // Success state
  if (success) {
    return (
      <div className="fixed inset-0 z-[1001] bg-black/95 flex items-center justify-center" data-testid="registration-success-overlay">
        <div className="text-center max-w-lg px-8">
          <div className="w-20 h-20 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-10 h-10 text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">
            Geraet erfolgreich registriert
          </h2>
          <div className="space-y-2 text-sm text-zinc-300">
            {success.device_name && <p>Geraet: <span className="text-white font-medium">{success.device_name}</span></p>}
            {success.customer_name && <p>Kunde: <span className="text-white font-medium">{success.customer_name}</span></p>}
            {success.license_status && <p>Lizenz: <span className="text-emerald-400 font-medium">{success.license_status}</span></p>}
          </div>
          <p className="text-xs text-zinc-500 mt-6">System wird in wenigen Sekunden neu geladen...</p>
        </div>
      </div>
    );
  }

  // Registration form
  return (
    <div className="fixed inset-0 z-[1001] bg-black/95 flex items-center justify-center" data-testid="registration-overlay">
      <div className="text-center max-w-lg px-8 w-full">
        <div className="w-20 h-20 rounded-full bg-amber-500/20 flex items-center justify-center mx-auto mb-6">
          <Shield className="w-10 h-10 text-amber-500" />
        </div>

        <h2 className="text-2xl font-bold text-white mb-2" data-testid="registration-title">
          Geraet nicht registriert
        </h2>
        <p className="text-zinc-400 mb-6 text-sm">
          Dieses Geraet muss zuerst beim zentralen Server registriert werden.
          Bitte geben Sie den Registrierungscode ein, den Sie vom Administrator erhalten haben.
        </p>

        {/* Install ID display */}
        {regStatus.install_id && (
          <div className="mb-5 p-3 bg-zinc-800/50 rounded flex items-center justify-between" data-testid="registration-install-id">
            <div className="flex items-center gap-2">
              <Monitor className="w-4 h-4 text-zinc-500" />
              <span className="text-xs text-zinc-500">Install-ID:</span>
              <span className="text-xs text-zinc-300 font-mono">{regStatus.install_id}</span>
            </div>
            <button
              onClick={() => navigator.clipboard?.writeText(regStatus.install_id)}
              className="text-zinc-500 hover:text-white transition-colors"
              title="Kopieren"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Server URL (only if not configured) */}
        <div className="space-y-3 mb-4">
          <input
            type="url"
            placeholder="Server-URL (z.B. https://central.example.com)"
            value={serverUrl}
            onChange={e => setServerUrl(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-white placeholder-zinc-500 focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none"
            data-testid="registration-server-url"
          />
          <input
            type="text"
            placeholder="Registrierungscode (drt_...)"
            value={token}
            onChange={e => setToken(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-white placeholder-zinc-500 focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none font-mono"
            data-testid="registration-token-input"
            autoFocus
          />
          <input
            type="text"
            placeholder="Geraetename (optional)"
            value={deviceName}
            onChange={e => setDeviceName(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-white placeholder-zinc-500 focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 outline-none"
            data-testid="registration-device-name"
          />
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2" data-testid="registration-error">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span className="text-sm text-red-400">{error}</span>
          </div>
        )}

        <button
          onClick={handleRegister}
          disabled={loading || !token.trim()}
          className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold rounded-lg px-6 py-3 transition-colors flex items-center justify-center gap-2"
          data-testid="registration-submit-btn"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Registrierung laeuft...
            </>
          ) : (
            <>
              <Shield className="w-4 h-4" />
              Geraet registrieren
            </>
          )}
        </button>

        <p className="text-xs text-zinc-600 mt-4">
          Die Registrierung erfordert eine aktive Internetverbindung zum zentralen Server.
        </p>
      </div>
    </div>
  );
}

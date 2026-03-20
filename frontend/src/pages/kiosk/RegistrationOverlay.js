import { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Monitor, KeyRound, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Map backend errors to human-readable German messages
const ERROR_MESSAGES = {
  'Token not found or not valid': 'Dieser Code ist ungültig. Bitte prüfen Sie die Eingabe.',
  'Token expired': 'Dieser Code ist abgelaufen. Bitte fordern Sie einen neuen an.',
  'Token already used': 'Dieser Code wurde bereits verwendet.',
  'Token has been revoked': 'Dieser Code wurde widerrufen.',
  'Install ID already registered': 'Dieses Gerät ist bereits registriert.',
  'Binding conflict': 'Es gibt einen Konflikt mit der Gerätebindung. Bitte kontaktieren Sie den Administrator.',
};

function friendlyError(err) {
  const detail = err?.response?.data?.detail || err?.response?.data?.message || '';
  // Check known error messages
  for (const [key, msg] of Object.entries(ERROR_MESSAGES)) {
    if (detail.toLowerCase().includes(key.toLowerCase())) return msg;
  }
  // Check HTTP status codes
  const status = err?.response?.status;
  if (status === 502) return 'Der zentrale Server ist nicht erreichbar. Bitte prüfen Sie die Netzwerkverbindung.';
  if (status === 504) return 'Zeitüberschreitung beim Verbindungsaufbau zum zentralen Server.';
  if (status === 403) return 'Zugriff verweigert. Der Code hat keine gültige Berechtigung.';
  if (status === 404) return 'Dieser Code wurde nicht gefunden.';
  if (detail) return detail;
  return 'Registrierung fehlgeschlagen. Bitte versuchen Sie es erneut.';
}

export default function RegistrationOverlay() {
  const [regStatus, setRegStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  // Form
  const [token, setToken] = useState('');
  const [deviceName, setDeviceName] = useState('');

  // Server URL state
  const [serverUrl, setServerUrl] = useState('');
  const [serverConfigured, setServerConfigured] = useState(false);

  // Load registration status and central server URL
  useEffect(() => {
    const load = async () => {
      try {
        const [statusRes, urlRes] = await Promise.all([
          axios.get(`${API}/licensing/registration-status`),
          axios.get(`${API}/licensing/central-server-url`),
        ]);
        setRegStatus(statusRes.data);
        if (urlRes.data.configured) {
          setServerUrl(urlRes.data.url);
          setServerConfigured(true);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // If already registered, auto-dismiss
  useEffect(() => {
    if (regStatus?.status === 'registered') {
      // Already registered — overlay will return null
    }
  }, [regStatus]);

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!token.trim()) return;
    setRegistering(true);
    setError('');

    try {
      const body = { token: token.trim() };
      if (deviceName.trim()) body.device_name = deviceName.trim();
      if (serverUrl.trim()) body.server_url = serverUrl.trim();

      const res = await axios.post(`${API}/licensing/register-device`, body);
      setSuccess(true);
      toast.success('Gerät erfolgreich registriert');
      // Auto-redirect: wait 3s then reload to enter normal kiosk flow
      setTimeout(() => {
        window.location.reload();
      }, 3000);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setRegistering(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-[100] bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-10 h-10 text-amber-500 animate-spin" />
      </div>
    );
  }

  if (regStatus?.status === 'registered') return null;

  return (
    <div className="fixed inset-0 z-[100] bg-zinc-950 flex items-center justify-center p-6" data-testid="registration-overlay">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mx-auto mb-4">
            <Monitor className="w-8 h-8 text-amber-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Gerät registrieren</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Geben Sie den Registrierungscode ein, den Sie von Ihrem Administrator erhalten haben.
          </p>
        </div>

        {/* Install ID */}
        {regStatus?.install_id && (
          <div className="mb-6 p-3 bg-zinc-900 rounded-lg border border-zinc-800 text-center">
            <p className="text-xs text-zinc-500 mb-1">Geräte-ID</p>
            <p className="text-sm font-mono text-zinc-300 select-all" data-testid="reg-install-id">{regStatus.install_id}</p>
          </div>
        )}

        {/* Success State */}
        {success ? (
          <div className="p-6 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-center" data-testid="reg-success">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-lg text-emerald-400 font-semibold">Erfolgreich registriert!</p>
            <p className="text-sm text-zinc-400 mt-1">Das Gerät wird jetzt aktiviert...</p>
          </div>
        ) : (
          <form onSubmit={handleRegister} className="space-y-4">
            {/* Error */}
            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-start gap-2" data-testid="reg-error">
                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Server URL — only show if NOT pre-configured */}
            {!serverConfigured && (
              <div>
                <label className="block text-sm text-zinc-300 mb-1.5">Server-Adresse</label>
                <input
                  type="url"
                  value={serverUrl}
                  onChange={e => setServerUrl(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-amber-500 transition-colors"
                  placeholder="https://api.dartcontrol.io"
                  data-testid="reg-server-url"
                />
              </div>
            )}

            {/* Registration Code */}
            <div>
              <label className="block text-sm text-zinc-300 mb-1.5">Registrierungscode</label>
              <div className="relative">
                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <input
                  type="text"
                  value={token}
                  onChange={e => setToken(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-10 pr-4 py-3 text-white text-sm font-mono focus:outline-none focus:border-amber-500 transition-colors tracking-wider"
                  placeholder="drt_..."
                  required
                  autoFocus
                  data-testid="reg-token-input"
                />
              </div>
            </div>

            {/* Device Name */}
            <div>
              <label className="block text-sm text-zinc-300 mb-1.5">Gerätename (optional)</label>
              <input
                type="text"
                value={deviceName}
                onChange={e => setDeviceName(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-amber-500 transition-colors"
                placeholder="z.B. Dartboard 3"
                data-testid="reg-device-name"
              />
            </div>

            <Button
              type="submit"
              disabled={registering || !token.trim()}
              className="w-full bg-amber-500 hover:bg-amber-400 text-black py-3 rounded-lg font-medium transition-colors"
              data-testid="reg-submit-btn"
            >
              {registering ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                'Gerät registrieren'
              )}
            </Button>

            {serverConfigured && (
              <p className="text-xs text-zinc-600 text-center">
                Verbunden mit: {serverUrl}
              </p>
            )}
          </form>
        )}
      </div>
    </div>
  );
}

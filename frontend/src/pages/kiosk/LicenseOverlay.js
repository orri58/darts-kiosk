import { useState, useEffect } from 'react';
import { AlertTriangle, Lock, Clock } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * License Overlay for Kiosk (v3.4.1)
 *
 * Shows a blocking overlay when the license is expired or blocked.
 * Shows a subtle warning bar during grace period.
 * Does NOT interrupt running games — only shown on locked/setup screens.
 *
 * Props:
 *   kioskState: current kiosk state ('locked', 'setup', 'in_game', etc.)
 */
export default function LicenseOverlay({ kioskState }) {
  const [licStatus, setLicStatus] = useState(null);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const res = await axios.get(`${API}/kiosk/license-status`, { timeout: 5000 });
        if (mounted) setLicStatus(res.data);
      } catch {
        // Fail silently — don't block on network errors
      }
    };
    check();
    const interval = setInterval(check, 5 * 60 * 1000); // recheck every 5 min
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  if (!licStatus) return null;

  const status = licStatus.status;

  // No overlay needed for active/test/no_license
  if (status === 'active' || status === 'test' || status === 'no_license') return null;

  // Don't show blocking overlay during active games
  const isInGame = kioskState === 'in_game' || kioskState === 'observer_active' || kioskState === 'finished';

  // Grace period: subtle yellow bar (non-blocking)
  if (status === 'grace') {
    if (isInGame) return null; // don't disturb running games
    return (
      <div
        className="fixed top-0 left-0 right-0 z-[999] bg-amber-500/90 text-black px-4 py-2 flex items-center justify-center gap-2"
        data-testid="license-grace-bar"
      >
        <Clock className="w-4 h-4" />
        <span className="text-sm font-medium">
          Lizenz abgelaufen — Grace Period aktiv
          {licStatus.grace_days_remaining != null && (
            <span className="ml-1">({licStatus.grace_days_remaining} Tage verbleibend)</span>
          )}
        </span>
      </div>
    );
  }

  // Expired or blocked: full blocking overlay
  if (status === 'expired' || status === 'blocked') {
    if (isInGame) return null; // NEVER interrupt running games
    return (
      <div
        className="fixed inset-0 z-[1000] bg-black/95 flex items-center justify-center"
        data-testid="license-blocked-overlay"
      >
        <div className="text-center max-w-md px-8">
          <div className="w-20 h-20 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-6">
            {status === 'blocked' ? (
              <Lock className="w-10 h-10 text-red-500" />
            ) : (
              <AlertTriangle className="w-10 h-10 text-red-500" />
            )}
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">
            {status === 'blocked' ? 'Lizenz gesperrt' : 'Lizenz abgelaufen'}
          </h2>
          <p className="text-zinc-400 mb-6">
            {status === 'blocked'
              ? 'Dieses Geraet wurde vom Administrator gesperrt. Neue Spiele koennen nicht gestartet werden.'
              : 'Die Lizenz fuer dieses Geraet ist abgelaufen. Bitte kontaktieren Sie den Administrator.'}
          </p>
          {licStatus.customer_name && (
            <p className="text-xs text-zinc-600">Kunde: {licStatus.customer_name}</p>
          )}
          <p className="text-xs text-zinc-600 mt-1">
            Status: {status} | Geprueft: {licStatus.checked_at ? new Date(licStatus.checked_at).toLocaleString('de-DE') : '-'}
          </p>
        </div>
      </div>
    );
  }

  return null;
}

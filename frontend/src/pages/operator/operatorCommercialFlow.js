export function buildLicenseDetailPath(surfacePrefix, licenseId, { intent = '', returnTo = '', returnLabel = '' } = {}) {
  const safeSurface = surfacePrefix || '/operator';
  const params = new URLSearchParams();
  if (intent) params.set('intent', intent);
  if (returnTo) params.set('returnTo', returnTo);
  if (returnLabel) params.set('returnLabel', returnLabel);
  const query = params.toString();
  return `${safeSurface}/licenses/${licenseId}${query ? `?${query}` : ''}`;
}

export function resolveLicenseBackTarget({ search = '', state = null, fallbackPath = '/operator/licenses', fallbackLabel = 'Portfolio' } = {}) {
  const params = new URLSearchParams(search || '');
  const stateReturnTo = state?.returnTo || state?.fromListPath || '';
  const stateReturnLabel = state?.returnLabel || state?.fromListLabel || '';
  const returnTo = params.get('returnTo') || stateReturnTo || fallbackPath;
  const returnLabel = params.get('returnLabel') || stateReturnLabel || fallbackLabel;
  return { returnTo, returnLabel };
}

export function getTokenStatePresentation(summary, { compact = false } = {}) {
  const state = summary?.state || 'missing';
  const expiresIn = summary?.active_expires_in_days;
  const counts = summary?.counts || {};

  const map = {
    active: {
      label: 'Token bereit',
      shortLabel: 'Bereit',
      tone: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
      detail: expiresIn != null ? `${expiresIn}T Restlaufzeit` : 'Sofort einsatzbereit',
      semantic: 'ready_now',
    },
    consumed: {
      label: 'Aktivierung genutzt',
      shortLabel: 'Genutzt',
      tone: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
      detail: 'Gerät bereits registriert',
      semantic: 'bound_device',
    },
    expired: {
      label: 'Token abgelaufen',
      shortLabel: 'Abgelaufen',
      tone: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
      detail: 'Neu ausstellen empfohlen',
      semantic: 'stale_token',
    },
    revoked: {
      label: 'Token widerrufen',
      shortLabel: 'Widerrufen',
      tone: 'border-red-500/20 bg-red-500/10 text-red-300',
      detail: 'Nur mit neuem Token aktivierbar',
      semantic: 'stale_token',
    },
    missing: {
      label: 'Kein Token',
      shortLabel: 'Kein Token',
      tone: 'border-zinc-700 bg-zinc-800/80 text-zinc-300',
      detail: counts.total > 0 ? `${counts.total} historische Token` : 'Noch nicht erstellt',
      semantic: 'missing_token',
    },
  };

  const selected = map[state] || map.missing;
  return {
    ...selected,
    detail: compact ? '' : selected.detail,
  };
}

const TRUTHY = new Set(['1', 'true', 'yes', 'on']);

function envFlag(name, fallback = false) {
  const raw = process.env[name];
  if (raw == null || raw === '') return fallback;
  return TRUTHY.has(String(raw).trim().toLowerCase());
}

export const PORTAL_SURFACE_ENABLED = envFlag('REACT_APP_ENABLE_PORTAL_SURFACE', false);
export const CALL_STAFF_ENABLED = envFlag('REACT_APP_ENABLE_CALL_STAFF', false);
export const LOCAL_CORE_PRICING_MODES = ['per_game', 'per_time'];

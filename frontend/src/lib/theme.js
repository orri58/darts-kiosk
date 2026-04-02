const FALLBACK_PALETTE = {
  bg: '#09090b',
  surface: '#18181b',
  primary: '#f59e0b',
  secondary: '#ffffff',
  accent: '#ef4444',
  text: '#e4e4e7',
};

function normalizeHex(hex, fallback = '#000000') {
  if (typeof hex !== 'string') return fallback;
  const trimmed = hex.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) return trimmed.toLowerCase();
  if (/^#[0-9a-fA-F]{3}$/.test(trimmed)) {
    return `#${trimmed[1]}${trimmed[1]}${trimmed[2]}${trimmed[2]}${trimmed[3]}${trimmed[3]}`.toLowerCase();
  }
  return fallback;
}

function hexToRgb(hex) {
  const value = normalizeHex(hex);
  return {
    r: parseInt(value.slice(1, 3), 16),
    g: parseInt(value.slice(3, 5), 16),
    b: parseInt(value.slice(5, 7), 16),
  };
}

function rgbToHex({ r, g, b }) {
  const clamp = (value) => Math.max(0, Math.min(255, Math.round(value)));
  return `#${[clamp(r), clamp(g), clamp(b)].map((part) => part.toString(16).padStart(2, '0')).join('')}`;
}

function rgbToHsl({ r, g, b }) {
  const rn = r / 255;
  const gn = g / 255;
  const bn = b / 255;
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const delta = max - min;

  let h = 0;
  if (delta !== 0) {
    if (max === rn) h = ((gn - bn) / delta) % 6;
    else if (max === gn) h = (bn - rn) / delta + 2;
    else h = (rn - gn) / delta + 4;
    h = Math.round(h * 60);
    if (h < 0) h += 360;
  }

  const l = (max + min) / 2;
  const s = delta === 0 ? 0 : delta / (1 - Math.abs(2 * l - 1));

  return {
    h,
    s: +(s * 100).toFixed(1),
    l: +(l * 100).toFixed(1),
  };
}

function hexToHslString(hex) {
  const { h, s, l } = rgbToHsl(hexToRgb(hex));
  return `${h} ${s}% ${l}%`;
}

function mixHex(baseHex, mixHexValue, weight = 0.5) {
  const base = hexToRgb(baseHex);
  const mix = hexToRgb(mixHexValue);
  const safeWeight = Math.max(0, Math.min(1, weight));
  return rgbToHex({
    r: base.r + (mix.r - base.r) * safeWeight,
    g: base.g + (mix.g - base.g) * safeWeight,
    b: base.b + (mix.b - base.b) * safeWeight,
  });
}

function relativeLuminance(hex) {
  const { r, g, b } = hexToRgb(hex);
  const toLinear = (channel) => {
    const value = channel / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  const rl = toLinear(r);
  const gl = toLinear(g);
  const bl = toLinear(b);
  return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
}

function contrastRatio(a, b) {
  const l1 = relativeLuminance(a);
  const l2 = relativeLuminance(b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function bestForeground(backgroundHex, candidates) {
  return [...candidates]
    .filter(Boolean)
    .map((hex) => normalizeHex(hex))
    .sort((a, b) => contrastRatio(b, backgroundHex) - contrastRatio(a, backgroundHex))[0] || '#ffffff';
}

function setHexVar(root, key, hex) {
  const normalized = normalizeHex(hex);
  const { r, g, b } = hexToRgb(normalized);
  root.style.setProperty(key, normalized);
  root.style.setProperty(`${key}-rgb`, `${r} ${g} ${b}`);
}

export function resolvePaletteColors(palette) {
  const colors = palette?.colors || palette || {};
  return {
    bg: normalizeHex(colors.bg, FALLBACK_PALETTE.bg),
    surface: normalizeHex(colors.surface, FALLBACK_PALETTE.surface),
    primary: normalizeHex(colors.primary, FALLBACK_PALETTE.primary),
    secondary: normalizeHex(colors.secondary, FALLBACK_PALETTE.secondary),
    accent: normalizeHex(colors.accent, FALLBACK_PALETTE.accent),
    text: normalizeHex(colors.text, FALLBACK_PALETTE.text),
  };
}

export function buildThemeTokens(palette) {
  const colors = resolvePaletteColors(palette);
  const surfaceHighlight = mixHex(colors.surface, colors.text, 0.08);
  const mutedSurface = mixHex(colors.surface, colors.text, 0.05);
  const textSecondary = mixHex(colors.text, colors.bg, 0.28);
  const textMuted = mixHex(colors.text, colors.bg, 0.58);
  const border = mixHex(colors.surface, colors.text, 0.14);
  const borderStrong = mixHex(colors.surface, colors.text, 0.24);
  const primarySoft = mixHex(colors.primary, colors.bg, 0.78);
  const accentSoft = mixHex(colors.accent, colors.bg, 0.82);
  const success = '#10b981';
  const warning = mixHex(colors.primary, '#facc15', 0.35);
  const info = mixHex(colors.primary, '#3b82f6', 0.55);
  const error = colors.accent;
  const locked = mixHex(colors.text, colors.bg, 0.7);
  const primaryForeground = bestForeground(colors.primary, [colors.bg, colors.text, '#000000', '#ffffff']);
  const accentForeground = bestForeground(colors.accent, [colors.bg, colors.text, '#000000', '#ffffff']);

  return {
    ...colors,
    surfaceHighlight,
    mutedSurface,
    textSecondary,
    textMuted,
    border,
    borderStrong,
    primarySoft,
    accentSoft,
    success,
    warning,
    info,
    error,
    locked,
    primaryForeground,
    accentForeground,
  };
}

export function applyPaletteToDocument(palette, { themeColor } = {}) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  const tokens = buildThemeTokens(palette);

  Object.entries({
    '--color-bg': tokens.bg,
    '--color-surface': tokens.surface,
    '--color-surface-highlight': tokens.surfaceHighlight,
    '--color-primary': tokens.primary,
    '--color-secondary': tokens.secondary,
    '--color-accent': tokens.accent,
    '--color-text': tokens.text,
    '--color-text-secondary': tokens.textSecondary,
    '--color-text-muted': tokens.textMuted,
    '--color-border': tokens.border,
    '--color-border-active': tokens.primary,
    '--color-success': tokens.success,
    '--color-warning': tokens.warning,
    '--color-error': tokens.error,
    '--color-info': tokens.info,
    '--color-locked': tokens.locked,
  }).forEach(([key, value]) => setHexVar(root, key, value));

  root.style.setProperty('--background', hexToHslString(tokens.bg));
  root.style.setProperty('--foreground', hexToHslString(tokens.text));
  root.style.setProperty('--card', hexToHslString(tokens.surface));
  root.style.setProperty('--card-foreground', hexToHslString(tokens.text));
  root.style.setProperty('--popover', hexToHslString(tokens.surface));
  root.style.setProperty('--popover-foreground', hexToHslString(tokens.text));
  root.style.setProperty('--primary', hexToHslString(tokens.primary));
  root.style.setProperty('--primary-foreground', hexToHslString(tokens.primaryForeground));
  root.style.setProperty('--secondary', hexToHslString(tokens.surfaceHighlight));
  root.style.setProperty('--secondary-foreground', hexToHslString(tokens.text));
  root.style.setProperty('--muted', hexToHslString(tokens.mutedSurface));
  root.style.setProperty('--muted-foreground', hexToHslString(tokens.textSecondary));
  root.style.setProperty('--accent', hexToHslString(tokens.surfaceHighlight));
  root.style.setProperty('--accent-foreground', hexToHslString(tokens.text));
  root.style.setProperty('--destructive', hexToHslString(tokens.error));
  root.style.setProperty('--destructive-foreground', hexToHslString(tokens.accentForeground));
  root.style.setProperty('--border', hexToHslString(tokens.border));
  root.style.setProperty('--input', hexToHslString(tokens.border));
  root.style.setProperty('--ring', hexToHslString(tokens.primary));
  root.style.setProperty('--chart-1', hexToHslString(tokens.primary));
  root.style.setProperty('--chart-2', hexToHslString(tokens.success));
  root.style.setProperty('--chart-3', hexToHslString(tokens.warning));
  root.style.setProperty('--chart-4', hexToHslString(tokens.info));
  root.style.setProperty('--chart-5', hexToHslString(tokens.accent));

  const metaTheme = document.querySelector('meta[name="theme-color"]');
  if (metaTheme) metaTheme.content = themeColor || tokens.bg;

  return tokens;
}

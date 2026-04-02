import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { applyPaletteToDocument, buildThemeTokens } from '../lib/theme';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [branding, setBranding] = useState({
    cafe_name: 'Dart Zone',
    subtitle: 'Darts & More',
    logo_url: null,
    palette_id: 'industrial',
    font_preset: 'industrial',
    background_style: 'solid'
  });
  
  const [pricing, setPricing] = useState({
    mode: 'per_player',
    per_game: { price_per_credit: 2.0, default_credits: 3, currency: 'EUR' },
    per_time: { price_per_30_min: 5.0, price_per_60_min: 8.0, currency: 'EUR' },
    per_player: { price_per_player: 1.5, currency: 'EUR' },
    max_players: 4,
    idle_timeout_minutes: 5,
    allowed_game_types: ['301', '501', 'Cricket', 'Training']
  });
  
  const [palettes, setPalettes] = useState([]);
  const [kioskTexts, setKioskTexts] = useState({
    locked_title: 'GESPERRT',
    locked_subtitle: 'Bitte an der Theke freischalten lassen',
    pricing_hint: '',
    game_running: 'SPIEL LÄUFT',
    game_finished: 'SPIEL BEENDET',
    call_staff: 'Personal rufen',
    credits_label: 'Credits verfügbar',
    time_label: 'Zeit übrig',
    staff_hint: '',
    upsell_message: 'Credits an der Theke nachladen',
  });
  const [pwaConfig, setPwaConfig] = useState({
    app_name: 'Darts Kiosk',
    short_name: 'Darts',
    theme_color: '#09090b',
    background_color: '#09090b',
  });
  const [lockscreenQr, setLockscreenQr] = useState({
    enabled: false,
    label: 'Leaderboard & Stats',
    path: '/public/leaderboard',
  });
  const [loading, setLoading] = useState(true);

  const fetchSettings = useCallback(async () => {
    try {
      const [brandingRes, pricingRes, palettesRes, textsRes, pwaRes, qrRes] = await Promise.all([
        axios.get(`${API}/settings/branding`),
        axios.get(`${API}/settings/pricing`),
        axios.get(`${API}/settings/palettes`),
        axios.get(`${API}/settings/kiosk-texts`).catch(() => ({ data: null })),
        axios.get(`${API}/settings/pwa`).catch(() => ({ data: null })),
        axios.get(`${API}/settings/lockscreen-qr`).catch(() => ({ data: null })),
      ]);

      const nextBranding = brandingRes.data || {};
      const nextPalettes = palettesRes.data || [];
      setBranding(nextBranding);
      setPricing(pricingRes.data);
      setPalettes(nextPalettes);
      if (textsRes.data) setKioskTexts(prev => ({ ...prev, ...textsRes.data }));
      if (pwaRes.data) setPwaConfig(prev => ({ ...prev, ...pwaRes.data }));
      if (qrRes.data) setLockscreenQr(prev => ({ ...prev, ...qrRes.data }));

      // Set document title from branding (except on /kiosk pages which use fixed title for Win32)
      if (!window.location.pathname.startsWith('/kiosk')) {
        document.title = nextBranding.cafe_name || 'Darts Kiosk';
      }

      const activePalette = nextPalettes.find((palette) => palette.id === nextBranding.palette_id) || nextPalettes[0];
      if (activePalette) {
        applyPaletteToDocument(activePalette, { themeColor: pwaRes.data?.theme_color });
      }
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  useEffect(() => {
    const path = window.location.pathname;
    if (path.startsWith('/admin/settings')) {
      return undefined;
    }

    const isLiveSurface = path.startsWith('/kiosk') || path.startsWith('/overlay') || path.startsWith('/public');
    const refreshInterval = isLiveSurface ? 10000 : 45000;
    const refresh = () => {
      if (document.visibilityState === 'visible') {
        fetchSettings();
      }
    };

    const interval = window.setInterval(refresh, refreshInterval);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [fetchSettings]);

  const activePalette = useMemo(
    () => palettes.find((palette) => palette.id === branding.palette_id) || palettes[0] || null,
    [palettes, branding.palette_id]
  );

  const theme = useMemo(() => buildThemeTokens(activePalette), [activePalette]);

  // Apply palette CSS variables when palette or theme color changes
  useEffect(() => {
    if (activePalette) {
      applyPaletteToDocument(activePalette, { themeColor: pwaConfig?.theme_color });
    }
  }, [activePalette, pwaConfig?.theme_color]);

  const updateBranding = async (newBranding) => {
    const response = await axios.put(`${API}/settings/branding`, { value: newBranding });
    setBranding(response.data);
    return response.data;
  };

  const updatePricing = async (newPricing) => {
    const response = await axios.put(`${API}/settings/pricing`, { value: newPricing });
    setPricing(response.data);
    return response.data;
  };

  const updatePalettes = async (newPalettes) => {
    const response = await axios.put(`${API}/settings/palettes`, { value: newPalettes });
    setPalettes(response.data);
    return response.data;
  };

  const getCurrentPalette = () => {
    return activePalette;
  };

  return (
    <SettingsContext.Provider value={{
      branding,
      pricing,
      palettes,
      kioskTexts,
      pwaConfig,
      lockscreenQr,
      loading,
      theme,
      updateBranding,
      updatePricing,
      updatePalettes,
      getCurrentPalette,
      refreshSettings: fetchSettings
    }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
}

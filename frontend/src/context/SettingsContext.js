import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import { applyPaletteToDocument, buildThemeTokens } from '../lib/theme';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const location = useLocation();
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
  const [kioskTheme, setKioskTheme] = useState({
    palette_id: 'industrial',
    font_preset: 'industrial',
    background_style: 'solid',
  });
  const [adminTheme, setAdminTheme] = useState({
    palette_id: 'slate',
  });
  const [kioskLayout, setKioskLayout] = useState({
    preset: 'balanced',
    header: { show_logo: true, show_title: true, show_subtitle: true, align: 'left', logo_size: 'md' },
    locked_screen: {
      pairing_position: 'bottom',
      show_community_widgets: false,
      panel_emphasis: 'balanced',
      content_align: 'left',
      logo_position: 'header',
      hero_logo_size: 'xl',
    },
  });
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
    upsell_pricing: '',
    locked_cards: {
      credits: { enabled: true, label: 'Credits', value: '', hint: 'Preis pro Credit' },
      matchstart: { enabled: true, label: 'Matchstart', value: '', hint: 'Abbuchung erst beim echten Match.' },
      unlock: { enabled: true, label: 'Freischaltung', value: '', hint: 'Typischer Startwert am Tresen.' },
    },
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
      const { data: bundle } = await axios.get(`${API}/settings/customization-bundle`);

      const nextBranding = bundle?.branding || {};
      const nextPricing = bundle?.pricing || {};
      const nextPalettes = Array.isArray(bundle?.palettes) ? bundle.palettes : [];
      const nextKioskTheme = bundle?.kioskTheme || {};
      const nextAdminTheme = bundle?.adminTheme || {};
      const nextKioskLayout = bundle?.kioskLayout || {};
      const nextKioskTexts = bundle?.kioskTexts || {};
      const nextPwaConfig = bundle?.pwaConfig || {};
      const nextLockscreenQr = bundle?.lockscreenQr || {};

      setBranding(nextBranding);
      setPricing(nextPricing);
      setPalettes(nextPalettes);
      setKioskTheme(nextKioskTheme);
      setAdminTheme(nextAdminTheme);
      setKioskLayout(nextKioskLayout);
      setKioskTexts(nextKioskTexts);
      setPwaConfig(nextPwaConfig);
      setLockscreenQr(nextLockscreenQr);

      if (!location.pathname.startsWith('/kiosk')) {
        document.title = nextBranding.cafe_name || 'Darts Kiosk';
      }

      const path = location.pathname;
      const themePaletteId = path.startsWith('/admin')
        ? (nextAdminTheme?.palette_id || 'slate')
        : (nextKioskTheme?.palette_id || nextBranding.palette_id);
      const activePalette = nextPalettes.find((palette) => palette.id === themePaletteId) || nextPalettes[0];
      if (activePalette) {
        applyPaletteToDocument(activePalette, { themeColor: nextPwaConfig?.theme_color });
      }
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setLoading(false);
    }
  }, [location.pathname]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  useEffect(() => {
    const path = location.pathname;
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
  }, [fetchSettings, location.pathname]);

  const activePalette = useMemo(() => {
    const path = location.pathname;
    const themePaletteId = path.startsWith('/admin')
      ? (adminTheme?.palette_id || 'slate')
      : (kioskTheme?.palette_id || branding.palette_id);
    return palettes.find((palette) => palette.id === themePaletteId) || palettes[0] || null;
  }, [palettes, branding.palette_id, kioskTheme?.palette_id, adminTheme?.palette_id, location.pathname]);

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

  const updateKioskTheme = async (newTheme) => {
    const response = await axios.put(`${API}/settings/kiosk-theme`, { value: newTheme });
    setKioskTheme(response.data);
    return response.data;
  };

  const updateAdminTheme = async (newTheme) => {
    const response = await axios.put(`${API}/settings/admin-theme`, { value: newTheme });
    setAdminTheme(response.data);
    return response.data;
  };

  const updateKioskLayout = async (newLayout) => {
    const response = await axios.put(`${API}/settings/kiosk-layout`, { value: newLayout });
    setKioskLayout(response.data);
    return response.data;
  };

  const updateKioskTexts = async (newTexts) => {
    const response = await axios.put(`${API}/settings/kiosk-texts`, { value: newTexts });
    setKioskTexts(response.data);
    return response.data;
  };

  const updatePwaConfig = async (newPwaConfig) => {
    const response = await axios.put(`${API}/settings/pwa`, { value: newPwaConfig });
    setPwaConfig(response.data);
    return response.data;
  };

  const updateLockscreenQr = async (newLockscreenQr) => {
    const response = await axios.put(`${API}/settings/lockscreen-qr`, { value: newLockscreenQr });
    setLockscreenQr(response.data);
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
      kioskTheme,
      adminTheme,
      kioskLayout,
      kioskTexts,
      pwaConfig,
      lockscreenQr,
      loading,
      theme,
      updateBranding,
      updatePricing,
      updatePalettes,
      updateKioskTheme,
      updateAdminTheme,
      updateKioskLayout,
      updateKioskTexts,
      updatePwaConfig,
      updateLockscreenQr,
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

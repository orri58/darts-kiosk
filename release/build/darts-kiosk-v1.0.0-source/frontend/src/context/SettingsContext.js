import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

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
    mode: 'per_game',
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
    credits_label: 'Spiele übrig',
    time_label: 'Zeit übrig',
    staff_hint: '',
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
      
      setBranding(brandingRes.data);
      setPricing(pricingRes.data);
      setPalettes(palettesRes.data);
      if (textsRes.data) setKioskTexts(prev => ({ ...prev, ...textsRes.data }));
      if (pwaRes.data) setPwaConfig(prev => ({ ...prev, ...pwaRes.data }));
      if (qrRes.data) setLockscreenQr(prev => ({ ...prev, ...qrRes.data }));

      // Set document title from branding
      document.title = brandingRes.data.cafe_name || 'Darts Kiosk';
      // Update manifest theme color
      const metaTheme = document.querySelector('meta[name="theme-color"]');
      if (metaTheme && pwaRes.data?.theme_color) metaTheme.content = pwaRes.data.theme_color;
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // Apply palette CSS variables when palette changes
  useEffect(() => {
    if (palettes.length > 0 && branding.palette_id) {
      const palette = palettes.find(p => p.id === branding.palette_id);
      if (palette) {
        const root = document.documentElement;
        root.style.setProperty('--color-bg', palette.colors.bg);
        root.style.setProperty('--color-surface', palette.colors.surface);
        root.style.setProperty('--color-primary', palette.colors.primary);
        root.style.setProperty('--color-secondary', palette.colors.secondary);
        root.style.setProperty('--color-accent', palette.colors.accent);
        root.style.setProperty('--color-text', palette.colors.text);
      }
    }
  }, [palettes, branding.palette_id]);

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
    return palettes.find(p => p.id === branding.palette_id) || palettes[0];
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

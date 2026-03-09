import { useState, useEffect, useMemo } from 'react';
import { toast } from 'sonner';
import { 
  Palette, 
  Type, 
  Euro, 
  Upload, 
  Check, 
  Image as ImageIcon,
  Save,
  ShieldCheck,
  Plus,
  Trash2,
  AlertTriangle,
  Download,
  ClipboardCopy,
  Eye,
  Volume2,
  Globe,
  QrCode
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Switch } from '../../components/ui/switch';
import { useSettings } from '../../context/SettingsContext';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Hex validation
const isValidHex = (hex) => /^#[0-9A-Fa-f]{6}$/.test(hex);

// Relative luminance per WCAG 2.0
function getLuminance(hex) {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const toLinear = (c) => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

function getContrastRatio(hex1, hex2) {
  if (!isValidHex(hex1) || !isValidHex(hex2)) return 0;
  const l1 = getLuminance(hex1);
  const l2 = getLuminance(hex2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

const COLOR_FIELDS = [
  { key: 'bg', label: 'Hintergrund' },
  { key: 'surface', label: 'Oberfläche' },
  { key: 'primary', label: 'Primär' },
  { key: 'secondary', label: 'Sekundär' },
  { key: 'accent', label: 'Akzent' },
  { key: 'text', label: 'Text' },
];

const EMPTY_PALETTE = { bg: '#09090b', surface: '#18181b', primary: '#f59e0b', secondary: '#ffffff', accent: '#ef4444', text: '#e4e4e7' };

export default function AdminSettings() {
  const { branding, pricing, palettes, kioskTexts, pwaConfig, lockscreenQr, updateBranding, updatePricing, updatePalettes, refreshSettings } = useSettings();
  const { token } = useAuth();
  
  const [localBranding, setLocalBranding] = useState(branding);
  const [localPricing, setLocalPricing] = useState(pricing);
  const [localKioskTexts, setLocalKioskTexts] = useState(kioskTexts);
  const [localPwa, setLocalPwa] = useState(pwaConfig);
  const [localQr, setLocalQr] = useState(lockscreenQr);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Palette editor state
  const [editingPalette, setEditingPalette] = useState(null); // null=closed, object=editing
  const [editingName, setEditingName] = useState('');
  const [editingColors, setEditingColors] = useState({ ...EMPTY_PALETTE });
  const [isNewPalette, setIsNewPalette] = useState(true);
  const [jsonImport, setJsonImport] = useState('');
  const [showJsonImport, setShowJsonImport] = useState(false);

  // Contrast warnings
  const contrastWarnings = useMemo(() => {
    const warnings = [];
    if (!isValidHex(editingColors.text) || !isValidHex(editingColors.bg)) return warnings;
    const textOnBg = getContrastRatio(editingColors.text, editingColors.bg);
    if (textOnBg < 4.5) warnings.push({ pair: 'Text / Hintergrund', ratio: textOnBg.toFixed(1), level: textOnBg < 3 ? 'critical' : 'warning' });
    if (isValidHex(editingColors.surface)) {
      const textOnSurface = getContrastRatio(editingColors.text, editingColors.surface);
      if (textOnSurface < 4.5) warnings.push({ pair: 'Text / Oberfläche', ratio: textOnSurface.toFixed(1), level: textOnSurface < 3 ? 'critical' : 'warning' });
    }
    if (isValidHex(editingColors.primary) && isValidHex(editingColors.bg)) {
      const primaryOnBg = getContrastRatio(editingColors.primary, editingColors.bg);
      if (primaryOnBg < 3) warnings.push({ pair: 'Primär / Hintergrund', ratio: primaryOnBg.toFixed(1), level: 'warning' });
    }
    return warnings;
  }, [editingColors]);

  const openNewPalette = () => {
    setEditingPalette('new');
    setEditingName('Mein Theme');
    setEditingColors({ ...EMPTY_PALETTE });
    setIsNewPalette(true);
  };

  const openEditPalette = (palette) => {
    setEditingPalette(palette.id);
    setEditingName(palette.name);
    setEditingColors({ ...palette.colors });
    setIsNewPalette(false);
  };

  const closePaletteEditor = () => {
    setEditingPalette(null);
    setShowJsonImport(false);
    setJsonImport('');
  };

  const handleSavePalette = async () => {
    if (!editingName.trim()) { toast.error('Name erforderlich'); return; }
    const invalid = COLOR_FIELDS.filter(f => !isValidHex(editingColors[f.key]));
    if (invalid.length > 0) { toast.error(`Ungültiger Hex: ${invalid.map(f => f.label).join(', ')}`); return; }

    setSaving(true);
    try {
      let updated;
      if (isNewPalette) {
        const id = editingName.trim().toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_');
        const existing = palettes.find(p => p.id === id);
        if (existing) { toast.error(`Palette "${id}" existiert bereits`); setSaving(false); return; }
        updated = [...palettes, { id, name: editingName.trim(), colors: { ...editingColors }, custom: true }];
      } else {
        updated = palettes.map(p => p.id === editingPalette ? { ...p, name: editingName.trim(), colors: { ...editingColors } } : p);
      }
      await updatePalettes(updated);
      closePaletteEditor();
      toast.success('Farbschema gespeichert');
    } catch { toast.error('Fehler beim Speichern'); }
    finally { setSaving(false); }
  };

  const handleDeletePalette = async (paletteId) => {
    if (localBranding.palette_id === paletteId) { toast.error('Aktives Schema kann nicht gelöscht werden'); return; }
    setSaving(true);
    try {
      const updated = palettes.filter(p => p.id !== paletteId);
      await updatePalettes(updated);
      toast.success('Farbschema gelöscht');
    } catch { toast.error('Fehler beim Löschen'); }
    finally { setSaving(false); }
  };

  const handleJsonImport = () => {
    try {
      const parsed = JSON.parse(jsonImport);
      if (parsed.colors) {
        const c = parsed.colors;
        const valid = COLOR_FIELDS.every(f => isValidHex(c[f.key]));
        if (!valid) { toast.error('Ungültige Hex-Werte im Import'); return; }
        setEditingColors({ ...c });
        if (parsed.name) setEditingName(parsed.name);
        setShowJsonImport(false);
        setJsonImport('');
        toast.success('Palette importiert');
      } else {
        toast.error('Ungültiges Format (benötigt "colors" Objekt)');
      }
    } catch { toast.error('Ungültiges JSON'); }
  };

  const handleJsonExport = () => {
    const data = JSON.stringify({ name: editingName, colors: editingColors }, null, 2);
    navigator.clipboard.writeText(data).then(() => toast.success('In Zwischenablage kopiert')).catch(() => toast.error('Kopieren fehlgeschlagen'));
  };

  // Stammkunde display settings
  const [stammkundeDisplay, setStammkundeDisplay] = useState({
    enabled: false, period: 'month', interval_seconds: 6, max_entries: 3, nickname_max_length: 15
  });
  const [stammkundeLoading, setStammkundeLoading] = useState(true);

  // Sound config state
  const [soundConfig, setSoundConfig] = useState({
    enabled: false, volume: 70, sound_pack: 'default',
    quiet_hours_enabled: false, quiet_hours_start: '22:00', quiet_hours_end: '08:00',
    rate_limit_ms: 1500,
  });
  const [soundPacks, setSoundPacks] = useState([]);
  const [soundLoading, setSoundLoading] = useState(true);
  const [testingSound, setTestingSound] = useState(null);

  // Language state
  const { lang, t, switchLang } = useI18n();
  const [languageSetting, setLanguageSetting] = useState('de');
  const [langLoading, setLangLoading] = useState(true);

  // Match sharing state
  const [matchSharing, setMatchSharing] = useState({ enabled: false, qr_timeout: 60 });
  const [matchSharingLoading, setMatchSharingLoading] = useState(true);

  useEffect(() => {
    const fetchStammkunde = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const res = await axios.get(`${API}/settings/stammkunde-display`, { headers });
        setStammkundeDisplay(res.data);
      } catch { /* use defaults */ }
      finally { setStammkundeLoading(false); }
    };
    fetchStammkunde();
    // Fetch sound config + packs
    const fetchSound = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const [cfgRes, packsRes] = await Promise.all([
          axios.get(`${API}/settings/sound`, { headers }),
          axios.get(`${API}/sounds/packs`, { headers }),
        ]);
        setSoundConfig(cfgRes.data);
        setSoundPacks(packsRes.data.packs || []);
      } catch { /* use defaults */ }
      finally { setSoundLoading(false); }
    };
    fetchSound();
    // Fetch language setting
    const fetchLang = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const res = await axios.get(`${API}/settings/language`, { headers });
        setLanguageSetting(res.data?.language || 'de');
      } catch { /* use default */ }
      finally { setLangLoading(false); }
    };
    fetchLang();
    // Fetch match sharing
    const fetchMatchSharing = async () => {
      try {
        const res = await axios.get(`${API}/settings/match-sharing`);
        setMatchSharing(res.data);
      } catch { /* use defaults */ }
      finally { setMatchSharingLoading(false); }
    };
    fetchMatchSharing();
  }, [token]);

  // Sync local kiosk texts & PWA config when context updates
  useEffect(() => {
    setLocalKioskTexts(kioskTexts);
  }, [kioskTexts]);
  useEffect(() => {
    setLocalPwa(pwaConfig);
  }, [pwaConfig]);
  useEffect(() => {
    setLocalQr(lockscreenQr);
  }, [lockscreenQr]);

  const handleSaveKioskTexts = async () => {
    setSaving(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await Promise.all([
        axios.put(`${API}/settings/kiosk-texts`, { value: localKioskTexts }, { headers }),
        axios.put(`${API}/settings/lockscreen-qr`, { value: localQr }, { headers }),
      ]);
      refreshSettings();
      toast.success('Kiosk-Einstellungen gespeichert');
    } catch { toast.error('Fehler beim Speichern'); }
    finally { setSaving(false); }
  };

  const handleSavePwa = async () => {
    setSaving(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.put(`${API}/settings/pwa`, { value: localPwa }, { headers });
      refreshSettings();
      toast.success('PWA-Konfiguration gespeichert');
    } catch { toast.error('Fehler beim Speichern'); }
    finally { setSaving(false); }
  };

  const handleSaveStammkundeDisplay = async () => {
    setSaving(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.put(`${API}/settings/stammkunde-display`, { value: stammkundeDisplay }, { headers });
      setStammkundeDisplay(res.data);
      toast.success('Stammkunde-Anzeige gespeichert');
    } catch (error) {
      toast.error('Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSoundConfig = async () => {
    setSaving(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.put(`${API}/settings/sound`, { value: soundConfig }, { headers });
      setSoundConfig(res.data);
      toast.success('Sound-Einstellungen gespeichert');
    } catch { toast.error('Fehler beim Speichern'); }
    finally { setSaving(false); }
  };

  const handleTestSound = async (event) => {
    setTestingSound(event);
    try {
      const pack = soundConfig.sound_pack || 'default';
      const audio = new Audio(`${API}/sounds/${pack}/${event}.wav`);
      audio.volume = (soundConfig.volume || 70) / 100;
      await audio.play();
    } catch { toast.error('Sound konnte nicht abgespielt werden'); }
    finally { setTimeout(() => setTestingSound(null), 1000); }
  };

  const handleSaveLanguage = async () => {
    setSaving(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.put(`${API}/settings/language`, { value: { language: languageSetting } }, { headers });
      setLanguageSetting(res.data.language);
      switchLang(res.data.language);
      toast.success(res.data.language === 'de' ? 'Sprache gespeichert' : 'Language saved');
    } catch { toast.error('Error saving language'); }
    finally { setSaving(false); }
  };

  const handleSaveMatchSharing = async () => {
    setSaving(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.put(`${API}/settings/match-sharing`, { value: matchSharing }, { headers });
      setMatchSharing(res.data);
      toast.success(t('save_success') || 'Gespeichert');
    } catch { toast.error('Fehler beim Speichern'); }
    finally { setSaving(false); }
  };

  const handleSaveBranding = async () => {
    setSaving(true);
    try {
      await updateBranding(localBranding);
      toast.success('Branding gespeichert');
    } catch (error) {
      toast.error('Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  };

  const handleSavePricing = async () => {
    setSaving(true);
    try {
      await updatePricing(localPricing);
      toast.success('Preise gespeichert');
    } catch (error) {
      toast.error('Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API}/assets/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      setLocalBranding({ ...localBranding, logo_url: `${API}/assets/${response.data.filename}` });
      toast.success('Logo hochgeladen');
    } catch (error) {
      toast.error('Fehler beim Upload');
    } finally {
      setUploading(false);
    }
  };

  const toggleGameType = (gameType) => {
    const current = localPricing.allowed_game_types || [];
    const updated = current.includes(gameType)
      ? current.filter(g => g !== gameType)
      : [...current, gameType];
    setLocalPricing({ ...localPricing, allowed_game_types: updated });
  };

  return (
    <div data-testid="admin-settings">
      <div className="mb-6">
        <h1 className="text-2xl font-heading uppercase tracking-wider text-white">{t('settings')}</h1>
        <p className="text-zinc-500">{t('branding_pricing_config')}</p>
      </div>

      <Tabs defaultValue="branding" className="space-y-6">
        <TabsList className="bg-zinc-900 border border-zinc-800 p-1 flex flex-wrap h-auto gap-1">
          <TabsTrigger value="branding" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Palette className="w-4 h-4 mr-2" />
            {t('branding')}
          </TabsTrigger>
          <TabsTrigger value="pricing" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Euro className="w-4 h-4 mr-2" />
            {t('pricing')}
          </TabsTrigger>
          <TabsTrigger value="palettes" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Type className="w-4 h-4 mr-2" />
            {t('color_scheme')}
          </TabsTrigger>
          <TabsTrigger value="stammkunde" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <ShieldCheck className="w-4 h-4 mr-2" />
            {t('stammkunde')}
          </TabsTrigger>
          <TabsTrigger value="sound" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Volume2 className="w-4 h-4 mr-2" />
            {t('sound')}
          </TabsTrigger>
          <TabsTrigger value="language" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Globe className="w-4 h-4 mr-2" />
            {t('language')}
          </TabsTrigger>
          <TabsTrigger value="match-sharing" data-testid="tab-match-sharing" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <QrCode className="w-4 h-4 mr-2" />
            QR Sharing
          </TabsTrigger>
          <TabsTrigger value="kiosk-texts" data-testid="tab-kiosk-texts" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Type className="w-4 h-4 mr-2" />
            {t('kiosk_texts') || 'Kiosk-Texte'}
          </TabsTrigger>
          <TabsTrigger value="pwa" data-testid="tab-pwa" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Download className="w-4 h-4 mr-2" />
            PWA / App
          </TabsTrigger>
        </TabsList>

        {/* Branding Tab */}
        <TabsContent value="branding" className="space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <ImageIcon className="w-5 h-5 text-amber-500" />
                Logo & Name
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Logo Upload */}
              <div className="space-y-3">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Logo</label>
                <div className="flex items-center gap-4">
                  <div className="w-24 h-24 bg-zinc-800 border-2 border-dashed border-zinc-700 rounded-sm flex items-center justify-center overflow-hidden">
                    {localBranding.logo_url ? (
                      <img src={localBranding.logo_url} alt="Logo" className="max-w-full max-h-full object-contain" />
                    ) : (
                      <ImageIcon className="w-8 h-8 text-zinc-600" />
                    )}
                  </div>
                  <div>
                    <input
                      type="file"
                      accept="image/png,image/svg+xml,image/jpeg,image/webp"
                      onChange={handleLogoUpload}
                      className="hidden"
                      id="logo-upload"
                    />
                    <label
                      htmlFor="logo-upload"
                      className="inline-flex items-center px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-sm text-zinc-300 cursor-pointer hover:border-amber-500/50 hover:text-amber-500 transition-all"
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      {uploading ? 'Wird hochgeladen...' : 'Logo hochladen'}
                    </label>
                    <p className="text-xs text-zinc-600 mt-2">PNG, SVG, JPG, WebP (max. 2MB)</p>
                    {localBranding.logo_url && (
                      <button
                        data-testid="remove-logo-btn"
                        onClick={async () => {
                          try {
                            const headers = { Authorization: `Bearer ${token}` };
                            await axios.delete(`${API}/settings/branding/logo`, { headers });
                            setLocalBranding({ ...localBranding, logo_url: '' });
                            toast.success('Logo entfernt');
                          } catch { toast.error('Fehler beim Entfernen'); }
                        }}
                        className="text-xs text-red-400 hover:text-red-300 mt-1 underline"
                      >
                        Logo entfernen
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Cafe Name */}
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Cafe Name</label>
                <Input
                  value={localBranding.cafe_name || ''}
                  onChange={(e) => setLocalBranding({ ...localBranding, cafe_name: e.target.value })}
                  placeholder="Dart Zone"
                  data-testid="cafe-name-input"
                  className="input-industrial"
                />
              </div>

              {/* Subtitle */}
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Untertitel</label>
                <Input
                  value={localBranding.subtitle || ''}
                  onChange={(e) => setLocalBranding({ ...localBranding, subtitle: e.target.value })}
                  placeholder="Darts & More"
                  data-testid="subtitle-input"
                  className="input-industrial"
                />
              </div>

              <Button
                onClick={handleSaveBranding}
                disabled={saving}
                data-testid="save-branding-btn"
                className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading"
              >
                <Save className="w-4 h-4 mr-2" />
                {saving ? 'Speichern...' : 'Speichern'}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pricing Tab */}
        <TabsContent value="pricing" className="space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Euro className="w-5 h-5 text-amber-500" />
                Preisgestaltung
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Default Mode */}
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Standard-Modus</label>
                <div className="grid grid-cols-3 gap-2">
                  {['per_game', 'per_time', 'per_player'].map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setLocalPricing({ ...localPricing, mode })}
                      className={`p-3 rounded-sm border-2 transition-all ${
                        localPricing.mode === mode
                          ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                          : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                      }`}
                    >
                      {mode === 'per_game' ? 'Pro Spiel' : mode === 'per_time' ? 'Pro Zeit' : 'Pro Spieler'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Per Game Pricing */}
              <div className="bg-zinc-800/50 rounded-sm p-4 space-y-4">
                <h4 className="text-sm text-zinc-400 uppercase tracking-wider">Pro Spiel</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-xs text-zinc-500">Preis pro Spiel (€)</label>
                    <Input
                      type="number"
                      step="0.5"
                      value={localPricing.per_game?.price_per_credit || 2}
                      onChange={(e) => setLocalPricing({
                        ...localPricing,
                        per_game: { ...localPricing.per_game, price_per_credit: parseFloat(e.target.value) }
                      })}
                      data-testid="price-per-game-input"
                      className="input-industrial h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs text-zinc-500">Standard Credits</label>
                    <Input
                      type="number"
                      value={localPricing.per_game?.default_credits || 3}
                      onChange={(e) => setLocalPricing({
                        ...localPricing,
                        per_game: { ...localPricing.per_game, default_credits: parseInt(e.target.value) }
                      })}
                      data-testid="default-credits-input"
                      className="input-industrial h-10"
                    />
                  </div>
                </div>
              </div>

              {/* Per Time Pricing */}
              <div className="bg-zinc-800/50 rounded-sm p-4 space-y-4">
                <h4 className="text-sm text-zinc-400 uppercase tracking-wider">Pro Zeit</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-xs text-zinc-500">30 Minuten (€)</label>
                    <Input
                      type="number"
                      step="0.5"
                      value={localPricing.per_time?.price_per_30_min || 5}
                      onChange={(e) => setLocalPricing({
                        ...localPricing,
                        per_time: { ...localPricing.per_time, price_per_30_min: parseFloat(e.target.value) }
                      })}
                      data-testid="price-30-min-input"
                      className="input-industrial h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs text-zinc-500">60 Minuten (€)</label>
                    <Input
                      type="number"
                      step="0.5"
                      value={localPricing.per_time?.price_per_60_min || 8}
                      onChange={(e) => setLocalPricing({
                        ...localPricing,
                        per_time: { ...localPricing.per_time, price_per_60_min: parseFloat(e.target.value) }
                      })}
                      data-testid="price-60-min-input"
                      className="input-industrial h-10"
                    />
                  </div>
                </div>
              </div>

              {/* Per Player Pricing */}
              <div className="bg-zinc-800/50 rounded-sm p-4 space-y-4">
                <h4 className="text-sm text-zinc-400 uppercase tracking-wider">Pro Spieler</h4>
                <div className="space-y-2">
                  <label className="text-xs text-zinc-500">Preis pro Spieler (€)</label>
                  <Input
                    type="number"
                    step="0.5"
                    value={localPricing.per_player?.price_per_player || 1.5}
                    onChange={(e) => setLocalPricing({
                      ...localPricing,
                      per_player: { ...localPricing.per_player, price_per_player: parseFloat(e.target.value) }
                    })}
                    data-testid="price-per-player-input"
                    className="input-industrial h-10 max-w-xs"
                  />
                </div>
              </div>

              {/* Max Players */}
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Max. Spieler</label>
                <Input
                  type="number"
                  min="1"
                  max="8"
                  value={localPricing.max_players || 4}
                  onChange={(e) => setLocalPricing({ ...localPricing, max_players: parseInt(e.target.value) })}
                  data-testid="max-players-input"
                  className="input-industrial max-w-xs"
                />
              </div>

              {/* Allowed Game Types */}
              <div className="space-y-3">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Erlaubte Spielarten</label>
                <div className="flex flex-wrap gap-2">
                  {['301', '501', 'Cricket', 'Training', 'Around the Clock', 'Shanghai'].map((game) => (
                    <button
                      key={game}
                      onClick={() => toggleGameType(game)}
                      className={`px-4 py-2 rounded-sm border transition-all ${
                        (localPricing.allowed_game_types || []).includes(game)
                          ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                          : 'border-zinc-700 text-zinc-500 hover:border-zinc-600'
                      }`}
                    >
                      {(localPricing.allowed_game_types || []).includes(game) && (
                        <Check className="w-4 h-4 inline mr-2" />
                      )}
                      {game}
                    </button>
                  ))}
                </div>
              </div>

              <Button
                onClick={handleSavePricing}
                disabled={saving}
                data-testid="save-pricing-btn"
                className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading"
              >
                <Save className="w-4 h-4 mr-2" />
                {saving ? 'Speichern...' : 'Speichern'}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Palettes Tab */}
        <TabsContent value="palettes" className="space-y-6">
          {/* Palette Selection */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Palette className="w-5 h-5 text-amber-500" />
                Farbschema wählen
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {palettes.map((palette) => (
                  <div key={palette.id} className={`relative group p-4 rounded-sm border-2 transition-all cursor-pointer ${
                    localBranding.palette_id === palette.id ? 'border-amber-500 ring-2 ring-amber-500/30' : 'border-zinc-700 hover:border-zinc-600'
                  }`} onClick={() => setLocalBranding({ ...localBranding, palette_id: palette.id })}
                    data-testid={`palette-${palette.id}`}>
                    <div className="flex gap-1 mb-3 h-8">
                      <div className="flex-1 rounded-sm" style={{ backgroundColor: palette.colors.bg }}></div>
                      <div className="flex-1 rounded-sm" style={{ backgroundColor: palette.colors.surface }}></div>
                      <div className="flex-1 rounded-sm" style={{ backgroundColor: palette.colors.primary }}></div>
                      <div className="flex-1 rounded-sm" style={{ backgroundColor: palette.colors.accent }}></div>
                    </div>
                    <p className="text-sm text-center text-zinc-300">{palette.name}</p>
                    {localBranding.palette_id === palette.id && (
                      <div className="flex justify-center mt-2"><Check className="w-5 h-5 text-amber-500" /></div>
                    )}
                    {/* Edit + Delete for custom palettes */}
                    <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={(e) => { e.stopPropagation(); openEditPalette(palette); }} data-testid={`edit-palette-${palette.id}`}
                        className="p-1 bg-zinc-800 rounded-sm text-zinc-400 hover:text-amber-500 border border-zinc-700">
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      {palette.custom && (
                        <button onClick={(e) => { e.stopPropagation(); handleDeletePalette(palette.id); }} data-testid={`delete-palette-${palette.id}`}
                          className="p-1 bg-zinc-800 rounded-sm text-zinc-400 hover:text-red-500 border border-zinc-700">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                {/* New Palette Button */}
                <button onClick={openNewPalette} data-testid="new-palette-btn"
                  className="flex flex-col items-center justify-center gap-2 p-4 rounded-sm border-2 border-dashed border-zinc-700 text-zinc-500 hover:border-amber-500/50 hover:text-amber-500 transition-all min-h-[120px]">
                  <Plus className="w-6 h-6" />
                  <span className="text-xs uppercase tracking-wider">Neues Schema</span>
                </button>
              </div>

              <div className="mt-6">
                <Button onClick={handleSaveBranding} disabled={saving} data-testid="save-palette-btn"
                  className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading">
                  <Save className="w-4 h-4 mr-2" />
                  {saving ? 'Speichern...' : 'Farbschema anwenden'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Palette Editor (inline, below) */}
          {editingPalette !== null && (
            <Card className="bg-zinc-900 border-zinc-800 border-amber-500/30" data-testid="palette-editor">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Palette className="w-5 h-5 text-amber-500" />
                  {isNewPalette ? 'Neues Farbschema erstellen' : `"${editingName}" bearbeiten`}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Name */}
                <div className="space-y-2">
                  <label className="text-sm text-zinc-500 uppercase tracking-wider">Name</label>
                  <Input value={editingName} onChange={(e) => setEditingName(e.target.value)} placeholder="Mein Theme"
                    data-testid="palette-name-input" className="input-industrial max-w-xs" />
                </div>

                {/* Color inputs + live preview side by side */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Color inputs */}
                  <div className="space-y-3">
                    {COLOR_FIELDS.map((field) => (
                      <div key={field.key} className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-sm border border-zinc-700 flex-shrink-0 cursor-pointer relative overflow-hidden"
                          style={{ backgroundColor: isValidHex(editingColors[field.key]) ? editingColors[field.key] : '#000' }}>
                          <input type="color" value={isValidHex(editingColors[field.key]) ? editingColors[field.key] : '#000000'}
                            onChange={(e) => setEditingColors({ ...editingColors, [field.key]: e.target.value })}
                            className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" />
                        </div>
                        <div className="flex-1">
                          <label className="text-xs text-zinc-500 uppercase">{field.label}</label>
                          <Input value={editingColors[field.key]} data-testid={`palette-color-${field.key}`}
                            onChange={(e) => setEditingColors({ ...editingColors, [field.key]: e.target.value })}
                            className={`input-industrial h-8 text-sm font-mono ${!isValidHex(editingColors[field.key]) ? 'border-red-500' : ''}`}
                            placeholder="#000000" />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Live Preview */}
                  <div className="rounded-sm overflow-hidden border border-zinc-700" data-testid="palette-preview">
                    <div className="p-4" style={{ backgroundColor: editingColors.bg }}>
                      <p className="text-xs uppercase tracking-wider mb-2 opacity-60" style={{ color: editingColors.text }}>Vorschau</p>
                      <h3 className="text-lg font-heading font-bold mb-3" style={{ color: editingColors.text }}>Dart Zone</h3>
                      <div className="p-3 rounded-sm mb-3" style={{ backgroundColor: editingColors.surface }}>
                        <p className="text-sm" style={{ color: editingColors.text }}>Oberflächen-Element</p>
                        <p className="text-xs mt-1" style={{ color: editingColors.secondary }}>Sekundärer Text</p>
                      </div>
                      <div className="flex gap-2">
                        <div className="px-3 py-1.5 rounded-sm text-sm font-bold" style={{ backgroundColor: editingColors.primary, color: editingColors.bg }}>
                          Primär
                        </div>
                        <div className="px-3 py-1.5 rounded-sm text-sm font-bold" style={{ backgroundColor: editingColors.accent, color: editingColors.bg }}>
                          Akzent
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Contrast Warnings */}
                {contrastWarnings.length > 0 && (
                  <div className="space-y-2" data-testid="contrast-warnings">
                    {contrastWarnings.map((w, i) => (
                      <div key={i} className={`flex items-center gap-2 px-3 py-2 rounded-sm border text-sm ${
                        w.level === 'critical' ? 'bg-red-500/10 border-red-500/30 text-red-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      }`}>
                        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                        <span>{w.pair}: Kontrast {w.ratio}:1 {w.level === 'critical' ? '(zu niedrig!)' : '(WCAG AA empfiehlt 4.5:1)'}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* JSON Import/Export */}
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={handleJsonExport} data-testid="palette-export-btn"
                    className="text-zinc-400 border-zinc-700 hover:text-amber-500 hover:border-amber-500/50">
                    <ClipboardCopy className="w-3.5 h-3.5 mr-1.5" /> JSON Export
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setShowJsonImport(!showJsonImport)} data-testid="palette-import-toggle"
                    className="text-zinc-400 border-zinc-700 hover:text-amber-500 hover:border-amber-500/50">
                    <Download className="w-3.5 h-3.5 mr-1.5" /> JSON Import
                  </Button>
                </div>

                {showJsonImport && (
                  <div className="space-y-2" data-testid="palette-import-area">
                    <textarea value={jsonImport} onChange={(e) => setJsonImport(e.target.value)} rows={4} placeholder='{"name":"My Theme","colors":{"bg":"#09090b",...}}'
                      className="w-full bg-zinc-800 border border-zinc-700 rounded-sm p-3 text-sm font-mono text-zinc-300 placeholder-zinc-600 focus:border-amber-500 focus:outline-none" />
                    <Button size="sm" onClick={handleJsonImport} className="bg-amber-500 hover:bg-amber-400 text-black">Importieren</Button>
                  </div>
                )}

                {/* Save / Cancel */}
                <div className="flex gap-3">
                  <Button onClick={handleSavePalette} disabled={saving} data-testid="save-custom-palette-btn"
                    className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading">
                    <Save className="w-4 h-4 mr-2" /> {saving ? 'Speichern...' : 'Farbschema speichern'}
                  </Button>
                  <Button variant="outline" onClick={closePaletteEditor} className="text-zinc-400 border-zinc-700 hover:text-white">
                    Abbrechen
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
        {/* Stammkunde Display Tab */}
        <TabsContent value="stammkunde" className="space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-amber-500" />
                Stammkunde-Anzeige auf Kiosk
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {stammkundeLoading ? (
                <p className="text-zinc-500">Lade...</p>
              ) : (
                <>
                  {/* Enable Toggle */}
                  <div className="flex items-center justify-between bg-zinc-800/50 rounded-sm p-4 border border-zinc-700">
                    <div>
                      <p className="text-zinc-300">Top Stammkunden auf Locked Screen</p>
                      <p className="text-xs text-zinc-500 mt-1">Zeigt registrierte Top-Spieler auf dem gesperrten Kiosk-Bildschirm</p>
                    </div>
                    <Switch
                      checked={stammkundeDisplay.enabled}
                      onCheckedChange={(v) => setStammkundeDisplay({ ...stammkundeDisplay, enabled: v })}
                      data-testid="stammkunde-display-toggle"
                    />
                  </div>

                  {stammkundeDisplay.enabled && (
                    <>
                      {/* Period */}
                      <div className="space-y-2">
                        <label className="text-sm text-zinc-500 uppercase tracking-wider">Zeitraum</label>
                        <div className="grid grid-cols-4 gap-2">
                          {[
                            { id: 'today', label: 'Heute' },
                            { id: 'week', label: 'Woche' },
                            { id: 'month', label: 'Monat' },
                            { id: 'all', label: 'Gesamt' },
                          ].map((p) => (
                            <button key={p.id} onClick={() => setStammkundeDisplay({ ...stammkundeDisplay, period: p.id })}
                              data-testid={`stammkunde-period-${p.id}`}
                              className={`p-3 rounded-sm border-2 transition-all text-sm ${
                                stammkundeDisplay.period === p.id
                                  ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                                  : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                              }`}>
                              {p.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Interval */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <label className="text-sm text-zinc-500 uppercase tracking-wider">Rotations-Intervall (Sek.)</label>
                          <Input type="number" min="5" max="8" step="1"
                            value={stammkundeDisplay.interval_seconds}
                            onChange={(e) => setStammkundeDisplay({ ...stammkundeDisplay, interval_seconds: Math.min(8, Math.max(5, parseInt(e.target.value) || 6)) })}
                            data-testid="stammkunde-interval-input"
                            className="input-industrial h-10" />
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm text-zinc-500 uppercase tracking-wider">Max. Einträge</label>
                          <Input type="number" min="1" max="3" step="1"
                            value={stammkundeDisplay.max_entries}
                            onChange={(e) => setStammkundeDisplay({ ...stammkundeDisplay, max_entries: Math.min(3, Math.max(1, parseInt(e.target.value) || 3)) })}
                            data-testid="stammkunde-max-entries-input"
                            className="input-industrial h-10" />
                        </div>
                      </div>

                      {/* Nickname truncation */}
                      <div className="space-y-2">
                        <label className="text-sm text-zinc-500 uppercase tracking-wider">Nickname Max. Länge</label>
                        <Input type="number" min="8" max="30" step="1"
                          value={stammkundeDisplay.nickname_max_length}
                          onChange={(e) => setStammkundeDisplay({ ...stammkundeDisplay, nickname_max_length: Math.min(30, Math.max(8, parseInt(e.target.value) || 15)) })}
                          data-testid="stammkunde-nickname-length-input"
                          className="input-industrial h-10 max-w-xs" />
                        <p className="text-xs text-zinc-600">Nicknames werden nach dieser Länge abgeschnitten</p>
                      </div>
                    </>
                  )}

                  <Button onClick={handleSaveStammkundeDisplay} disabled={saving}
                    data-testid="save-stammkunde-display-btn"
                    className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading">
                    <Save className="w-4 h-4 mr-2" />
                    {saving ? 'Speichern...' : 'Speichern'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        {/* Sound Tab */}
        <TabsContent value="sound" className="space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Volume2 className="w-5 h-5 text-amber-500" />
                Kiosk Sound-Effekte
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {soundLoading ? (
                <p className="text-zinc-500">Lade...</p>
              ) : (
                <>
                  {/* Enable Toggle */}
                  <div className="flex items-center justify-between bg-zinc-800/50 rounded-sm p-4 border border-zinc-700">
                    <div>
                      <p className="text-zinc-300">Sound-Effekte aktivieren</p>
                      <p className="text-xs text-zinc-500 mt-1">Spielt Sounds bei Spielereignissen auf dem Kiosk</p>
                    </div>
                    <Switch
                      checked={soundConfig.enabled}
                      onCheckedChange={(v) => setSoundConfig({ ...soundConfig, enabled: v })}
                      data-testid="sound-enable-toggle"
                    />
                  </div>

                  {soundConfig.enabled && (
                    <>
                      {/* Volume */}
                      <div className="space-y-2">
                        <label className="text-sm text-zinc-500 uppercase tracking-wider">
                          Lautstärke: {soundConfig.volume}%
                        </label>
                        <input type="range" min="0" max="100" step="5"
                          value={soundConfig.volume}
                          onChange={(e) => setSoundConfig({ ...soundConfig, volume: parseInt(e.target.value) })}
                          data-testid="sound-volume-slider"
                          className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-amber-500" />
                      </div>

                      {/* Sound Pack */}
                      <div className="space-y-2">
                        <label className="text-sm text-zinc-500 uppercase tracking-wider">Sound-Pack</label>
                        <div className="flex gap-2">
                          {soundPacks.map((pack) => (
                            <button key={pack.id} onClick={() => setSoundConfig({ ...soundConfig, sound_pack: pack.id })}
                              data-testid={`sound-pack-${pack.id}`}
                              className={`px-4 py-2 rounded-sm border-2 transition-all text-sm ${
                                soundConfig.sound_pack === pack.id
                                  ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                                  : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                              }`}>
                              {pack.name}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Sound Preview / Test */}
                      <div className="space-y-2">
                        <label className="text-sm text-zinc-500 uppercase tracking-wider">Sounds testen</label>
                        <div className="grid grid-cols-5 gap-2">
                          {[
                            { id: 'start', label: 'Start' },
                            { id: 'one_eighty', label: '180!' },
                            { id: 'checkout', label: 'Checkout' },
                            { id: 'bust', label: 'Bust' },
                            { id: 'win', label: 'Sieg' },
                          ].map((s) => (
                            <button key={s.id} onClick={() => handleTestSound(s.id)}
                              data-testid={`test-sound-${s.id}`}
                              className={`p-3 rounded-sm border text-sm transition-all ${
                                testingSound === s.id
                                  ? 'border-amber-500 bg-amber-500/20 text-amber-400'
                                  : 'border-zinc-700 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300'
                              }`}>
                              {s.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Rate Limit */}
                      <div className="space-y-2">
                        <label className="text-sm text-zinc-500 uppercase tracking-wider">
                          Rate Limit: {soundConfig.rate_limit_ms}ms
                        </label>
                        <input type="range" min="500" max="5000" step="250"
                          value={soundConfig.rate_limit_ms}
                          onChange={(e) => setSoundConfig({ ...soundConfig, rate_limit_ms: parseInt(e.target.value) })}
                          data-testid="sound-rate-limit-slider"
                          className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-amber-500" />
                        <p className="text-xs text-zinc-600">Min. Abstand zwischen gleichen Sounds (+ max. 30/min global)</p>
                      </div>

                      {/* Quiet Hours */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between bg-zinc-800/50 rounded-sm p-4 border border-zinc-700">
                          <div>
                            <p className="text-zinc-300">Ruhezeiten</p>
                            <p className="text-xs text-zinc-500 mt-1">Sounds während der Ruhezeit stumm schalten</p>
                          </div>
                          <Switch
                            checked={soundConfig.quiet_hours_enabled}
                            onCheckedChange={(v) => setSoundConfig({ ...soundConfig, quiet_hours_enabled: v })}
                            data-testid="sound-quiet-hours-toggle"
                          />
                        </div>

                        {soundConfig.quiet_hours_enabled && (
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <label className="text-sm text-zinc-500 uppercase tracking-wider">Von</label>
                              <Input type="time" value={soundConfig.quiet_hours_start}
                                onChange={(e) => setSoundConfig({ ...soundConfig, quiet_hours_start: e.target.value })}
                                data-testid="sound-quiet-start"
                                className="input-industrial h-10" />
                            </div>
                            <div className="space-y-2">
                              <label className="text-sm text-zinc-500 uppercase tracking-wider">Bis</label>
                              <Input type="time" value={soundConfig.quiet_hours_end}
                                onChange={(e) => setSoundConfig({ ...soundConfig, quiet_hours_end: e.target.value })}
                                data-testid="sound-quiet-end"
                                className="input-industrial h-10" />
                            </div>
                          </div>
                        )}
                      </div>
                    </>
                  )}

                  <Button onClick={handleSaveSoundConfig} disabled={saving}
                    data-testid="save-sound-config-btn"
                    className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading">
                    <Save className="w-4 h-4 mr-2" />
                    {saving ? 'Speichern...' : 'Speichern'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        {/* Language Tab */}
        <TabsContent value="language" className="space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Globe className="w-5 h-5 text-amber-500" />
                Spracheinstellungen
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {langLoading ? (
                <p className="text-zinc-500">Lade...</p>
              ) : (
                <>
                  <p className="text-zinc-400 text-sm">Standard-Sprache für Kiosk und Admin-Oberfläche</p>

                  <div className="grid grid-cols-2 gap-4 max-w-md">
                    <button onClick={() => setLanguageSetting('de')} data-testid="lang-de-btn"
                      className={`flex items-center gap-3 p-4 rounded-sm border-2 transition-all ${
                        languageSetting === 'de' ? 'border-amber-500 bg-amber-500/20' : 'border-zinc-700 hover:border-zinc-600'
                      }`}>
                      <span className="text-2xl">🇩🇪</span>
                      <div className="text-left">
                        <p className={`font-heading font-bold ${languageSetting === 'de' ? 'text-amber-500' : 'text-zinc-300'}`}>Deutsch</p>
                        <p className="text-xs text-zinc-500">Standard</p>
                      </div>
                      {languageSetting === 'de' && <Check className="w-5 h-5 text-amber-500 ml-auto" />}
                    </button>

                    <button onClick={() => setLanguageSetting('en')} data-testid="lang-en-btn"
                      className={`flex items-center gap-3 p-4 rounded-sm border-2 transition-all ${
                        languageSetting === 'en' ? 'border-amber-500 bg-amber-500/20' : 'border-zinc-700 hover:border-zinc-600'
                      }`}>
                      <span className="text-2xl">🇬🇧</span>
                      <div className="text-left">
                        <p className={`font-heading font-bold ${languageSetting === 'en' ? 'text-amber-500' : 'text-zinc-300'}`}>English</p>
                        <p className="text-xs text-zinc-500">International</p>
                      </div>
                      {languageSetting === 'en' && <Check className="w-5 h-5 text-amber-500 ml-auto" />}
                    </button>
                  </div>

                  <Button onClick={handleSaveLanguage} disabled={saving}
                    data-testid="save-language-btn"
                    className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading">
                    <Save className="w-4 h-4 mr-2" />
                    {saving ? 'Speichern...' : 'Speichern'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Match Sharing Tab */}
        <TabsContent value="match-sharing" className="space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100 flex items-center gap-2">
                <QrCode className="w-5 h-5 text-amber-500" />
                QR Match Sharing
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {matchSharingLoading ? (
                <p className="text-zinc-400">Laden...</p>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-zinc-200 text-base">QR Match Sharing aktivieren</Label>
                      <p className="text-zinc-400 text-sm mt-1">
                        Nach Spielende wird ein QR-Code mit Match-Ergebnis angezeigt,
                        den Kunden scannen und teilen koennen.
                      </p>
                    </div>
                    <Switch
                      data-testid="match-sharing-toggle"
                      checked={matchSharing.enabled}
                      onCheckedChange={(v) => setMatchSharing({ ...matchSharing, enabled: v })}
                    />
                  </div>

                  {matchSharing.enabled && (
                    <div className="space-y-2 pl-4 border-l-2 border-amber-500/30">
                      <Label className="text-zinc-200">QR Anzeige Dauer (Sekunden)</Label>
                      <Input
                        data-testid="qr-timeout-input"
                        type="number"
                        min={5}
                        max={300}
                        value={matchSharing.qr_timeout}
                        onChange={(e) => setMatchSharing({ ...matchSharing, qr_timeout: parseInt(e.target.value) || 60 })}
                        className="bg-zinc-800 border-zinc-700 text-zinc-100 w-32"
                      />
                      <p className="text-zinc-500 text-xs">
                        QR-Screen verschwindet automatisch nach dieser Zeit.
                      </p>
                    </div>
                  )}

                  <Button
                    data-testid="save-match-sharing-btn"
                    onClick={handleSaveMatchSharing}
                    disabled={saving}
                    className="bg-amber-500 hover:bg-amber-600 text-black"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    {saving ? 'Speichern...' : 'Speichern'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Kiosk Texts Tab */}
        <TabsContent value="kiosk-texts" className="space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Type className="w-5 h-5 text-amber-500" />
                {t('kiosk_texts') || 'Kiosk-Texte konfigurieren'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <p className="text-sm text-zinc-400">Texte, die auf den Kiosk-Bildschirmen angezeigt werden.</p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-zinc-300">Gesperrt-Titel</Label>
                  <Input data-testid="kiosk-text-locked-title" value={localKioskTexts.locked_title || ''} onChange={(e) => setLocalKioskTexts(p => ({ ...p, locked_title: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="GESPERRT" />
                </div>
                <div>
                  <Label className="text-zinc-300">Gesperrt-Untertitel</Label>
                  <Input data-testid="kiosk-text-locked-subtitle" value={localKioskTexts.locked_subtitle || ''} onChange={(e) => setLocalKioskTexts(p => ({ ...p, locked_subtitle: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="Bitte an der Theke freischalten lassen" />
                </div>
                <div>
                  <Label className="text-zinc-300">Preishinweis (optional)</Label>
                  <Input data-testid="kiosk-text-pricing-hint" value={localKioskTexts.pricing_hint || ''} onChange={(e) => setLocalKioskTexts(p => ({ ...p, pricing_hint: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="z.B. Happy Hour: 50% Rabatt!" />
                </div>
                <div>
                  <Label className="text-zinc-300">Personal-Hinweis (optional)</Label>
                  <Input data-testid="kiosk-text-staff-hint" value={localKioskTexts.staff_hint || ''} onChange={(e) => setLocalKioskTexts(p => ({ ...p, staff_hint: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="z.B. Fragen? Personal hilft gerne!" />
                </div>
              </div>

              <div className="border-t border-zinc-800 pt-4">
                <h4 className="text-sm font-medium text-zinc-300 mb-3">Spielbildschirm-Texte</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label className="text-zinc-300">Spiel läuft</Label>
                    <Input data-testid="kiosk-text-game-running" value={localKioskTexts.game_running || ''} onChange={(e) => setLocalKioskTexts(p => ({ ...p, game_running: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="SPIEL LÄUFT" />
                  </div>
                  <div>
                    <Label className="text-zinc-300">Spiel beendet</Label>
                    <Input data-testid="kiosk-text-game-finished" value={localKioskTexts.game_finished || ''} onChange={(e) => setLocalKioskTexts(p => ({ ...p, game_finished: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="SPIEL BEENDET" />
                  </div>
                  <div>
                    <Label className="text-zinc-300">Personal rufen</Label>
                    <Input data-testid="kiosk-text-call-staff" value={localKioskTexts.call_staff || ''} onChange={(e) => setLocalKioskTexts(p => ({ ...p, call_staff: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="Personal rufen" />
                  </div>
                  <div>
                    <Label className="text-zinc-300">Credits-Label</Label>
                    <Input data-testid="kiosk-text-credits-label" value={localKioskTexts.credits_label || ''} onChange={(e) => setLocalKioskTexts(p => ({ ...p, credits_label: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="Spiele übrig" />
                  </div>
                  <div>
                    <Label className="text-zinc-300">Zeit-Label</Label>
                    <Input data-testid="kiosk-text-time-label" value={localKioskTexts.time_label || ''} onChange={(e) => setLocalKioskTexts(p => ({ ...p, time_label: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="Zeit übrig" />
                  </div>
                </div>
              </div>

              {/* Lock Screen QR Toggle */}
              <div className="border-t border-zinc-800 pt-4">
                <h4 className="text-sm font-medium text-zinc-300 mb-3">QR-Code auf Sperrbildschirm</h4>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <Label className="text-zinc-300">QR für Leaderboard anzeigen</Label>
                    <p className="text-xs text-zinc-500">Kleiner QR-Code unten rechts auf dem Sperrbildschirm</p>
                  </div>
                  <button
                    data-testid="lockscreen-qr-toggle"
                    onClick={() => setLocalQr(p => ({ ...p, enabled: !p.enabled }))}
                    className={`w-12 h-6 rounded-full transition-colors relative ${localQr.enabled ? 'bg-amber-500' : 'bg-zinc-700'}`}
                  >
                    <div className={`w-5 h-5 rounded-full bg-white absolute top-0.5 transition-all ${localQr.enabled ? 'left-6' : 'left-0.5'}`} />
                  </button>
                </div>
                {localQr.enabled && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
                    <div>
                      <Label className="text-zinc-300">QR-Label</Label>
                      <Input data-testid="lockscreen-qr-label" value={localQr.label || ''} onChange={(e) => setLocalQr(p => ({ ...p, label: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="Leaderboard & Stats" />
                    </div>
                    <div>
                      <Label className="text-zinc-300">Zielseite (Pfad)</Label>
                      <Input data-testid="lockscreen-qr-path" value={localQr.path || ''} onChange={(e) => setLocalQr(p => ({ ...p, path: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="/public/leaderboard" />
                    </div>
                  </div>
                )}
              </div>

              <Button data-testid="save-kiosk-texts-btn" onClick={handleSaveKioskTexts} disabled={saving} className="bg-amber-500 hover:bg-amber-600 text-black">
                <Save className="w-4 h-4 mr-2" />
                {saving ? 'Speichern...' : 'Speichern'}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* PWA / App Tab */}
        <TabsContent value="pwa" className="space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Download className="w-5 h-5 text-amber-500" />
                PWA / Installierbare App
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <p className="text-sm text-zinc-400">
                Konfiguriere den App-Namen und das Erscheinungsbild, wenn die App auf einem Gerät installiert wird.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-zinc-300">App-Name (lang)</Label>
                  <Input data-testid="pwa-app-name" value={localPwa.app_name || ''} onChange={(e) => setLocalPwa(p => ({ ...p, app_name: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="Darts Kiosk System" />
                  <p className="text-xs text-zinc-500 mt-1">Wird im App-Launcher angezeigt</p>
                </div>
                <div>
                  <Label className="text-zinc-300">Kurzname</Label>
                  <Input data-testid="pwa-short-name" value={localPwa.short_name || ''} onChange={(e) => setLocalPwa(p => ({ ...p, short_name: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white" placeholder="Darts" />
                  <p className="text-xs text-zinc-500 mt-1">Unter dem App-Icon auf dem Homescreen</p>
                </div>
                <div>
                  <Label className="text-zinc-300">Theme-Farbe</Label>
                  <div className="flex gap-2">
                    <Input data-testid="pwa-theme-color" type="color" value={localPwa.theme_color || '#09090b'} onChange={(e) => setLocalPwa(p => ({ ...p, theme_color: e.target.value }))} className="w-12 h-10 p-1 bg-zinc-800 border-zinc-700" />
                    <Input value={localPwa.theme_color || '#09090b'} onChange={(e) => setLocalPwa(p => ({ ...p, theme_color: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white font-mono" />
                  </div>
                </div>
                <div>
                  <Label className="text-zinc-300">Hintergrundfarbe</Label>
                  <div className="flex gap-2">
                    <Input data-testid="pwa-bg-color" type="color" value={localPwa.background_color || '#09090b'} onChange={(e) => setLocalPwa(p => ({ ...p, background_color: e.target.value }))} className="w-12 h-10 p-1 bg-zinc-800 border-zinc-700" />
                    <Input value={localPwa.background_color || '#09090b'} onChange={(e) => setLocalPwa(p => ({ ...p, background_color: e.target.value }))} className="bg-zinc-800 border-zinc-700 text-white font-mono" />
                  </div>
                </div>
              </div>

              <div className="bg-zinc-800/50 border border-zinc-700 rounded-sm p-4">
                <h4 className="text-sm font-medium text-zinc-300 mb-2">Installationshinweis</h4>
                <p className="text-xs text-zinc-400">
                  Auf <strong>Android</strong>: Chrome &rarr; Menü (&vellip;) &rarr; "Zum Startbildschirm hinzufügen"<br />
                  Auf <strong>iPhone/iPad</strong>: Safari &rarr; Teilen-Button &rarr; "Zum Home-Bildschirm"<br />
                  Auf <strong>Desktop</strong>: Chrome/Edge &rarr; Adressleiste &rarr; Install-Icon
                </p>
              </div>

              <Button data-testid="save-pwa-btn" onClick={handleSavePwa} disabled={saving} className="bg-amber-500 hover:bg-amber-600 text-black">
                <Save className="w-4 h-4 mr-2" />
                {saving ? 'Speichern...' : 'Speichern'}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

import { useState } from 'react';
import { toast } from 'sonner';
import { 
  Palette, 
  Type, 
  Euro, 
  Upload, 
  Check, 
  Image as ImageIcon,
  Save
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Switch } from '../../components/ui/switch';
import { useSettings } from '../../context/SettingsContext';
import { useAuth } from '../../context/AuthContext';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminSettings() {
  const { branding, pricing, palettes, updateBranding, updatePricing } = useSettings();
  const { token } = useAuth();
  
  const [localBranding, setLocalBranding] = useState(branding);
  const [localPricing, setLocalPricing] = useState(pricing);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

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
        <h1 className="text-2xl font-heading uppercase tracking-wider text-white">Einstellungen</h1>
        <p className="text-zinc-500">Branding, Preise und Konfiguration</p>
      </div>

      <Tabs defaultValue="branding" className="space-y-6">
        <TabsList className="bg-zinc-900 border border-zinc-800 p-1">
          <TabsTrigger value="branding" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Palette className="w-4 h-4 mr-2" />
            Branding
          </TabsTrigger>
          <TabsTrigger value="pricing" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Euro className="w-4 h-4 mr-2" />
            Preise
          </TabsTrigger>
          <TabsTrigger value="palettes" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Type className="w-4 h-4 mr-2" />
            Farbschema
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
                  <button
                    key={palette.id}
                    onClick={() => {
                      setLocalBranding({ ...localBranding, palette_id: palette.id });
                    }}
                    data-testid={`palette-${palette.id}`}
                    className={`p-4 rounded-sm border-2 transition-all ${
                      localBranding.palette_id === palette.id
                        ? 'border-amber-500 ring-2 ring-amber-500/30'
                        : 'border-zinc-700 hover:border-zinc-600'
                    }`}
                  >
                    {/* Color Preview */}
                    <div className="flex gap-1 mb-3 h-8">
                      <div className="flex-1 rounded-sm" style={{ backgroundColor: palette.colors.bg }}></div>
                      <div className="flex-1 rounded-sm" style={{ backgroundColor: palette.colors.surface }}></div>
                      <div className="flex-1 rounded-sm" style={{ backgroundColor: palette.colors.primary }}></div>
                      <div className="flex-1 rounded-sm" style={{ backgroundColor: palette.colors.accent }}></div>
                    </div>
                    <p className="text-sm text-center text-zinc-300">{palette.name}</p>
                    {localBranding.palette_id === palette.id && (
                      <div className="flex justify-center mt-2">
                        <Check className="w-5 h-5 text-amber-500" />
                      </div>
                    )}
                  </button>
                ))}
              </div>

              <div className="mt-6">
                <Button
                  onClick={handleSaveBranding}
                  disabled={saving}
                  data-testid="save-palette-btn"
                  className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading"
                >
                  <Save className="w-4 h-4 mr-2" />
                  {saving ? 'Speichern...' : 'Farbschema anwenden'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

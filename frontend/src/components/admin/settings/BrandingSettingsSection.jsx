import axios from 'axios';
import { Image as ImageIcon, Palette, Upload, Check, Save } from 'lucide-react';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Input } from '../../ui/input';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function BrandingSettingsSection({
  localBranding,
  setLocalBranding,
  localKioskTheme,
  setLocalKioskTheme,
  localAdminTheme,
  setLocalAdminTheme,
  localKioskLayout,
  setLocalKioskLayout,
  palettes,
  handleLogoUpload,
  handleSaveBranding,
  saving,
  uploading,
  token,
  toast,
}) {
  const handleRemoveLogo = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.delete(`${API}/settings/branding/logo`, { headers });
      setLocalBranding({ ...localBranding, logo_url: '' });
      toast.success('Logo entfernt');
    } catch {
      toast.error('Fehler beim Entfernen');
    }
  };

  return (
    <div className="space-y-6">
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <ImageIcon className="w-5 h-5 text-amber-500" />
            Logo & Name
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-3">
            <label className="text-sm text-zinc-500 uppercase tracking-wider">Logo</label>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-2xl border border-dashed border-zinc-700 bg-zinc-800">
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
                  className="inline-flex items-center rounded-2xl border border-zinc-700 bg-zinc-800 px-4 py-2 text-zinc-300 cursor-pointer hover:border-amber-500/50 hover:text-amber-500 transition-all"
                >
                  <Upload className="w-4 h-4 mr-2" />
                  {uploading ? 'Wird hochgeladen...' : 'Logo hochladen'}
                </label>
                <p className="text-xs text-zinc-600 mt-2">PNG, SVG, JPG, WebP · max. 2MB</p>
                {localBranding.logo_url && (
                  <button
                    data-testid="remove-logo-btn"
                    onClick={handleRemoveLogo}
                    className="text-xs text-red-400 hover:text-red-300 mt-1 underline"
                  >
                    Logo entfernen
                  </button>
                )}
              </div>
            </div>
          </div>

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

          <div className="grid gap-4 xl:grid-cols-2">
            <div className="space-y-3 rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
              <div>
                <p className="text-sm font-medium text-white">Kiosk-Thema</p>
                <p className="text-xs text-zinc-500">Nur für Kiosk, Overlay und öffentliche Flächen.</p>
              </div>
              <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-zinc-500">Palette</label>
                <select
                  value={localKioskTheme?.palette_id || 'industrial'}
                  onChange={(e) => setLocalKioskTheme({ ...localKioskTheme, palette_id: e.target.value })}
                  className="input-industrial h-11"
                >
                  {palettes.map((palette) => (
                    <option key={`kiosk-${palette.id}`} value={palette.id}>{palette.name}</option>
                  ))}
                </select>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-xs uppercase tracking-wider text-zinc-500">Logo-Größe</label>
                  <select
                    value={localKioskLayout?.header?.logo_size || 'md'}
                    onChange={(e) => setLocalKioskLayout({ ...localKioskLayout, header: { ...(localKioskLayout?.header || {}), logo_size: e.target.value } })}
                    className="input-industrial h-11"
                  >
                    <option value="sm">Klein</option>
                    <option value="md">Mittel</option>
                    <option value="lg">Groß</option>
                    <option value="xl">Sehr groß</option>
                    <option value="2xl">Maximal</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-xs uppercase tracking-wider text-zinc-500">Header-Ausrichtung</label>
                  <select
                    value={localKioskLayout?.header?.align || 'left'}
                    onChange={(e) => setLocalKioskLayout({ ...localKioskLayout, header: { ...(localKioskLayout?.header || {}), align: e.target.value } })}
                    className="input-industrial h-11"
                  >
                    <option value="left">Links</option>
                    <option value="center">Mitte</option>
                  </select>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex items-center gap-3 rounded-xl border border-zinc-800 px-3 py-3 text-sm text-zinc-300">
                  <input
                    type="checkbox"
                    checked={Boolean(localKioskLayout?.header?.show_logo)}
                    onChange={(e) => setLocalKioskLayout({ ...localKioskLayout, header: { ...(localKioskLayout?.header || {}), show_logo: e.target.checked } })}
                  />
                  Logo anzeigen
                </label>
                <label className="flex items-center gap-3 rounded-xl border border-zinc-800 px-3 py-3 text-sm text-zinc-300">
                  <input
                    type="checkbox"
                    checked={Boolean(localKioskLayout?.header?.show_subtitle)}
                    onChange={(e) => setLocalKioskLayout({ ...localKioskLayout, header: { ...(localKioskLayout?.header || {}), show_subtitle: e.target.checked } })}
                  />
                  Untertitel anzeigen
                </label>
              </div>
            </div>

            <div className="space-y-3 rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
              <div>
                <p className="text-sm font-medium text-white">Admin-Thema</p>
                <p className="text-xs text-zinc-500">Ruhiger Operator-Look, unabhängig vom Kiosk.</p>
              </div>
              <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-zinc-500">Palette</label>
                <select
                  value={localAdminTheme?.palette_id || 'slate'}
                  onChange={(e) => setLocalAdminTheme({ ...localAdminTheme, palette_id: e.target.value })}
                  className="input-industrial h-11"
                >
                  {palettes.map((palette) => (
                    <option key={`admin-${palette.id}`} value={palette.id}>{palette.name}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-zinc-500">Pairing-Code auf Lockscreen</label>
                <select
                  value={localKioskLayout?.locked_screen?.pairing_position || 'bottom'}
                  onChange={(e) => setLocalKioskLayout({ ...localKioskLayout, locked_screen: { ...(localKioskLayout?.locked_screen || {}), pairing_position: e.target.value } })}
                  className="input-industrial h-11"
                >
                  <option value="bottom">Unten</option>
                  <option value="side">Rechte Seite</option>
                </select>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-xs uppercase tracking-wider text-zinc-500">Lockscreen Inhalt</label>
                  <select
                    value={localKioskLayout?.locked_screen?.content_align || 'left'}
                    onChange={(e) => setLocalKioskLayout({ ...localKioskLayout, locked_screen: { ...(localKioskLayout?.locked_screen || {}), content_align: e.target.value } })}
                    className="input-industrial h-11"
                  >
                    <option value="left">Links</option>
                    <option value="center">Mittig</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-xs uppercase tracking-wider text-zinc-500">Logo-Position Lockscreen</label>
                  <select
                    value={localKioskLayout?.locked_screen?.logo_position || 'header'}
                    onChange={(e) => setLocalKioskLayout({ ...localKioskLayout, locked_screen: { ...(localKioskLayout?.locked_screen || {}), logo_position: e.target.value } })}
                    className="input-industrial h-11"
                  >
                    <option value="header">Im Header</option>
                    <option value="hero">Groß im Hauptbereich</option>
                  </select>
                </div>
              </div>
              {(localKioskLayout?.locked_screen?.logo_position || 'header') === 'hero' && (
                <div className="space-y-2">
                  <label className="text-xs uppercase tracking-wider text-zinc-500">Lockscreen Logo-Größe</label>
                  <select
                    value={localKioskLayout?.locked_screen?.hero_logo_size || 'xl'}
                    onChange={(e) => setLocalKioskLayout({ ...localKioskLayout, locked_screen: { ...(localKioskLayout?.locked_screen || {}), hero_logo_size: e.target.value } })}
                    className="input-industrial h-11"
                  >
                    <option value="lg">Groß</option>
                    <option value="xl">Sehr groß</option>
                    <option value="2xl">Maximal</option>
                  </select>
                </div>
              )}
              <label className="flex items-center gap-3 rounded-xl border border-zinc-800 px-3 py-3 text-sm text-zinc-300">
                <input
                  type="checkbox"
                  checked={Boolean(localKioskLayout?.locked_screen?.show_community_widgets)}
                  onChange={(e) => setLocalKioskLayout({ ...localKioskLayout, locked_screen: { ...(localKioskLayout?.locked_screen || {}), show_community_widgets: e.target.checked } })}
                />
                Rankings / Community-Widgets auf dem Lockscreen anzeigen
              </label>
            </div>
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
    </div>
  );
}

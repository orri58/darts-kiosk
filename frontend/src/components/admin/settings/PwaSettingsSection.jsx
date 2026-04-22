import { Download, Save } from 'lucide-react';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';

export default function PwaSettingsSection({ localPwa, setLocalPwa, handleSavePwa, saving }) {
  return (
    <div className="space-y-6">
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
              Auf <strong>Android</strong>: Chrome → Menü (⋮) → "Zum Startbildschirm hinzufügen"<br />
              Auf <strong>iPhone/iPad</strong>: Safari → Teilen-Button → "Zum Home-Bildschirm"<br />
              Auf <strong>Desktop</strong>: Chrome/Edge → Adressleiste → Install-Icon
            </p>
          </div>

          <Button data-testid="save-pwa-btn" onClick={handleSavePwa} disabled={saving} className="bg-amber-500 hover:bg-amber-600 text-black">
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Speichern...' : 'Speichern'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

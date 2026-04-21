import { ClipboardCopy, Download, Trash2, Upload } from 'lucide-react';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';

export default function CustomizationProfilesSection({
  customizationBusy,
  customizationImportJson,
  setCustomizationImportJson,
  handleExportCustomizationProfile,
  handleResetCustomizationProfile,
  handleCustomizationImportFile,
  handleImportCustomizationProfile,
  toast,
}) {
  const handleCopyJson = async () => {
    try {
      await navigator.clipboard.writeText(customizationImportJson || '');
      toast.success('In Zwischenablage kopiert');
    } catch {
      toast.error('Kopieren fehlgeschlagen');
    }
  };

  return (
    <div className="space-y-6">
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <ClipboardCopy className="w-5 h-5 text-amber-500" />
            Customization Profiles
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4 text-sm text-zinc-400">
            Exportiere den aktuellen kiosk/admin Customization-Stand als JSON-Profil, importiere ihn auf anderen Geräten wieder oder setze die komplette Customization sauber auf Standard zurück.
          </div>
          <div className="grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
            <div className="space-y-4 rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
              <div>
                <p className="text-sm font-medium text-white">Export / Reset</p>
                <p className="text-xs text-zinc-500 mt-1">Ideal für Backup, Venue-Profile oder schnellen Rollout auf weitere Systeme.</p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row">
                <Button onClick={handleExportCustomizationProfile} disabled={customizationBusy} className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading">
                  <Download className="w-4 h-4 mr-2" />
                  {customizationBusy ? 'Läuft...' : 'Profil exportieren'}
                </Button>
                <Button onClick={handleResetCustomizationProfile} disabled={customizationBusy} variant="outline" className="border-red-700 text-red-300 hover:bg-red-950/40 uppercase font-heading">
                  <Trash2 className="w-4 h-4 mr-2" />
                  Auf Standard zurücksetzen
                </Button>
              </div>
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-zinc-400">
                Reset betrifft Branding, Themes, Layout, Kiosk-Texte, PWA, QR, Overlay, Sprache, Match-Sharing und weitere contract-gemanagte Customization-Felder.
              </div>
            </div>
            <div className="space-y-4 rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-white">Import</p>
                  <p className="text-xs text-zinc-500 mt-1">JSON-Datei laden oder den Profilinhalt direkt einfügen.</p>
                </div>
                <label className="inline-flex items-center rounded-2xl border border-zinc-700 bg-zinc-800 px-4 py-2 text-zinc-300 cursor-pointer hover:border-amber-500/50 hover:text-amber-500 transition-all">
                  <Upload className="w-4 h-4 mr-2" />
                  Datei laden
                  <input type="file" accept="application/json,.json" onChange={handleCustomizationImportFile} className="hidden" />
                </label>
              </div>
              <textarea
                value={customizationImportJson}
                onChange={(e) => setCustomizationImportJson(e.target.value)}
                placeholder='{"meta":{"type":"customization-profile","version":1},"bundle":{...}}'
                className="min-h-[280px] w-full rounded-2xl border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm text-zinc-200 outline-none focus:border-amber-500"
                data-testid="customization-profile-json"
              />
              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <Button onClick={handleCopyJson} disabled={!customizationImportJson || customizationBusy} variant="outline" className="border-zinc-700 text-zinc-300 uppercase font-heading">
                  <ClipboardCopy className="w-4 h-4 mr-2" />
                  JSON kopieren
                </Button>
                <Button onClick={handleImportCustomizationProfile} disabled={!customizationImportJson || customizationBusy} className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading" data-testid="import-customization-profile-btn">
                  <Upload className="w-4 h-4 mr-2" />
                  {customizationBusy ? 'Import läuft...' : 'Profil importieren'}
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

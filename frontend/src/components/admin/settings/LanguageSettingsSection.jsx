import { Check, Globe, Save } from 'lucide-react';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';

export default function LanguageSettingsSection({
  languageSetting,
  setLanguageSetting,
  langLoading,
  handleSaveLanguage,
  saving,
}) {
  return (
    <div className="space-y-6">
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
    </div>
  );
}

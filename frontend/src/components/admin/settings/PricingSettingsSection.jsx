import { Check, Euro, Save } from 'lucide-react';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Input } from '../../ui/input';

export default function PricingSettingsSection({ localPricing, setLocalPricing, toggleGameType, handleSavePricing, saving }) {
  return (
    <div className="space-y-6">
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Euro className="w-5 h-5 text-amber-500" />
            Preisgestaltung
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4 text-sm leading-6 text-zinc-400">
            Aktiv ist nur noch der Credits-Flow: freischalten, spielen, bei echtem Matchstart abbuchen.
            Legacy-Varianten bleiben intern kompatibel, tauchen hier aber nicht mehr als Hauptprodukt auf.
          </div>

          <div className="bg-zinc-800/50 rounded-sm p-4 space-y-4">
            <h4 className="text-sm text-zinc-400 uppercase tracking-wider">Credits</h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-xs text-zinc-500">Preis pro Credit (€)</label>
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
                <label className="text-xs text-zinc-500">Standard-Freischaltung</label>
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
    </div>
  );
}

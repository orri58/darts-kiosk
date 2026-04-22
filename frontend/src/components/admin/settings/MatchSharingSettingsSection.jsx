import { QrCode, Save } from 'lucide-react';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Switch } from '../../ui/switch';

export default function MatchSharingSettingsSection({
  matchSharing,
  setMatchSharing,
  matchSharingLoading,
  handleSaveMatchSharing,
  saving,
}) {
  return (
    <div className="space-y-6">
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
              <div className="flex items-center justify-between gap-4">
                <div>
                  <Label className="text-zinc-200 text-base">QR Match Sharing aktivieren</Label>
                  <p className="text-zinc-400 text-sm mt-1">
                    Nach echtem Session-Ende wird ein QR-Code mit Match-Ergebnis angezeigt.
                    Bei laufender Session mit Restcredits bleibt der Kiosk im lokalen Flow.
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
    </div>
  );
}

import axios from 'axios';
import { Eye, Save, Timer } from 'lucide-react';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Switch } from '../../ui/switch';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function KioskControlSettingsSection({
  postMatchDelay,
  setPostMatchDelay,
  autodartsDesktopSettings,
  setAutodartsDesktopSettings,
  savingKiosk,
  setSavingKiosk,
  token,
  toast,
  t,
}) {
  const handleSaveKioskControl = async () => {
    setSavingKiosk(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await Promise.all([
        axios.put(`${API}/settings/post-match-delay`, { value: postMatchDelay }, { headers }),
        axios.put(`${API}/settings/autodarts-desktop`, { value: autodartsDesktopSettings }, { headers }),
      ]);
      toast.success('Gespeichert');
    } catch {
      toast.error('Fehler beim Speichern');
    } finally {
      setSavingKiosk(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Timer className="w-5 h-5 text-amber-500" /> {t('post_match_delay')}
          </CardTitle>
          <p className="text-sm text-zinc-400">{t('post_match_delay_desc')}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-zinc-300">{t('delay_ms')}</Label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="0"
                max="15000"
                step="500"
                value={postMatchDelay.delay_ms}
                onChange={(e) => setPostMatchDelay({ ...postMatchDelay, delay_ms: parseInt(e.target.value) })}
                className="flex-1 accent-amber-500"
                data-testid="post-match-delay-slider"
              />
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min="0"
                  max="30000"
                  value={postMatchDelay.delay_ms}
                  onChange={(e) => setPostMatchDelay({ ...postMatchDelay, delay_ms: parseInt(e.target.value) || 0 })}
                  className="w-24 bg-zinc-800 border-zinc-700 text-white text-center"
                  data-testid="post-match-delay-input"
                />
                <span className="text-sm text-zinc-400">ms</span>
              </div>
            </div>
            <p className="text-xs text-zinc-500">{(postMatchDelay.delay_ms / 1000).toFixed(1)}s</p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Eye className="w-5 h-5 text-amber-500" /> {t('autodarts_desktop')}
          </CardTitle>
          <p className="text-sm text-zinc-400">{t('autodarts_desktop_desc')}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-zinc-300">{t('autodarts_exe_path')}</Label>
            <Input
              value={autodartsDesktopSettings.exe_path}
              onChange={(e) => setAutodartsDesktopSettings({ ...autodartsDesktopSettings, exe_path: e.target.value })}
              className="bg-zinc-800 border-zinc-700 text-white font-mono text-sm"
              placeholder="C:\Program Files\Autodarts\Autodarts.exe"
              data-testid="autodarts-exe-path-input"
            />
          </div>
          <div className="flex items-center gap-3">
            <Switch
              checked={autodartsDesktopSettings.auto_start}
              onCheckedChange={(v) => setAutodartsDesktopSettings({ ...autodartsDesktopSettings, auto_start: v })}
              data-testid="autodarts-auto-start-switch"
            />
            <Label className="text-zinc-300">{t('autodarts_auto_start')}</Label>
          </div>
        </CardContent>
      </Card>

      <Button
        onClick={handleSaveKioskControl}
        disabled={savingKiosk}
        className="bg-amber-500 hover:bg-amber-600 text-black font-medium w-full"
        data-testid="save-kiosk-control-btn"
      >
        <Save className="w-4 h-4 mr-2" />
        {savingKiosk ? 'Speichern...' : 'Speichern'}
      </Button>
    </div>
  );
}

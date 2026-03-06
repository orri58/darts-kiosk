import { useState, useEffect } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Trophy, Target, Users, Clock, Share2 } from 'lucide-react';

const QR_DISPLAY_SECONDS = 60;

export default function MatchResultScreen({ branding, matchToken, session, onTimeout }) {
  const [secondsLeft, setSecondsLeft] = useState(QR_DISPLAY_SECONDS);

  const matchUrl = `${window.location.origin}/match/${matchToken}`;

  useEffect(() => {
    const iv = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(iv);
          onTimeout();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(iv);
  }, [onTimeout]);

  const pct = (secondsLeft / QR_DISPLAY_SECONDS) * 100;

  return (
    <div className="h-full w-full flex flex-col bg-zinc-950" data-testid="match-result-screen">
      {/* Header */}
      <div className="p-6 border-b border-zinc-800">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <h1 className="text-2xl font-heading font-bold uppercase tracking-wider text-white">
            {branding?.cafe_name || 'Dart Zone'}
          </h1>
          <div className="flex items-center gap-2 bg-amber-500/20 text-amber-400 border border-amber-500/50 rounded-sm px-4 py-2">
            <Trophy className="w-5 h-5" />
            <span className="font-heading uppercase tracking-wider">SPIEL BEENDET</span>
          </div>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="flex flex-col lg:flex-row items-center gap-12 max-w-5xl w-full">
          {/* Left: Match Info */}
          <div className="flex-1 space-y-8 text-center lg:text-left">
            <div>
              <div className="flex items-center justify-center lg:justify-start gap-3 mb-2">
                <Target className="w-8 h-8 text-amber-500" />
                <h2 className="text-5xl font-heading font-bold uppercase text-white" data-testid="match-game-type">
                  {session?.game_type || 'DART'}
                </h2>
              </div>
            </div>

            {/* Players */}
            <div>
              <div className="flex items-center justify-center lg:justify-start gap-2 mb-3">
                <Users className="w-5 h-5 text-zinc-500" />
                <span className="text-sm text-zinc-500 uppercase tracking-wider">Spieler</span>
              </div>
              <div className="flex flex-wrap gap-3 justify-center lg:justify-start">
                {session?.players?.map((player, i) => (
                  <span
                    key={i}
                    className={`px-4 py-2 rounded-sm font-mono text-lg ${i === 0 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'bg-zinc-800 text-zinc-300 border border-zinc-700'}`}
                    data-testid={`match-player-${i}`}
                  >
                    {i === 0 && <Trophy className="w-4 h-4 inline mr-2" />}
                    {player}
                  </span>
                ))}
              </div>
            </div>

            {/* Share hint */}
            <div className="flex items-center justify-center lg:justify-start gap-2 text-zinc-500">
              <Share2 className="w-4 h-4" />
              <span className="text-sm">QR-Code scannen um das Ergebnis zu teilen</span>
            </div>
          </div>

          {/* Right: QR Code */}
          <div className="flex flex-col items-center gap-4">
            <div className="bg-white p-6 rounded-sm" data-testid="match-qr-code">
              <QRCodeSVG
                value={matchUrl}
                size={220}
                level="M"
                bgColor="#ffffff"
                fgColor="#000000"
              />
            </div>
            <p className="text-xs text-zinc-600 font-mono text-center max-w-[280px] break-all">
              {matchUrl}
            </p>
            <p className="text-sm text-zinc-500">24h gueltig</p>
          </div>
        </div>
      </div>

      {/* Footer: countdown */}
      <div className="p-4 border-t border-zinc-800 bg-zinc-950/80">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-zinc-600 uppercase tracking-wider flex items-center gap-1">
              <Clock className="w-3 h-3" /> Zurueck zum Startbildschirm in
            </span>
            <span className="text-sm font-mono text-zinc-400" data-testid="match-countdown">
              {secondsLeft}s
            </span>
          </div>
          <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-amber-500 transition-all duration-1000 ease-linear"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

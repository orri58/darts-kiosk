import { useRef, useEffect, useCallback, useState } from 'react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const SOUND_EVENTS = ['start', 'one_eighty', 'checkout', 'bust', 'win'];
const GLOBAL_MAX_PER_MIN = 30;

/**
 * Kiosk Sound Manager
 * - Preloads all sounds on mount
 * - Autoplay-unlock on first user touch/click
 * - Per-event rate limiting (configurable, default 1500ms)
 * - Global rate limiting (max 30 sounds/min)
 * - Quiet hours check
 * - Volume control
 */
export function useSoundManager(boardId) {
  const audioCtxRef = useRef(null);
  const buffersRef = useRef({});    // event -> AudioBuffer
  const lastPlayRef = useRef({});   // event -> timestamp
  const globalCountRef = useRef([]); // timestamps of recent plays
  const configRef = useRef(null);
  const unlockedRef = useRef(false);
  const [ready, setReady] = useState(false);

  // Fetch sound config
  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API}/settings/sound`);
      if (res.ok) {
        const cfg = await res.json();
        configRef.current = cfg;
        return cfg;
      }
    } catch { /* silent */ }
    return null;
  }, []);

  // Initialize AudioContext + preload sounds
  const initAudio = useCallback(async () => {
    if (audioCtxRef.current) return;

    const cfg = await fetchConfig();
    if (!cfg?.enabled) return;

    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    audioCtxRef.current = ctx;

    const pack = cfg.sound_pack || 'default';

    // Preload all sounds in parallel
    const loads = SOUND_EVENTS.map(async (event) => {
      try {
        const res = await fetch(`${API}/sounds/${pack}/${event}.wav`);
        if (res.ok) {
          const arrayBuf = await res.arrayBuffer();
          const audioBuf = await ctx.decodeAudioData(arrayBuf);
          buffersRef.current[event] = audioBuf;
        }
      } catch { /* silent */ }
    });

    await Promise.all(loads);
    setReady(true);
  }, [fetchConfig]);

  // Autoplay unlock on first user interaction
  useEffect(() => {
    const unlock = async () => {
      if (unlockedRef.current) return;
      unlockedRef.current = true;
      await initAudio();

      // Resume AudioContext if suspended (autoplay policy)
      if (audioCtxRef.current?.state === 'suspended') {
        await audioCtxRef.current.resume();
      }
    };

    // Listen for first touch/click/keydown
    const events = ['click', 'touchstart', 'keydown'];
    events.forEach((e) => document.addEventListener(e, unlock, { once: false, passive: true }));

    return () => {
      events.forEach((e) => document.removeEventListener(e, unlock));
    };
  }, [initAudio]);

  // Refresh config periodically (every 60s)
  useEffect(() => {
    const iv = setInterval(fetchConfig, 60000);
    return () => clearInterval(iv);
  }, [fetchConfig]);

  // Check quiet hours
  const isQuietHours = useCallback(() => {
    const cfg = configRef.current;
    if (!cfg?.quiet_hours_enabled) return false;

    const now = new Date();
    const hhmm = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const start = cfg.quiet_hours_start || '22:00';
    const end = cfg.quiet_hours_end || '08:00';

    // Handle overnight range (e.g. 22:00 - 08:00)
    if (start <= end) {
      return hhmm >= start && hhmm < end;
    }
    return hhmm >= start || hhmm < end;
  }, []);

  // Play a sound event with rate limiting
  const play = useCallback((event) => {
    const cfg = configRef.current;
    if (!cfg?.enabled) return;
    if (!audioCtxRef.current || !buffersRef.current[event]) return;
    if (isQuietHours()) return;

    const now = Date.now();
    const rateLimitMs = cfg.rate_limit_ms || 1500;

    // Per-event rate limit
    if (lastPlayRef.current[event] && now - lastPlayRef.current[event] < rateLimitMs) {
      return;
    }

    // Global rate limit (max 30/min)
    const oneMinAgo = now - 60000;
    globalCountRef.current = globalCountRef.current.filter((t) => t > oneMinAgo);
    if (globalCountRef.current.length >= GLOBAL_MAX_PER_MIN) {
      return;
    }

    // Play the sound
    try {
      const ctx = audioCtxRef.current;
      if (ctx.state === 'suspended') ctx.resume();

      const source = ctx.createBufferSource();
      source.buffer = buffersRef.current[event];

      const gainNode = ctx.createGain();
      gainNode.gain.value = Math.max(0, Math.min(1, (cfg.volume || 70) / 100));

      source.connect(gainNode);
      gainNode.connect(ctx.destination);
      source.start(0);

      lastPlayRef.current[event] = now;
      globalCountRef.current.push(now);
    } catch { /* silent */ }
  }, [isQuietHours]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
      }
    };
  }, []);

  return { play, ready, refetchConfig: fetchConfig };
}

"""
Synthetic Sound Generator for Kiosk Sound Effects
Generates short WAV files (<= 0.8s) using pure Python synthesis.
Called once on first startup, files cached in /data/assets/sounds/{pack}/.
"""
import wave
import struct
import math
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050  # Good enough for short UI sounds, small files
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit
MAX_AMP = 0.85  # Normalize volume

SOUND_EVENTS = ["start", "one_eighty", "checkout", "bust", "win"]


def _sin(freq, t, phase=0.0):
    return math.sin(2 * math.pi * freq * t + phase)


def _envelope(t, attack=0.02, decay=0.05, sustain_level=0.7, release=0.15, total=0.5):
    """ADSR envelope."""
    if t < attack:
        return t / attack
    elif t < attack + decay:
        return 1.0 - (1.0 - sustain_level) * ((t - attack) / decay)
    elif t < total - release:
        return sustain_level
    elif t < total:
        return sustain_level * (1.0 - (t - (total - release)) / release)
    return 0.0


def _write_wav(path: Path, samples: list[float], sample_rate: int = SAMPLE_RATE):
    """Write normalized float samples to a 16-bit mono WAV."""
    peak = max(abs(s) for s in samples) if samples else 1.0
    scale = MAX_AMP / peak if peak > 0 else 1.0

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        for s in samples:
            val = int(s * scale * 32767)
            val = max(-32768, min(32767, val))
            wf.writeframes(struct.pack("<h", val))


def _gen_start() -> list[float]:
    """Ascending two-tone chime: C5 → E5 (0.5s)."""
    duration = 0.5
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        # First tone C5 (523 Hz) fades, second tone E5 (659 Hz) fades in
        env1 = _envelope(t, attack=0.01, decay=0.1, sustain_level=0.4, release=0.15, total=0.3)
        env2 = _envelope(max(0, t - 0.15), attack=0.01, decay=0.1, sustain_level=0.5, release=0.2, total=0.35)
        s = _sin(523.25, t) * env1 * 0.6 + _sin(659.25, t) * env2 * 0.7
        # Subtle overtone
        s += _sin(1046.5, t) * env2 * 0.15
        samples.append(s)
    return samples


def _gen_one_eighty() -> list[float]:
    """Triumphant chord: C5+E5+G5 with shimmer (0.7s)."""
    duration = 0.7
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = _envelope(t, attack=0.01, decay=0.08, sustain_level=0.6, release=0.3, total=duration)
        s = (_sin(523.25, t) * 0.4 + _sin(659.25, t) * 0.35 +
             _sin(783.99, t) * 0.3 + _sin(1046.5, t) * 0.15)
        # Shimmer via slight vibrato
        s *= (1.0 + 0.03 * _sin(6.0, t))
        samples.append(s * env)
    return samples


def _gen_checkout() -> list[float]:
    """Clean high ping / ding (0.4s)."""
    duration = 0.4
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = _envelope(t, attack=0.005, decay=0.06, sustain_level=0.3, release=0.2, total=duration)
        # High bell-like tone A5 (880 Hz) with harmonics
        s = _sin(880, t) * 0.6 + _sin(1760, t) * 0.2 + _sin(2640, t) * 0.08
        samples.append(s * env)
    return samples


def _gen_bust() -> list[float]:
    """Low descending tone (0.5s) - subtle disappointment."""
    duration = 0.5
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = _envelope(t, attack=0.01, decay=0.1, sustain_level=0.4, release=0.2, total=duration)
        # Descending from G3 (196) to E3 (165)
        freq = 196.0 - (196.0 - 164.81) * (t / duration)
        s = _sin(freq, t) * 0.6 + _sin(freq * 2, t) * 0.15
        samples.append(s * env)
    return samples


def _gen_win() -> list[float]:
    """Ascending arpeggio: C5→E5→G5→C6 (0.8s)."""
    duration = 0.8
    n = int(SAMPLE_RATE * duration)
    notes = [(523.25, 0.0), (659.25, 0.15), (783.99, 0.30), (1046.5, 0.45)]
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        s = 0.0
        for freq, onset in notes:
            dt = t - onset
            if dt < 0:
                continue
            note_dur = duration - onset
            env = _envelope(dt, attack=0.01, decay=0.05, sustain_level=0.5, release=0.2, total=note_dur)
            s += _sin(freq, t) * env * 0.4
            s += _sin(freq * 2, t) * env * 0.1  # Overtone
        samples.append(s)
    return samples


_GENERATORS = {
    "start": _gen_start,
    "one_eighty": _gen_one_eighty,
    "checkout": _gen_checkout,
    "bust": _gen_bust,
    "win": _gen_win,
}


def ensure_sound_pack(base_dir: Path, pack: str = "default") -> Path:
    """Generate sound files if they don't exist. Returns pack directory."""
    pack_dir = base_dir / pack
    pack_dir.mkdir(parents=True, exist_ok=True)

    generated = False
    for event, gen_fn in _GENERATORS.items():
        fpath = pack_dir / f"{event}.wav"
        if not fpath.exists():
            logger.info(f"Generating sound: {pack}/{event}.wav")
            samples = gen_fn()
            _write_wav(fpath, samples)
            generated = True

    if generated:
        logger.info(f"Sound pack '{pack}' ready at {pack_dir}")
    return pack_dir


def list_sound_packs(base_dir: Path) -> list[dict]:
    """List available sound packs."""
    if not base_dir.exists():
        return []
    packs = []
    for d in sorted(base_dir.iterdir()):
        if d.is_dir():
            events = [f.stem for f in d.glob("*.wav") if f.stem in SOUND_EVENTS]
            packs.append({"id": d.name, "name": d.name.replace("_", " ").title(), "events": events})
    return packs

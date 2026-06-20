"""Shared Kokoro synthesis helpers used by both the server and the export CLI."""
import io
import os
import shutil
import subprocess
import tempfile
import threading

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAMPLE_RATE = 24000
# Resolve ffmpeg from PATH, falling back to the common Homebrew locations
# (a GUI-launched server may have a minimal PATH).
FFMPEG = shutil.which("ffmpeg") or next(
    (p for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg") if os.path.exists(p)),
    "ffmpeg",
)

_pipelines = {}
_lock = threading.Lock()  # Kokoro/torch isn't reliably thread-safe; serialize synth.


def get_pipeline(voice: str) -> KPipeline:
    code = "b" if voice[:1] == "b" else "a"  # b* = British, a* = American
    if code not in _pipelines:
        _pipelines[code] = KPipeline(lang_code=code)
    return _pipelines[code]


def synth_audio(text: str, voice: str, speed: float = 1.0) -> np.ndarray:
    with _lock:
        pipe = get_pipeline(voice)
        chunks = [audio for _, _, audio in pipe(text, voice=voice, speed=speed)]
    return np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)


def synth_wav_bytes(text: str, voice: str, speed: float = 1.0) -> bytes:
    audio = synth_audio(text, voice, speed)
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def synth_to_mp3(text: str, voice: str, out_path: str, speed: float = 1.0,
                 title: str | None = None, author: str = "Read Aloud") -> tuple[str, float]:
    """Synthesize `text` and encode to an MP3 with ID3 tags. Returns (path, seconds)."""
    audio = synth_audio(text, voice, speed)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    try:
        sf.write(wav_path, audio, SAMPLE_RATE, subtype="PCM_16")
        cmd = [FFMPEG, "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-qscale:a", "4"]
        if title:
            cmd += ["-metadata", f"title={title}"]
        cmd += ["-metadata", f"artist={author}", "-metadata", "album=Read Aloud", out_path]
        subprocess.run(cmd, check=True, capture_output=True)
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)
    return out_path, len(audio) / SAMPLE_RATE

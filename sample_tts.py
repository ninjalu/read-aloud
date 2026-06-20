"""Generate Kokoro TTS samples so we can judge the voice quality."""
import sys
import numpy as np
import soundfile as sf
from kokoro import KPipeline

TEXT = (
    "There is something quietly radical about being read to. "
    "For most of human history, stories arrived through the voice, not the page. "
    "If this sounds natural to you, then we have found the voice for your reading."
)

VOICES = sys.argv[1:] or ["af_heart", "am_michael"]
pipeline = KPipeline(lang_code="a")  # American English

for voice in VOICES:
    chunks = [audio for _, _, audio in pipeline(TEXT, voice=voice)]
    audio = np.concatenate(chunks)
    out = f"sample_{voice}.wav"
    sf.write(out, audio, 24000)
    print(f"wrote {out}  ({len(audio)/24000:.1f}s)")

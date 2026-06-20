import numpy as np, soundfile as sf
from kokoro import KPipeline
TEXT=("There is something quietly radical about being read to. "
"For most of human history, stories arrived through the voice, not the page. "
"If this sounds natural to you, then we have found the voice for your reading.")
pipe=KPipeline(lang_code="b")  # British English
for v in ["bf_emma","bf_isabella","bm_george","bm_lewis"]:
    a=np.concatenate([au for _,_,au in pipe(TEXT,voice=v)])
    sf.write(f"sample_{v}.wav",a,24000); print(f"wrote sample_{v}.wav ({len(a)/24000:.1f}s)")

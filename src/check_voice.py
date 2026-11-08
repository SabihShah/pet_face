import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

print("input device:", sd.query_devices(kind="input")["name"])
t = time.time()
model = WhisperModel("base.en", device="cpu", compute_type="int8")
print("model loaded in %.1fs" % (time.time() - t))
print("speak for 5 seconds...")
audio = sd.rec(int(5 * 16000), samplerate=16000, channels=1, dtype="float32")
sd.wait()
audio = audio[:, 0]
print("peak level: %.2f" % np.abs(audio).max())
t = time.time()
segs, _ = model.transcribe(audio, language="en", vad_filter=True)
text = " ".join(s.text.strip() for s in segs)
print("heard (%.1fs): %s" % (time.time() - t, text or "<nothing>"))

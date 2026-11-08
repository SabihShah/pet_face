import time, numpy as np, sounddevice as sd
from openwakeword.model import Model

m = Model(wakeword_models=["alexa"], inference_framework="onnx")

def phase(name, secs):
    print(f"\n== {name} ({secs}s) starting in 3s ==")
    time.sleep(3)
    print("GO")
    hits, last = {0.5: 0, 0.7: 0}, {0.5: -9.0, 0.7: -9.0}
    t0 = time.time()
    with sd.InputStream(samplerate=16000, channels=1, blocksize=1280, dtype="int16") as s:
        while time.time() - t0 < secs:
            x, _ = s.read(1280)
            v = max(m.predict(x[:, 0]).values())
            now = time.time() - t0
            for th in hits:
                if v > th and now - last[th] > 1.5:
                    hits[th] += 1
                    last[th] = now
                    print(f"  t={now:.1f}s th={th} score={v:.2f}")
    print(f"events={hits}")

phase("SAY 'alexa' 8 times, ~2 s apart", 25)
phase("TALK normally, never say the wake word", 25)
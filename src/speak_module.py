import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root (models/ lives there)
import io, json, socket, sys, time, wave
import numpy as np, sounddevice as sd
from piper import PiperVoice

voice = PiperVoice.load(os.path.join(ROOT, "models/tts/en_US-lessac-medium.onnx"))
out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send(**m):
    out.sendto(json.dumps(m).encode(), ("127.0.0.1", 5005))

def mute(on):
    out.sendto(json.dumps({"mute": on}).encode(), ("127.0.0.1", 5007))

def say(text, emotion=None):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        voice.synthesize_wav(text, w)
    buf.seek(0)
    with wave.open(buf) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = sr // 30
    env = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x), hop)])
    env = np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1)
    if emotion:
        send(cmd="emotion", value=emotion)
    mute(True)
    time.sleep(0.05)
    sd.play(x, sr)
    t0 = time.time()
    while (i := int((time.time() - t0) * 30)) < len(env):
        send(cmd="level", value=float(env[i]))
        time.sleep(1 / 30)
    sd.wait()
    send(cmd="level", value=0.0)
    mute(False)
    if emotion:
        time.sleep(1.0)
        send(cmd="emotion", value="neutral")

if len(sys.argv) > 1:
    say(" ".join(sys.argv[1:]))
else:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 5006))
    print("speak_module listening on 5006")
    while True:
        data, _ = sock.recvfrom(8192)
        try:
            msg = json.loads(data.decode())
        except ValueError:
            continue
        if isinstance(msg, dict) and msg.get("say"):
            say(str(msg["say"]), msg.get("emotion"))

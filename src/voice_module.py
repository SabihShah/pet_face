import argparse, collections, json, queue, socket, threading, time
import numpy as np, sounddevice as sd
from faster_whisper import WhisperModel
from openwakeword.model import Model
from voice_cmd import parse_cmd

SR, BLK = 16000, 1280  # 80 ms blocks, what openWakeWord expects

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="base.en")
ap.add_argument("--device", default=None)
ap.add_argument("--wake", default="alexa")
ap.add_argument("--wake-th", type=float, default=0.7)
ap.add_argument("--window", type=float, default=10.0)   # listen window after wake / after each reply
ap.add_argument("--silence", type=float, default=0.8)
ap.add_argument("--thresh", type=float, default=3.0)   # x noise floor
a = ap.parse_args()
dev = int(a.device) if a.device and a.device.isdigit() else a.device

_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
def send(**m):
    _sock.sendto(json.dumps(m).encode(), ("127.0.0.1", 5005))

TAIL = 0.8          # keep muted this long after the robot stops (room echo)
mute = {"start": None, "ivals": []}

def _mute_loop():
    ms = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ms.bind(("127.0.0.1", 5007))
    while True:
        d, _ = ms.recvfrom(1024)
        try:
            on = bool(json.loads(d.decode()).get("mute"))
        except ValueError:
            continue
        now = time.time()
        if on:
            if mute["start"] is None:
                mute["start"] = now
        elif mute["start"] is not None:
            mute["ivals"] = (mute["ivals"] + [(mute["start"], now + TAIL)])[-20:]
            mute["start"] = None

def is_muted(t0, t1):
    if mute["start"] is not None and t1 > mute["start"]:
        return True
    return any(t1 > s and t0 < e for s, e in mute["ivals"])

threading.Thread(target=_mute_loop, daemon=True).start()

stt = WhisperModel(a.model, device="cpu", compute_type="int8")
oww = Model(wakeword_models=[a.wake], inference_framework="onnx")
q = queue.Queue()
def cb(indata, frames, t, status):
    q.put((time.time(), indata[:, 0].copy()))
rms = lambda x: float(np.sqrt(np.mean((x / 32768.0) ** 2)) + 1e-9)

with sd.InputStream(samplerate=SR, channels=1, blocksize=BLK,
                    dtype="int16", device=dev, callback=cb):
    print("calibrating (stay quiet 1 s)...")
    [q.get() for _ in range(6)]  # drop startup transient
    floor = float(np.median([rms(q.get()[1]) for _ in range(13)]))
    print(f"floor={floor:.4f}  say '{a.wake}'")
    clk = 0.0                     # audio clock (immune to transcription backlog)
    state, deadline, skip, last_wake = "idle", 0.0, 0.0, -9.0
    pre = collections.deque(maxlen=4)
    buf, speaking, last_voice, t0 = [], False, 0.0, 0.0
    while True:
        tb, blk = q.get()
        clk += BLK / SR
        if is_muted(tb - BLK / SR - 0.15, tb):
            buf, speaking = [], False
            pre.clear()
            oww.reset()
            deadline = clk + a.window
            state = "listening"
            continue
        r = rms(blk)
        voiced = r > max(floor * a.thresh, 0.01) and clk > skip
        if r < floor:
            floor = 0.9 * floor + 0.1 * r
        elif not speaking and r < floor * 1.5:
            floor = 0.999 * floor + 0.001 * r

        if state == "idle":
            if max(oww.predict(blk).values()) > a.wake_th and clk - last_wake > 1.5:
                last_wake = clk
                state, deadline, skip = "listening", clk + a.window, clk + 0.4
                buf, speaking = [], False
                pre.clear()
                print("WAKE")
                send(event="wake")
            continue

        if not speaking:
            pre.append(blk)
            if voiced:
                speaking, t0, last_voice = True, clk, clk
                buf = list(pre)
            elif clk > deadline:
                state = "idle"
                oww.reset()
                print("idle")
                send(event="voice_idle")
            continue

        buf.append(blk)
        if voiced:
            last_voice = clk
            deadline = max(deadline, clk + 2.0)
        if clk - last_voice > a.silence or clk - t0 > 15:
            speaking = False
            if last_voice - t0 >= 0.3:
                audio = np.concatenate(buf).astype(np.float32) / 32768.0
                t1 = time.time()
                segs, _ = stt.transcribe(audio, language="en", beam_size=1, vad_filter=True)
                text = " ".join(s.text.strip() for s in segs).strip()
                if text:
                    print(f"[{time.time()-t1:.1f}s] {text}")
                    send(event="speech", text=text)
                    cmd = parse_cmd(text)
                    if cmd:
                        print("CMD", cmd)
                        _sock.sendto(json.dumps({"voice_cmd": cmd}).encode(), ("127.0.0.1", 5009))
                    else:
                        _sock.sendto(json.dumps({"text": text}).encode(), ("127.0.0.1", 5008))
            buf = []
            pre.clear()
            deadline = clk + a.window   # follow-up allowed without the wake word

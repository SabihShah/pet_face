# Pet Face

An animated desk-pet robot with an expressive screen face, voice AI, camera-based perception, and movement control. The robot sees you, listens to you, talks back, and reacts emotionally in real time.

## Features

- **Animated face** — 20+ emotions rendered with Pygame (happy, sad, angry, surprised, sleepy, love, and more)
- **AI brain** — Conversational responses powered by a local LLM (Qwen 2.5 via Ollama), with persistent memory of facts about you
- **Voice I/O** — Wake-word detection (OpenWakeWord), speech-to-text (faster-whisper), and text-to-speech (Piper TTS)
- **Camera perception** — Face detection, facial emotion recognition (HSEmotion), and hand gesture recognition (MediaPipe: wave, thumbs up/down)
- **Voice commands** — Natural language movement commands parsed into structured actions (go forward 2 meters, turn left 90 degrees, stop, etc.)
- **Mood system** — Long-term happiness state that drifts based on interactions and time away
- **Animated hands** — Greeting wave and thumbs-up gestures rendered alongside the face

## Architecture

All modules communicate over UDP on localhost. Each process is independent and can be run separately.

```
                  ┌─────────────┐
                  │   app.py    │  Pygame display (face + hands)
                  └──────┬──────┘
                         │ UDP :5005
          ┌──────────────┼──────────────────┐
          │              │                  │
   ┌──────┴──────┐ ┌─────┴──────┐  ┌───────┴──────┐
   │voice_module │ │camera_module│  │ brain_module │
   │  :5005 out  │ │  :5005 out  │  │  :5008 in    │
   └──────┬──────┘ └────────────┘  └───────┬──────┘
          │                                │
          │ speech text → :5008            │ reply → :5006
          │ voice_cmd  → :5009     ┌───────┴──────┐
          │                        │ speak_module │
          │ mute signal ← :5007    │  :5006 in    │
          └────────────────────────┘
```

| Port | Direction | Purpose |
|------|-----------|---------|
| 5005 | → app.py  | Events: gaze, person_arrived/left, emotion, gesture, speech |
| 5006 | → speak   | TTS: `{"say": "...", "emotion": "..."}` |
| 5007 | ↔ voice   | Mute signal during TTS playback |
| 5008 | → brain   | STT text for LLM |
| 5009 | → app.py  | Parsed voice movement commands |
| 5010 | → head    | Head movement actions (nod, shake, greet) |

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally with `qwen2.5:3b` pulled
- A webcam
- A microphone and speaker

### Python dependencies

```bash
pip install pygame numpy sounddevice faster-whisper openwakeword piper-tts \
            opencv-python mediapipe hsemotion-onnx
```

### Models

Place the following model files under `models/`:

| Path | Source |
|------|--------|
| `models/face_detection_yunet_2023mar.onnx` | OpenCV Zoo |
| `models/gesture_recognizer.task` | MediaPipe |
| `models/tts/en_US-lessac-medium.onnx` + `.json` | Piper TTS releases |

## Usage

### Quick start (all modules, one terminal)

```bash
./run.sh              # start brain, speak, app, camera, voice; stream logs; Ctrl+C stops all
./run.sh --no-tail    # start without streaming logs
./run.sh stop         # stop from another terminal
```

`run.sh` strips ROS from the environment, checks Ollama, sets the mic input volume
(`MIC_VOLUME`, default 0.15), and writes each module's output to `logs/<module>.log`.
Options: `CAM=0`, `WHISPER_MODEL=base.en`, `VOICE_ARGS="--wake-th 0.5"`, `CAMERA_ARGS="--no-preview"`.

### Manual start

Start each module in a separate terminal:

```bash
# 1. Start the Ollama LLM server (in its own process)
ollama serve

# 2. AI brain (LLM + memory)
python src/brain_module.py

# 3. Text-to-speech
python src/speak_module.py

# 4. Camera (face detection + gesture recognition)
python src/camera_module.py

# 5. Voice (wake word + STT)
python src/voice_module.py

# 6. Animated face display
python src/app.py
```

### Keyboard shortcuts (app.py)

| Key | Action |
|-----|--------|
| `1`–`6` | Set emotion: neutral, happy, sad, angry, surprised, sleepy |
| `T` | Toggle talking animation |
| `H` | Trigger greeting wave |
| `F` | Toggle fullscreen |
| `Esc` | Quit |

### Voice module options

```
python src/voice_module.py --model base.en --wake alexa --wake-th 0.7 --window 10 --silence 0.8
```

### Camera options

```
python src/camera_module.py --cam 1 --no-preview --no-hands
```

## Voice Commands

The robot understands natural movement commands after the wake word:

| Command | Action |
|---------|--------|
| "Go forward two meters" | `{"action": "forward", "dist": 2.0}` |
| "Turn left 90 degrees" | `{"action": "left", "angle": 90}` |
| "Turn around" | `{"action": "right", "angle": 180}` |
| "Go back" | `{"action": "back"}` |
| "Stop" | `{"action": "stop"}` |
| "Keep going forward" | `{"action": "forward", "continuous": true}` |

## Memory

The brain module extracts and persists facts about you (name, hobbies, family, plans) in `facts.json`. You can explicitly ask it to remember or forget things:

- *"Remember that my sister's name is Ayesha"*
- *"Forget my favorite color"*

Mood state (happiness level, time away) is stored in `mood.json`.

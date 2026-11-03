import argparse
import collections
import json
import socket
import time
import urllib.request  # noqa: hsemotion-onnx forgets this import
import cv2
import pygame
import mediapipe as mp
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision
from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

MODEL = "models/face_detection_yunet_2023mar.onnx"
ADDR = ("127.0.0.1", 5005)
EMO_EVERY = 0.2
WINDOW = 6
ARRIVE_FRAMES = 4
LEAVE_AFTER = 2.0
GESTURE_EVERY = 0.1
WAVE_COOLDOWN = 4.0
HAND_LINKS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11),
              (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)]
LABELS = {"Happiness": "happy", "Sadness": "sad", "Anger": "angry", "Surprise": "surprised",
          "Fear": "fear", "Disgust": "disgust", "Contempt": "contempt", "Neutral": "neutral"}

GZ = {"x": 0.0, "y": 0.0, "t": 0.0}
GAZE_FLIP = 1   # 1: eyes look toward the person; set to 1 if they look away
GAZE_GAIN = 1.5

def is_wave(hist, now, x):
    if x is None:
        hist.clear()
        return False
    hist.append((now, x))
    while hist and now - hist[0][0] > 1.5:
        hist.popleft()
    if len(hist) < 6:
        return False
    rev, direction, anchor = 0, 0, hist[0][1]
    for _, v in list(hist)[1:]:
        d = v - anchor
        if abs(d) > 0.04:
            nd = 1 if d > 0 else -1
            if direction and nd != direction:
                rev += 1
            direction = nd
            anchor = v
    return rev >= 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=1)
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--no-hands", action="store_true")
    args = ap.parse_args()

    det = cv2.FaceDetectorYN.create(MODEL, "", (320, 320), 0.8, 0.3, 5000)
    fer = HSEmotionRecognizer(model_name="enet_b0_8_best_afew")
    rec = None
    if not args.no_hands:
        rec = vision.GestureRecognizer.create_from_options(vision.GestureRecognizerOptions(
            base_options=mpp.BaseOptions(model_asset_path="models/gesture_recognizer.task"),
            running_mode=vision.RunningMode.VIDEO, num_hands=1))
    cap = cv2.VideoCapture(args.cam)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise SystemExit("camera not available")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    screen = None

    def send(msg):
        sock.sendto(json.dumps(msg).encode(), ADDR)

    votes = collections.deque(maxlen=WINDOW)
    present, seen, last_seen, last_emo = False, 0, 0.0, 0.0
    smooth, raw, conf = None, None, 0.0
    g_hist, g_stable, last_g, last_wave = collections.deque(maxlen=4), "none", 0.0, 0.0
    wave_hist, t_start = collections.deque(), time.time()
    hand_pts = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        det.setInputSize((w, h))
        _, faces = det.detect(frame)
        now = time.time()
        box = None
        if faces is not None and len(faces):
            f = max(faces, key=lambda r: r[2] * r[3])
            x, y = max(0, int(f[0])), max(0, int(f[1]))
            fw, fh = min(int(f[2]), w - x), min(int(f[3]), h - y)
            if fw > 20 and fh > 20:
                box = (x, y, fw, fh)
        if box:
            gx = ((box[0] + box[2] / 2) / w - 0.5) * 2
            gy = ((box[1] + box[3] / 2) / h - 0.5) * 2
            GZ["x"] += (gx - GZ["x"]) * 0.4
            GZ["y"] += (gy - GZ["y"]) * 0.4
            if time.time() - GZ["t"] > 0.07:
                GZ["t"] = time.time()
                send({"event": "gaze", "x": round(GAZE_FLIP * GAZE_GAIN * GZ["x"], 3),
                      "y": round(GAZE_GAIN * GZ["y"], 3)})
            seen += 1
            last_seen = now
            if not present and seen >= ARRIVE_FRAMES:
                present = True
                send({"event": "person_arrived"})
                print("person_arrived")
            if now - last_emo >= EMO_EVERY:
                last_emo = now
                x, y, fw, fh = box
                crop = cv2.cvtColor(frame[y:y + fh, x:x + fw], cv2.COLOR_BGR2RGB)
                label, _ = fer.predict_emotions(crop, logits=False)
                raw = LABELS.get(label, label.lower())
                votes.append(raw)
                top, n = collections.Counter(votes).most_common(1)[0]
                conf = n / len(votes)
                if len(votes) >= 3 and conf >= 0.5 and top != smooth:
                    smooth = top
                    send({"event": "person_emotion", "value": smooth, "conf": round(conf, 2)})
                    print("person_emotion", smooth, round(conf, 2))
        else:
            seen = 0
            if present and now - last_seen > LEAVE_AFTER:
                present, smooth = False, None
                votes.clear()
                send({"event": "person_left"})
                print("person_left")
        if rec and now - last_g >= GESTURE_EVERY:
            last_g = now
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            res = rec.recognize_for_video(img, int((now - t_start) * 1000))
            name, palm_x, hand_pts = "none", None, None
            if res.gestures:
                name = res.gestures[0][0].category_name
                palm_x = res.hand_landmarks[0][9].x
                hand_pts = [(int(p.x * w), int(p.y * h)) for p in res.hand_landmarks[0]]
            g_hist.append(name)
            if len(g_hist) == g_hist.maxlen and len(set(g_hist)) == 1 and g_hist[0] != g_stable:
                g_stable = g_hist[0]
                ev = {"Thumb_Up": "thumb_up", "Thumb_Down": "thumb_down"}.get(g_stable)
                if ev:
                    send({"event": "gesture", "value": ev})
                    print("gesture", ev)
            if is_wave(wave_hist, now, palm_x if name == "Open_Palm" else None) and now - last_wave > WAVE_COOLDOWN:
                last_wave = now
                wave_hist.clear()
                send({"event": "gesture", "value": "wave"})
                print("gesture wave")
        if not args.no_preview:
            if box:
                x, y, fw, fh = box
                cv2.rectangle(frame, (x, y), (x + fw, y + fh), (255, 220, 70), 2)
                cv2.putText(frame, "%s %d%%" % (smooth or "...", conf * 100), (x, max(20, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 220, 70), 2)
                cv2.putText(frame, "raw: %s" % raw, (x, y + fh + 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            else:
                cv2.putText(frame, "no face", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (80, 80, 255), 2)
            cv2.putText(frame, "hand: %s" % g_stable, (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (120, 255, 120), 2)
            if hand_pts:
                xs, ys = [p[0] for p in hand_pts], [p[1] for p in hand_pts]
                cv2.rectangle(frame, (min(xs) - 12, min(ys) - 12), (max(xs) + 12, max(ys) + 12), (120, 255, 120), 2)
                for a, b in HAND_LINKS:
                    cv2.line(frame, hand_pts[a], hand_pts[b], (255, 255, 255), 1)
                for p in hand_pts:
                    cv2.circle(frame, p, 3, (0, 140, 255), -1)
                cv2.putText(frame, g_stable, (min(xs) - 12, max(0, min(ys) - 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (120, 255, 120), 2)
            if screen is None:
                pygame.init()
                pygame.display.set_caption("camera")
                screen = pygame.display.set_mode((w, h))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            screen.blit(pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB"), (0, 0))
            pygame.display.flip()
            stop = False
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_q)):
                    stop = True
            if stop:
                break
    cap.release()
    pygame.quit()


if __name__ == "__main__":
    main()

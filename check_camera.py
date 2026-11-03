import urllib.request
import time
import cv2
from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

det = cv2.FaceDetectorYN.create("models/face_detection_yunet_2023mar.onnx", "", (320, 320), 0.8, 0.3, 5000)
fer = HSEmotionRecognizer(model_name="enet_b0_8_best_afew")
cap = cv2.VideoCapture(1)
ok, frame = cap.read()
print("camera ok:", ok, frame.shape if ok else None)
t0, n = time.time(), 0
while ok and time.time() - t0 < 5:
    ok, frame = cap.read()
    if not ok:
        break
    h, w = frame.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(frame)
    if faces is None:
        continue
    x, y, fw, fh = [max(0, int(v)) for v in faces[0][:4]]
    crop = frame[y:y + fh, x:x + fw]
    if crop.size == 0:
        continue
    emo, _ = fer.predict_emotions(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB), logits=False)
    n += 1
    print(emo)
print("predictions:", n)
cap.release()

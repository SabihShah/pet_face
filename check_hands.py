import time
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision

opts = vision.GestureRecognizerOptions(
    base_options=mpp.BaseOptions(model_asset_path="models/gesture_recognizer.task"),
    running_mode=vision.RunningMode.VIDEO, num_hands=1)
rec = vision.GestureRecognizer.create_from_options(opts)
cap = cv2.VideoCapture(1)
t0, last = time.time(), None
while time.time() - t0 < 8:
    ok, frame = cap.read()
    if not ok:
        break
    img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    res = rec.recognize_for_video(img, int((time.time() - t0) * 1000))
    g = res.gestures[0][0].category_name if res.gestures else "no hand"
    if g != last:
        print(g)
        last = g
cap.release()

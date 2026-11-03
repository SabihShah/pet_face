import re
from mood import Mood

MAP = {"happy": "happy", "angry": "sad", "sad": "sad", "surprised": "surprised",
       "fear": "surprised", "neutral": "neutral", "disgust": "neutral", "contempt": "neutral"}
MIN_HOLD = 1.5
PHYS = {"pick_up": ("surprised", 2.5), "tilt": ("worried", 2.0), "shake": ("dizzy", 3.0),
        "cliff": ("cliff", 3.0), "bump_near": ("surprised", 1.5)}
HOLD_MAX = 15.0
LEAVE_HOLD = 1.5
WAKE_HOLD = 0.8
VOICE_MAX = 12.0
IDLE_SLEEPY = 120.0
CAM_EVENTS = {"person_arrived", "person_left", "person_emotion", "gesture"}
INTERACT = {"wake", "speech", "person_arrived", "gesture"}
GREET_W = {"hi", "hello", "hey", "hiya", "greetings"}
PRAISE_W = {"good", "great", "awesome", "love", "thanks", "thank", "amazing",
            "wonderful", "nice", "cute", "smart", "best", "happy", "perfect"}
SAD_W = {"sad", "died", "lost", "miss", "cry", "crying", "terrible", "awful",
         "bad", "sorry", "lonely", "hurt", "sick"}


class Behavior:
    def __init__(self):
        self.emotion = "neutral"
        self.set_at = 0.0
        self.pending = None
        self.leave_at = None
        self.voice_until = 0.0
        self.last = None
        self.present = False
        self._changed = False
        self.mood = Mood()

    def _apply(self, e, now):
        if e != self.emotion:
            self.emotion, self.set_at, self._changed = e, now, True

    def handle(self, m, now):
        ev = m.get("event")
        missed = ev in INTERACT and self.mood.interact(now)
        if ev == "speech":
            w = set(re.findall(r"[a-z']+", str(m.get("text", "")).lower()))
            self.mood.bump(0.05 + 0.12 * len(w & PRAISE_W) - 0.04 * len(w & SAD_W))
        elif ev == "gesture":
            self.mood.bump({"thumb_up": 0.2, "thumb_down": -0.3, "wave": 0.1}.get(m.get("value"), 0.0))
        elif ev == "person_emotion":
            self.mood.touch(now)
        elif ev == "touch":
            self.mood.touch(now)
            self.mood.bump(0.15)
        elif ev in PHYS:
            self.mood.touch(now)
        r = self._handle(m, now)
        if missed:
            self.pending, self.leave_at = None, None
            self._apply("love", now)
            return "missed"
        return r

    def _handle(self, m, now):
        ev = m.get("event")
        if ev:
            self.last = now
            if ev in ("person_arrived", "person_emotion"):
                self.present = True
            elif ev == "person_left":
                self.present = False
            if self.emotion == "sleepy":
                self._apply("neutral", now)
        if ev in ("wake", "speech"):
            self.voice_until = now + VOICE_MAX
        elif ev == "voice_idle":
            self.voice_until = 0.0
            return None
        elif ev in CAM_EVENTS and now < self.voice_until:
            return None
        if ev == "person_arrived":
            self.leave_at = None
            return "greet"
        if ev == "person_left":
            self.pending = None
            self.leave_at = now + LEAVE_HOLD
        elif ev == "person_emotion":
            self.leave_at = None
            target = MAP.get(str(m.get("value")), "neutral")
            if now - self.set_at >= MIN_HOLD:
                self._apply(target, now)
                self.pending = None
            else:
                self.pending = target
        elif ev == "gesture":
            g = m.get("value")
            if g == "wave":
                return "greet"
            if g == "thumb_up":
                return "thumb_up"
            if g == "thumb_down":
                self.pending = None
                self.leave_at = None
                self._apply("sad", now)
        elif ev == "touch":
            self.pending = None
            self._apply("content", now)
            self.leave_at = now + 3.0
        elif ev in PHYS:
            self.pending = None
            self._apply(PHYS[ev][0], now)
            self.leave_at = now + PHYS[ev][1]
        elif ev == "wake":
            self.pending = None
            self._apply("surprised", now)
            self.leave_at = now + WAKE_HOLD
        elif ev == "speech":
            w = set(re.findall(r"[a-z']+", str(m.get("text", "")).lower()))
            self.pending = None
            self.leave_at = None
            if w & GREET_W:
                return "greet"
            pos, neg = len(w & PRAISE_W), len(w & SAD_W)
            if pos > neg:
                self._apply("happy", now)
            elif neg > pos:
                self._apply("sad", now)
        return None

    def update(self, now):
        self.mood.update(now)
        if self.leave_at is not None and now >= self.leave_at:
            self.leave_at = None
            self._apply("neutral", now)
        if self.pending is not None and now - self.set_at >= MIN_HOLD:
            self._apply(self.pending, now)
            self.pending = None
        elif self.emotion not in ("neutral", "sleepy") and now - self.set_at > HOLD_MAX:
            self._apply("neutral", now)
        if self.last is None:
            self.last = now
        if (self.emotion != "sleepy" and not self.present and now >= self.voice_until
                and now - self.last >= IDLE_SLEEPY):
            self._apply("sleepy", now)
        if self._changed:
            self._changed = False
            return self.emotion
        return None

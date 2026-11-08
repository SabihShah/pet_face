import math
import random
import pygame

BG = (10, 12, 18)
FG = (70, 220, 255)
MOUTH_FILL = (20, 70, 90)
PINK = (255, 90, 140)
TEAR = (110, 190, 255)

PRESETS = {
    "neutral":      dict(ew=1.0,  eh=1.0,  cover=0.0,  tilt=0.0,  lower=0.0, curve=0.15, open=0.0),
    "happy":        dict(ew=1.0,  eh=1.0,  cover=0.0,  tilt=0.0,  lower=0.9, curve=0.9,  open=0.0),
    "sad":          dict(ew=1.0,  eh=0.9,  cover=0.25, tilt=-0.8, lower=0.0, curve=-0.8, open=0.0),
    "angry":        dict(ew=1.0,  eh=0.9,  cover=0.30, tilt=0.9,  lower=0.0, curve=-0.4, open=0.0),
    "surprised":    dict(ew=0.8,  eh=1.3,  cover=0.0,  tilt=0.0,  lower=0.0, curve=0.0,  open=0.8),
    "sleepy":       dict(ew=1.0,  eh=0.7,  cover=0.5,  tilt=0.0,  lower=0.0, curve=0.1,  open=0.0),
    "excited":      dict(ew=1.05, eh=1.15, cover=0.0,  tilt=0.0,  lower=0.6, curve=1.0,  open=0.5),
    "laughing":     dict(ew=1.05, eh=0.8,  cover=0.0,  tilt=0.0,  lower=1.0, curve=1.0,  open=1.0),
    "proud":        dict(ew=1.0,  eh=0.95, cover=0.15, tilt=0.0,  lower=0.7, curve=0.7,  open=0.0),
    "shy":          dict(ew=0.95, eh=0.9,  cover=0.1,  tilt=-0.4, lower=0.5, curve=0.4,  open=0.0),
    "smug":         dict(ew=1.0,  eh=0.85, cover=0.3,  tilt=0.2,  lower=0.3, curve=0.6,  open=0.0),
    "curious":      dict(ew=0.9,  eh=1.2,  cover=0.0,  tilt=0.0,  lower=0.0, curve=0.2,  open=0.15),
    "worried":      dict(ew=0.95, eh=1.0,  cover=0.15, tilt=-1.0, lower=0.0, curve=-0.3, open=0.0),
    "scared":       dict(ew=0.8,  eh=1.35, cover=0.0,  tilt=-0.5, lower=0.0, curve=-0.3, open=0.5),
    "annoyed":      dict(ew=1.0,  eh=0.8,  cover=0.4,  tilt=0.4,  lower=0.0, curve=-0.2, open=0.0),
    "bored":        dict(ew=1.0,  eh=0.75, cover=0.45, tilt=0.0,  lower=0.0, curve=-0.05, open=0.0),
    "disappointed": dict(ew=1.0,  eh=0.85, cover=0.35, tilt=-0.5, lower=0.0, curve=-0.6, open=0.0),
    # special-draw emotions (base shape here, extra drawing in Face.draw)
    "love":         dict(ew=1.0,  eh=1.0,  cover=0.0,  tilt=0.0,  lower=0.0, curve=0.9,  open=0.0),
    "crying":       dict(ew=1.0,  eh=0.9,  cover=0.25, tilt=-0.8, lower=0.0, curve=-0.9, open=0.3),
    "thinking":     dict(ew=0.95, eh=1.0,  cover=0.0,  tilt=0.0,  lower=0.0, curve=-0.05, open=0.0),    
    "wink":         dict(ew=1.0,  eh=1.0,  cover=0.0,  tilt=0.0,  lower=0.5, curve=0.9,  open=0.0),
    "confused":     dict(ew=1.0,  eh=1.0,  cover=0.15, tilt=-0.3, lower=0.0, curve=-0.1, open=0.0),
    "dizzy":        dict(ew=1.0,  eh=1.0,  cover=0.0,  tilt=0.0,  lower=0.0, curve=0.0,  open=0.2),
}
PRESETS["content"] = dict(ew=1.0, eh=1.0, cover=0.0, tilt=0.0, lower=0.0, curve=0.7, open=0.0)
PRESETS["cliff"] = dict(PRESETS["scared"])
FX = {"love", "crying", "thinking", "wink", "confused", "dizzy", "content", "cliff"}


def draw_heart(s, cx, cy, size, col):
    pts = []
    for i in range(40):
        a = 2 * math.pi * i / 40
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x * size / 32, cy + size * 0.05 + y * size / 32))
    pygame.draw.polygon(s, col, pts)


def draw_spiral(s, cx, cy, r, t, col, width):
    pts = []
    for i in range(60):
        a = i * 0.35 + t * 6
        rr = r * i / 60
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    pygame.draw.lines(s, col, False, pts, width)


class Face:
    def __init__(self):
        self.cur = dict(PRESETS["neutral"])
        self.tgt = dict(PRESETS["neutral"])
        self.emotion = "neutral"
        self.fx = None
        self.talk = 0.0
        self.t = 0.0
        self.blink_t = -1.0
        self.next_blink = 2.0
        self.gaze = [0.0, 0.0]
        self.gaze_tgt = [0.0, 0.0]
        self.next_gaze = 1.0
        self.track = [0.0, 0.0]
        self.track_t = -9.0
        self.yawn_t = -1.0
        self.next_yawn = 0.0

    def set_emotion(self, name):
        if name in PRESETS:
            if name == "sleepy" and self.emotion != "sleepy":
                self.next_yawn = self.t + random.uniform(4.0, 8.0)
            self.emotion = name
            self.fx = name if name in FX else None
            self.tgt = dict(PRESETS[name])

    def look_at(self, x, y):
        self.track = [max(-1.8, min(1.8, x * 1.8)), max(-1.2, min(1.2, y * 1.8))]
        self.track_t = self.t

    def update(self, dt):
        self.t += dt
        k = min(1.0, dt * 10.0)
        for key in self.cur:
            self.cur[key] += (self.tgt[key] - self.cur[key]) * k
        if self.blink_t < 0 and self.t > self.next_blink:
            self.blink_t = 0.0
        if self.blink_t >= 0:
            self.blink_t += dt
            if self.blink_t > 0.18:
                self.blink_t = -1.0
                self.next_blink = self.t + random.uniform(2.0, 6.0)
        if self.fx == "thinking":
            self.gaze_tgt = [0.9, -0.8]
        elif self.t - self.track_t < 0.6:
            self.gaze_tgt = list(self.track)
        elif self.t > self.next_gaze:
            a = 0.3 if self.emotion == "sleepy" else 1.0
            self.gaze_tgt = [a * random.uniform(-1, 1), a * random.uniform(-0.6, 0.6)]
            self.next_gaze = self.t + random.uniform(1.5, 4.0)
        if self.yawn_t >= 0:
            self.yawn_t += dt
            if self.yawn_t > 2.6:
                self.yawn_t = -1.0
                self.next_yawn = self.t + random.uniform(12.0, 25.0)
        elif self.emotion == "sleepy" and self.t > self.next_yawn:
            self.yawn_t = 0.0
        g = min(1.0, dt * 6.0)
        for i in range(2):
            self.gaze[i] += (self.gaze_tgt[i] - self.gaze[i]) * g

    def draw(self, s):
        w, h = s.get_size()
        s.fill(BG)
        c = self.cur
        fx = self.fx
        b = math.sin(math.pi * self.blink_t / 0.18) if self.blink_t >= 0 else 0.0
        ye = math.sin(math.pi * self.yawn_t / 2.6) if self.yawn_t >= 0 else 0.0
        b = max(b, ye)
        breathe = 1.0 + 0.015 * math.sin(self.t * 2.0)
        ew = w * 0.17 * c["ew"]
        eh = h * 0.36 * c["eh"] * breathe * (1.0 - 0.92 * b)
        gk = 2.5 if fx == "thinking" else 1.0
        gx = self.gaze[0] * w * 0.02 * gk
        gy = self.gaze[1] * h * 0.03 * gk

        for side in (-1, 1):
            cx = w * 0.5 + side * w * 0.22 + gx
            cy = h * 0.40 + gy

            if fx == "love":
                draw_heart(s, cx, cy, ew * 1.25 * (1.0 + 0.1 * math.sin(self.t * 6.0)), PINK)
                continue
            if fx == "dizzy":
                draw_spiral(s, cx, cy, ew * 0.5, self.t * (1 if side == 1 else -1), FG, max(3, int(h * 0.015)))
                continue
            if fx == "content":
                r2 = pygame.Rect(0, 0, int(ew * 0.9), int(h * 0.2))
                r2.center = (int(cx), int(cy))
                pygame.draw.arc(s, FG, r2, 0.25, math.pi - 0.25, max(4, int(h * 0.03)))
                pygame.draw.ellipse(s, (150, 55, 95), pygame.Rect(int(cx - ew * 0.3), int(cy + h * 0.1), int(ew * 0.6), int(h * 0.07)))
                continue
            if fx == "wink" and side == 1:
                r2 = pygame.Rect(0, 0, int(ew), int(h * 0.2))
                r2.center = (int(cx), int(cy))
                pygame.draw.arc(s, FG, r2, 0.25, math.pi - 0.25, max(4, int(h * 0.03)))
                continue

            ehs = eh
            if fx == "confused":
                ehs = eh * (0.8 if side == -1 else 1.15)
            rect = pygame.Rect(0, 0, int(ew), max(2, int(ehs)))
            rect.center = (int(cx), int(cy))
            pygame.draw.rect(s, FG, rect, border_radius=int(min(ew, ehs) * 0.35))

            base = rect.top + c["cover"] * ehs
            inner = c["tilt"] * ehs * 0.5
            y_left = base + (inner if side == 1 else -inner)
            y_right = base + (inner if side == -1 else -inner)
            if c["cover"] > 0.01 or abs(c["tilt"]) > 0.01:
                pygame.draw.polygon(s, BG, [(rect.left - 3, rect.top - 4), (rect.right + 3, rect.top - 4),
                                            (rect.right + 3, y_right), (rect.left - 3, y_left)])
            if c["lower"] > 0.01:
                ecy = cy + ehs * 0.5 + ehs * 0.6 * (1.0 - c["lower"])
                er = pygame.Rect(0, 0, int(ew * 1.4), max(2, int(ehs * 1.2)))
                er.center = (int(cx), int(ecy))
                pygame.draw.ellipse(s, BG, er)

            if fx == "crying":
                for k in range(2):
                    ph = (self.t * 0.5 + k * 0.5 + (0.25 if side == 1 else 0.0)) % 1.0
                    ty = rect.bottom + ph * h * 0.28
                    rr = int(h * 0.018 * (1.0 - ph * 0.4))
                    pygame.draw.circle(s, TEAR, (int(cx), int(ty)), max(2, rr))

        mw = w * 0.10 * (1.0 - 0.3 * c["open"])
        mx, my = w * 0.5, h * 0.74 + gy * 0.5
        amp = h * 0.07
        o = max(c["open"], self.talk * 0.9, ye * 0.95)
        wav_ph = self.t * 8.0 if fx == "dizzy" else 0.0
        up, low = [], []
        n = 24
        for i in range(n + 1):
            f = i / n
            x = mx - mw + 2 * mw * f
            y = my + c["curve"] * amp * math.sin(math.pi * f)
            if fx in ("confused", "dizzy"):
                y += amp * 0.35 * math.sin(2 * math.pi * f * 1.5 + wav_ph)
            up.append((x, y))
            low.append((x, y + o * h * 0.10 * math.sin(math.pi * f)))
        if o > 0.03:
            poly = up + low[::-1]
            pygame.draw.polygon(s, MOUTH_FILL, poly)
            pygame.draw.lines(s, FG, True, poly, max(2, int(h * 0.012)))
        else:
            pygame.draw.lines(s, FG, False, up, max(3, int(h * 0.018)))

        if fx == "thinking":
            # dots above the eyes, on the side the eyes look toward
            for i in range(3):
                rr = h * 0.012 * (1.0 + 0.6 * max(0.0, math.sin(self.t * 4.0 - i * 0.9)))
                pygame.draw.circle(s, FG, (int(w * 0.58 + i * w * 0.05), int(h * 0.10)), max(2, int(rr)))

        if fx == "cliff" and math.sin(self.t * 12.0) > -0.3:
            tx, ty, r = w * 0.90, h * 0.14, h * 0.10
            tri = [(tx, ty - r), (tx + r * 0.95, ty + r * 0.7), (tx - r * 0.95, ty + r * 0.7)]
            pygame.draw.polygon(s, (255, 200, 0), tri)
            pygame.draw.polygon(s, (60, 45, 0), tri, max(2, int(h * 0.01)))
            pygame.draw.line(s, (40, 30, 0), (tx, ty - r * 0.3), (tx, ty + r * 0.2), max(3, int(h * 0.018)))
            pygame.draw.circle(s, (40, 30, 0), (int(tx), int(ty + r * 0.45)), max(2, int(h * 0.011)))
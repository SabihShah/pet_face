import math
import pygame
from pygame.math import Vector2

FILL = (70, 220, 255)
EDGE = (30, 130, 160)
SIZE = 200
HAND_X = 0.75
WRIST = Vector2(0, 50)


def _hand_surface():
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    c = SIZE // 2
    fingers = [pygame.Rect(c + dx - 5, 94 - hgt, 10, hgt + 14)
               for dx, hgt in ((-18, 40), (-6, 48), (6, 46), (18, 36))]
    palm = pygame.Rect(c - 23, 88, 46, 62)
    a, b = (c - 21, 128), (c - 38, 106)
    for col, grow in ((EDGE, 2), (FILL, 0)):
        for r in fingers + [palm]:
            pygame.draw.rect(s, col, r.inflate(grow * 2, grow * 2), border_radius=6)
        pygame.draw.line(s, col, a, b, 11 + grow * 2)
        for p in (a, b):
            pygame.draw.circle(s, col, p, 6 + grow)
    return s


def _thumb_surface():
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    c = SIZE // 2
    body = pygame.Rect(c - 28, 96, 56, 54)
    thumb = pygame.Rect(c - 24, 34, 18, 72)
    for col, grow in ((EDGE, 2), (FILL, 0)):
        for r in (body, thumb):
            pygame.draw.rect(s, col, r.inflate(grow * 2, grow * 2), border_radius=8)
    for i in range(3):
        y = 108 + i * 14
        pygame.draw.line(s, EDGE, (c - 2, y), (c + 24, y), 3)
    return s


class Hands:
    def __init__(self):
        self.base = _hand_surface()
        self.thumb = _thumb_surface()
        self.mode = "wave"
        self.lift = 0.0
        self.t = 0.0
        self.wave_left = 0.0
        self.finished = False

    def greet(self, seconds=3.2):
        self.mode = "wave"
        self.wave_left = seconds

    def thumbs_up(self, seconds=2.5):
        self.mode = "thumb"
        self.wave_left = seconds

    def just_finished(self):
        f, self.finished = self.finished, False
        return f

    def update(self, dt):
        self.t += dt
        was = self.wave_left > 0
        self.wave_left = max(0.0, self.wave_left - dt)
        target = 1.0 if self.wave_left > 0 else 0.0
        self.lift += (target - self.lift) * min(1.0, dt * 8.0)
        if was and self.wave_left == 0.0:
            self.finished = True

    def draw(self, s):
        if self.lift < 0.01 or self.wave_left <= 0:
            return
        w, h = s.get_size()
        scale = h / 480.0 * 1.4
        if self.mode == "thumb":
            angle, src = 0.0, self.thumb
            bounce = abs(math.sin(self.t * 7)) * 14 * self.lift
        else:
            angle, src = 8 + 28 * math.sin(self.t * 11) * self.lift, self.base
            bounce = 0.0
        img = pygame.transform.rotozoom(src, angle, scale)
        wrist = Vector2(w * HAND_X, h * (1.12 - 0.5 * self.lift) - bounce)
        center = wrist - (WRIST * scale).rotate(-angle)
        s.blit(img, img.get_rect(center=(int(center.x), int(center.y))))

import json, math, os, time

PATH = os.path.expanduser("~/pet_face/mood.json")
MISS_AFTER = 2 * 3600.0
LONELY_FULL = 6 * 3600.0
TAU = 900.0                 # mood relaxation time constant, seconds


class Mood:
    def __init__(self):
        self.h, self.last = 0.3, time.time()
        self.returned_at, self.returned_after = 0.0, 0.0
        try:
            d = json.load(open(PATH))
            self.h = float(d.get("happiness", self.h))
            self.last = float(d.get("last_interaction", self.last))
            self.returned_at = float(d.get("returned_at", 0.0))
            self.returned_after = float(d.get("returned_after", 0.0))
        except Exception:
            pass
        self._upd, self._saved = time.time(), 0.0

    def lonely(self, now):
        return min(1.0, max(0.0, (now - self.last) / LONELY_FULL))

    def touch(self, now):
        self.last = now

    def bump(self, d):
        self.h = max(-1.0, min(1.0, self.h + d))

    def interact(self, now):
        gap = now - self.last
        self.last = now
        missed = gap > MISS_AFTER
        if missed:
            self.returned_at, self.returned_after = now, gap
            self.bump(0.4)
            print("mood: user back after %.0f s" % gap)
        self.save(now)
        return missed

    def update(self, now):
        dt, self._upd = now - self._upd, now
        target = 0.3 - 0.9 * self.lonely(now)
        self.h += (target - self.h) * (1.0 - math.exp(-dt / TAU))
        if now - self._saved > 60:
            self.save(now)

    def save(self, now):
        self._saved = now
        try:
            json.dump({"happiness": round(self.h, 3), "last_interaction": self.last,
                       "returned_at": self.returned_at, "returned_after": self.returned_after},
                      open(PATH, "w"))
        except Exception:
            pass
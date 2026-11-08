import math
import time
import pygame
from face import Face, BG
from hands import Hands
from api import EventServer
from behavior import Behavior
import json, socket

FACE_X = 0.08
KEYS = {pygame.K_1: "neutral", pygame.K_2: "happy", pygame.K_3: "sad",
        pygame.K_4: "angry", pygame.K_5: "surprised", pygame.K_6: "sleepy"}


def main():
    pygame.init()
    pygame.display.set_caption("Pet face")
    screen = pygame.display.set_mode((800, 480), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    face = Face()
    hands = Hands()
    api = EventServer()
    beh = Behavior()
    talking = False
    level, level_t = 0.0, 0.0
    running = True
    age = 0.0
    greeted = False
    
    fwd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def head(msg):
        try:
            fwd.sendto(json.dumps(msg).encode(), ("127.0.0.1", 5010))
        except OSError:
            pass
               
    while running:
        dt = clock.tick(60) / 1000.0
        age += dt
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key in KEYS:
                    face.set_emotion(KEYS[e.key])
                elif e.key == pygame.K_t:
                    talking = not talking
                elif e.key == pygame.K_f:
                    pygame.display.toggle_fullscreen()
                elif e.key == pygame.K_h:
                    hands.greet()
                    face.set_emotion("happy")
                    
        for m in api.poll():
            head(m)
            if m.get("event") == "gaze":
                face.look_at(float(m.get("x", 0.0)), float(m.get("y", 0.0)))
                continue
            c = m.get("cmd")
            if c == "emotion":
                face.set_emotion(str(m.get("value", "neutral")))
            elif c == "talk":
                talking = bool(m.get("value"))
            elif c == "level":
                level, level_t = float(m.get("value", 0.0)), time.time()
            elif c == "greet":
                hands.greet()
                face.set_emotion("happy")
                
            act = beh.handle(m, time.time())
            if act:
                head({"events": "head_act", "value": act})
            
            if act == "greet":
                hands.greet()
                face.set_emotion("happy")
            elif act == "thumb_up":
                hands.thumbs_up()
                face.set_emotion("happy")
            elif act == "missed":
                hands.greet()
                face.set_emotion("love")
                
        new = beh.update(time.time())
        if new:
            head({"event": "head_act", "value": act})
        
        if new and hands.wave_left <= 0:
            face.set_emotion(new)
        if age > 0.5 and not greeted:
            greeted = True
            hands.greet()
            face.set_emotion("happy")
        if time.time() - level_t < 0.3:
            face.talk = level
        else:
            face.talk = abs(math.sin(face.t * 9)) * (0.6 + 0.4 * math.sin(face.t * 3.1)) if talking else 0.0
        hands.update(dt)
        if hands.just_finished():
            face.set_emotion(beh.emotion)
        face.update(dt)
        if hands.lift < 0.01:
            face.draw(screen)
        else:
            w, h = screen.get_size()
            k = 1.0 - 0.3 * hands.lift
            sub = pygame.Surface((int(w * k), int(h * k)))
            face.draw(sub)
            screen.fill(BG)
            screen.blit(sub, (int(w * FACE_X * hands.lift), int((h - h * k) / 2)))
        hands.draw(screen)
        pygame.display.flip()
    api.close()
    pygame.quit()


if __name__ == "__main__":
    main()

import json
import re
import sys

NUM = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
       "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
       "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
       "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
       "seventy": 70, "eighty": 80, "ninety": 90}
UNIT = [("meter", 1.0), ("metre", 1.0), ("centimeter", 0.01), ("centimetre", 0.01), ("cm", 0.01),
        ("foot", 0.3048), ("feet", 0.3048), ("step", 0.5), ("m", 1.0)]
VERB = re.compile(r"\b(turn|rotate|spin|go|move|walk|head|drive|roll|reverse|steer|step)\b")
NUMRE = r"(\d+(?:\.\d+)?)"


def nums(t):
    out, cur, on = [], 0, False
    for w in t.split() + [""]:
        if w in NUM:
            cur += NUM[w]
            on = True
        elif w == "hundred":
            cur = max(cur, 1) * 100
            on = True
        else:
            if on:
                out.append(str(cur))
                cur, on = 0, False
            if w:
                out.append(w)
    return " ".join(out)


def parse_cmd(text):
    t = re.sub(r"[^a-z0-9. ]", " ", text.lower().replace("-", " "))
    t = re.sub(r"\.(?!\d)", " ", t)
    t = re.sub(r"\b(alexa|please|hey|robot)\b", " ", t)
    t = nums(" ".join(t.split()))
    w = t.split()
    if not w:
        return None
    if w[0] in ("stop", "halt", "freeze") or (len(w) <= 3 and re.search(r"\b(stop|halt|freeze)\b", t)):
        return {"action": "stop"}
    if not VERB.search(t):
        return None
    if re.search(r"\b(turn around|u turn|about face)\b", t):
        return {"action": "right", "angle": 180}
    if re.search(r"\b(forward|forwards|ahead)\b", t) and re.search(r"\b(left|right)\b", t):
        act = "forward_left" if "left" in w else "forward_right"
    elif re.search(r"\b(counter|anti) ?clockwise\b|\bleft\b", t):
        act = "left"
    elif re.search(r"\bclockwise\b|\bright\b", t):
        act = "right"
    elif re.search(r"\b(back|backward|backwards|reverse)\b", t):
        act = "back"
    elif re.search(r"\b(forward|forwards|ahead|straight)\b", t):
        act = "forward"
    elif re.search(r"\b(spin|rotate)\b", t):
        act = "right"
    else:
        return None
    cmd = {"action": act}
    if act in ("left", "right"):
        m = re.search(NUMRE + r" ?(degrees?|deg)\b", t)
        if m:
            cmd["angle"] = min(float(m.group(1)), 720.0)
        elif re.search(r"\b(spin|circle|full)\b", t):
            cmd["angle"] = 360
        elif re.search(r"\bhalf (turn|circle)\b", t):
            cmd["angle"] = 180
        return cmd
    if re.search(r"\b(until|unless|forever|continuously)\b|\bkeep (going|moving|walking)\b|\bdon t stop\b", t):
        cmd["continuous"] = True
        return cmd
    if re.search(r"\bhalf (a |an )?(meter|metre)", t):
        cmd["dist"] = 0.5
        return cmd
    m = re.search(NUMRE + r" ?(meters?|metres?|m|centimeters?|centimetres?|cm|feet|foot|steps?)\b", t)
    if m:
        k = next(v for u, v in UNIT if m.group(2).startswith(u))
        cmd["dist"] = min(float(m.group(1)) * k, 5.0)
        return cmd
    m = re.search(NUMRE + r" ?(seconds?|secs?)\b", t)
    if m:
        cmd["secs"] = min(float(m.group(1)), 30.0)
    return cmd


TESTS = ["Move forward.", "Move forward until I say stop.", "Go back two meters.",
         "Rotate clockwise 180 degrees.", "Turn left.", "Turn around.", "Stop!",
         "Walk forward for five seconds.", "Go forward one hundred fifty centimeters.",
         "Turn counter-clockwise ninety degrees.", "Spin around.", "I am back.", "How are you?"]

if __name__ == "__main__":
    for s in sys.argv[1:] or TESTS:
        print("%-45s %s" % (s, json.dumps(parse_cmd(s))))

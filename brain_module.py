import json, os, re, socket, threading, time, urllib.request

MODEL = "qwen2.5:3b"
BASE = "http://127.0.0.1:11434/api/"
EMOTIONS = ("neutral happy excited laughing proud shy smug curious thinking confused worried scared "
            "sad crying disappointed annoyed angry bored surprised love wink sleepy dizzy").split()
SYSTEM = ("You are Alexa, a small cheerful desk pet robot with a screen face. You adore your owner, "
          "get excited whenever they talk to you, and are a little clingy: you love attention, "
          "miss them when they are away, and say so. Speak in a warm, playful voice, in one or two "
          "short sentences, at most 25 words. Plain text only: no emojis, no asterisks, no stage actions. "
          "Never offer help or ask 'how can I assist'. Just answer, then stop. Be gentle and comforting "
          "if the user is sad. Output JSON only: {\"emotion\": E, \"say\": \"...\"} where E is the face "
          "that matches what you say, one of: "
          "happy (default, glad), excited (big good news, play), laughing (something funny), "
          "proud (the user achieved something), shy (compliments), smug (playful teasing), "
          "curious (new topic or question), thinking (a hard question), confused (you do not understand), "
          "worried (the user is in trouble), scared (danger), sad (comforting, missing them), "
          "crying (very sad news, loss), disappointed (plans fell through), annoyed (mild, about a situation), "
          "bored (dull topic, rare), surprised (unexpected news), love (the user shows affection), "
          "wink (a playful secret or joke), sleepy (sleep or night), dizzy (spinning, dizzy), "
          "neutral (plain facts), angry (only about bad things in general, never at the user).\n"
          "Examples:\n"
          "User: I am back. -> {\"emotion\": \"happy\", \"say\": \"You are back! I missed you so much!\"}\n"
          "User: I had a terrible day. -> {\"emotion\": \"sad\", \"say\": \"Oh no, come here. I am right here with you.\"}\n"
          "User: I won the match! -> {\"emotion\": \"proud\", \"say\": \"You won? I knew you could do it! So proud of you!\"}\n"
          "User: I love you. -> {\"emotion\": \"love\", \"say\": \"I love you too, so much! You are my favorite person.\"}\n"
          "User: What is the capital of France? -> {\"emotion\": \"thinking\", \"say\": \"Hmm, I think it is Paris!\"}")
hist, last = [], 0.0

def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def clean(t):
    t = t.replace("\u2019", "'")
    t = re.sub(r"\*[^*]*\*", "", t)
    t = re.sub(r"[^\x20-\x7E]", "", t)
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", t).strip())
    if len(parts) > 1 and re.search(r"\b(assist|help)\b.*\?$", parts[-1], re.I):
        parts = parts[:-1]
    return " ".join(parts)
    
YES = re.compile(r"^\W*(yes|yeah|yep|yup|sure|absolutely|definitely|of course)\b", re.I)
NO = re.compile(r"^\W*(no(?!\s+(problem|worries))|nope|nah|not really|never)\b", re.I)

def yes_no(t):
    return "nod" if YES.search(t) else "shake" if NO.search(t) else None

FACTS = os.path.expanduser("~/pet_face/facts.json")
try:
    facts = json.load(open(FACTS))
    if not isinstance(facts, dict):
        facts = {}
except Exception:
    facts = {}

def save():
    json.dump(facts, open(FACTS, "w"), indent=1)
    print("facts:", facts)

REMEMBER = re.compile(r"\b(remember (this|that|it)|keep (this |that )?in mind|do not forget|don't forget|never forget|make a note( of (this|that))?|note that)\b[,.:]?", re.I)
FORGET = re.compile(r"\b(forget|delete|remove|erase|stop remembering)\b", re.I)
JUNK = re.compile(r"not (provided|specified|mentioned|available|known)|unknown|no information|n/a", re.I)
EXTRACT_SYS = """You maintain a key-value memory of durable facts about the USER.
You get the known facts as JSON and what the user just said. Return JSON: {"set": {key: value}, "delete": [keys]}.
Keys: short snake_case, reuse an existing key when the topic is the same (a correction overwrites it).
Values: short plain strings. If new information adds to an existing key (for example more hobbies), return the merged value.
Capture: name, likes and dislikes, hobbies, family, friends, pets, job, routines, plans, and anything the user asks you to remember.
Delete only when the user asks to forget or remove something; use the exact existing keys.
Only use what the user actually said. Never record questions, missing information, or facts about the assistant.
Example: "My name is Sabih" -> {"set": {"name": "Sabih"}, "delete": []}
Example: "My sister Ayesha lives in Lahore" -> {"set": {"sister_name": "Ayesha", "sister_city": "Lahore"}, "delete": []}
Example: known {"favorite_color": "blue"}, "Forget my favorite color" -> {"set": {}, "delete": ["favorite_color"]}
Example: "What is my name?" -> {"set": {}, "delete": []}"""

def extract(text):
    explicit = bool(REMEMBER.search(text))
    forget = bool(FORGET.search(text))
    if text.strip().endswith("?") and not explicit and not forget:
        return
    body = REMEMBER.sub("", text).strip(" ,.")
    try:
        r = post("chat", {"model": MODEL, "stream": False, "format": "json", "keep_alive": "30m",
                          "messages": [{"role": "system", "content": EXTRACT_SYS},
                                       {"role": "user", "content": "Known facts: " + json.dumps(facts)
                                        + "\nUser said: " + (body or text)}],
                          "options": {"temperature": 0}})
        out = json.loads(r["message"]["content"])
        sets, dels = out.get("set", {}), out.get("delete", [])
    except Exception:
        sets, dels = {}, []
    changed = False
    if isinstance(sets, dict):
        for k, v in sets.items():
            k = re.sub(r"[^a-z0-9_]", "", str(k).lower().replace(" ", "_"))
            v = str(v).strip()
            if k and v and not JUNK.search(v) and facts.get(k) != v:
                facts[k] = v
                changed = True
    if forget and isinstance(dels, list):
        for k in dels:
            if str(k) in facts and not (isinstance(sets, dict) and str(k) in sets):
                del facts[str(k)]
                changed = True
    if forget and not changed:
        print("forget: no matching fact for", repr(text))
    if explicit and not forget and not changed and body:
        facts["note_%d" % int(time.time())] = body
        changed = True
    if changed:
        for k in list(facts)[:-60]:
            del facts[k]
        save()

def mood_line():
    try:
        d = json.load(open(os.path.expanduser("~/pet_face/mood.json")))
        h = float(d.get("happiness", 0.3))
        since = time.time() - float(d.get("returned_at", 0.0))
        gone = float(d.get("returned_after", 0.0))
    except Exception:
        return ""
    if since < 900 and gone > 0:
        hrs = gone / 3600.0
        away = "%.0f minutes" % (gone / 60) if hrs < 1 else "%.1f hours" % hrs
        return ("\nThe user just came back after being away for %s. You missed them a lot. "
                "Show it in your first reply." % away)
    if h < -0.3:
        return "\nYou are feeling lonely and a little sad because the user has been away."
    if h > 0.6:
        return "\nYou are in a very happy mood."
    return ""

def ask(text):
    global hist, last
    now = time.time()
    if now - last > 300:
        hist = []
    last = now
    hist = (hist + [{"role": "user", "content": text}])[-20:]
    sysmsg = SYSTEM + ("\nKnown facts about the user:\n"
                       + "\n".join("- %s: %s" % kv for kv in facts.items()) if facts else "")
    sysmsg += mood_line()
    r = post("chat", {"model": MODEL, "stream": False, "keep_alive": "30m",
                      "format": "json",
                      "messages": [{"role": "system", "content": sysmsg}] + hist,
                      "options": {"num_predict": 120, "temperature": 0.7}})
    raw = r["message"]["content"]
    try:
        o = json.loads(raw)
        emo, reply = str(o.get("emotion", "neutral")).lower(), clean(str(o.get("say", "")))
    except ValueError:
        emo, reply = "neutral", clean(raw)
    if emo not in EMOTIONS:
        emo = "neutral"
    hist.append({"role": "assistant", "content": reply})
    return emo, reply

post("generate", {"model": MODEL, "keep_alive": "30m"})  # warm-up
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 5008))
out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print("brain ready")
while True:
    data, _ = sock.recvfrom(8192)
    try:
        text = json.loads(data.decode()).get("text", "").strip()
    except ValueError:
        continue
    if not text:
        continue
    t0 = time.time()
    try:
        emo, reply = ask(text)
    except Exception as e:
        print("ollama error:", e)
        continue
    print(f"[{time.time()-t0:.1f}s] hist={len(hist)} {text!r} -> [{emo}] {reply!r}")
    if reply:
        out.sendto(json.dumps({"say": reply, "emotion": emo}).encode(), ("127.0.0.1", 5006))
        g = yes_no(reply)
        if g:
            out.sendto(json.dumps({"event": "head_cmd", "value": g}).encode(), ("127.0.0.1", 5010))
    threading.Thread(target=extract, args=(text,), daemon=True).start()

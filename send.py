import json
import socket
import sys

cmd = sys.argv[1]
msg = {"cmd": cmd}
if len(sys.argv) > 2:
    v = sys.argv[2]
    msg["value"] = (v.lower() == "true") if cmd == "talk" else v
if cmd == "event":
    msg = {"event": sys.argv[2]}
    if len(sys.argv) > 3:
        msg["text"] = sys.argv[3]
socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(json.dumps(msg).encode(), ("127.0.0.1", 5005))

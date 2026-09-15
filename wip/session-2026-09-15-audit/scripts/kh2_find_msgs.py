import json, sys
path = sys.argv[1]
for n, raw in enumerate(open(path, encoding="utf-8")):
    try:
        rec = json.loads(raw)
    except Exception:
        continue
    if rec.get("type") != "user":
        continue
    c = (rec.get("message") or {}).get("content")
    texts = [c] if isinstance(c, str) else [b.get("text", "") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text"]
    for t in texts:
        for key in ("please tell me you fixed a global", "I want a global fix", "makke sure all is documented", "goal"):
            if key in t:
                print(n, key, "|", t[:80].replace("\n", " "))
print("total lines", n)

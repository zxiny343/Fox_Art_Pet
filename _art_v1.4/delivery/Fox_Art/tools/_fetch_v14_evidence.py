import subprocess, json, os, urllib.request, io

PY = r"C:\Users\zxiny\AppData\Local\Programs\Python\Python310\python.exe"
GET = r"D:\01_Software\WorkBuddy\resources\app.asar.unpacked\resources\plugins\workbuddy-builtin\skills\library\drive\get_download_link.py"
OUT = r"C:\Users\zxiny\WorkBuddy\2026-11-01-00-53-44\_evidence"
os.makedirs(OUT, exist_ok=True)

nodes = [
    ("NxEhEGhDHV0aoI0RqExglp", "tails.png"),
    ("plUa5VZLrstWqEeQkkEaY8", "ears.png"),
]
for nid, fname in nodes:
    r = subprocess.run([PY, GET, "--node-id", nid], capture_output=True, text=True,
                       encoding="utf-8")
    line = next((l for l in r.stdout.split("\n") if l.startswith("KS_DRIVE_DOWNLOAD ")), None)
    if not line:
        print("FAIL", nid, r.stdout[:300], r.stderr[:300])
        continue
    d = json.loads(line[len("KS_DRIVE_DOWNLOAD "):])
    url = d["download_url"]
    p = os.path.join(OUT, fname)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as resp, open(p, "wb") as f:
        f.write(resp.read())
    print("OK", nid, d["file_name"], os.path.getsize(p), "bytes ->", p)

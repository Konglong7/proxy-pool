# -*- coding: utf-8 -*-
"""Inspect raw HTML files + zdopen response to design per-site extractors."""
import os, re, json, requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(OUT, "raw")

# 1) save zdopen response
_app_id = os.environ.get("ZDOPEN_APP_ID", "").strip()
_akey = os.environ.get("ZDOPEN_AKEY", "").strip()
if _app_id and _akey:
    url = ("http://www.zdopen.com/FreeProxy/Get/?app_id={}&akey={}"
           "&dalu=0&protocol_type=4&return_type=3").format(_app_id, _akey)
    r = requests.get(url, timeout=15, verify=False)
    with open(os.path.join(RAW, "zdopen_out.txt"), "w", encoding="utf-8") as f:
        f.write(r.text)
    print("zdopen status:", r.status_code, "len:", len(r.text))
    print("zdopen head:", r.text[:500].replace("\n", " | "))
else:
    print("zdopen SKIP: 未设置 ZDOPEN_APP_ID/ZDOPEN_AKEY")
print("=" * 70)

# 2) locate data blobs & ip/port patterns
IPPORT = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}[:\uFF1A](\d{2,5})\b")
IP = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")

def head_lines(fname, n=3):
    try:
        return open(os.path.join(RAW, fname), encoding="utf-8", errors="ignore").read()
    except FileNotFoundError:
        return ""

def scan(name, filename):
    body = head_lines(filename)
    if not body:
        print(f"{name:20s} NO RAW FILE")
        return
    ipp = IPPORT.findall(body)
    ips = IP.findall(body)
    nxt = "__NEXT_DATA__" in body
    has_json = bool(re.search(r"fetch\(|axios|XMLHttpRequest|xhr", body))
    has_down = bool(re.search(r"download|\.txt|\.json|format=txt|export", body, re.I))
    # find first occurrences
    m1 = re.search(IPPORT, body)
    samples = []
    for mo in list(re.finditer(IPPORT, body))[:5]:
        samples.append(mo.group(0))
    print(f"{name:20s} ip:port={len(ipp):4d} ips={len(ips):4d} next_data={nxt} fetch/ajax={has_json} download={has_down} sample={'; '.join(samples) if samples else '-'}")

for n, f in [("advanced.name","advanced.name.html"), ("cometvpn","cometvpn.html"),
             ("databay","databay.html"), ("net-vortex","net-vortex.html"),
             ("openproxylist","openproxylist.html"), ("proxmint","proxmint.html"),
             ("proxymix","proxymix.html"), ("proxynova","proxynova.html"),
             ("proxyo2","proxyo2.html"), ("proxysale","proxysale.html"),
             ("scrappey","scrappey.html"), ("socks5proxies","socks5proxies.html"),
             ("spys.one","spys.one.html"), ("stormsia","stormsia.html")]:
    scan(n, f)
print("=" * 70)

# 3) stormsia: find data/API url in html
body = head_lines("stormsia.html")
for pat in [r"https?://[^\"' ]+\.(json|txt|php)[^\"' ]*", r"/proxy-list[^\"' ]*",
            r"api[^\"' ]*", r"github(/|:)[^\"' ]+"]:
    found = sorted(set(re.findall(pat, body)))[:8]
    if found:
        print("stormsia", pat, "->", found)

# 4) openproxylist: download links
body = head_lines("openproxylist.html")
print("openproxylist links:", sorted(set(re.findall(r'href="([^"]+)"', body)))[:20])

# 5) spys.one: what do rows look like
body = head_lines("spys.one.html")
m = re.search(r"<tr>.*?</tr>", body, re.S)
if m:
    print("spys.one first tr:", m.group(0)[:600])
m2 = re.search(r"<script>(.*?)</script>", body, re.S)
if m2:
    print("spys.one first script:", m2.group(1)[:300])

# 6) proxynova: how are IPs encoded
body = head_lines("proxynova.html")
idx = body.find("8080")
print("proxynova around 8080:", body[max(0, idx-400):idx+200].replace("\n", " ")[:800])
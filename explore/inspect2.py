# -*- coding: utf-8 -*-
"""Inspect proxy.cc data endpoint + proxynova atob obfuscation + spys packer decode."""
import re, base64, os, json, requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}

# ---- proxy.cc ----
try:
    r = requests.get("https://proxy.cc/zh/freeproxy/", headers=UA, timeout=25, verify=False)
    body = r.text
    open(os.path.join(RAW, "proxycc.html"), "w", encoding="utf-8").write(body)
    print("proxy.cc saved", len(body))
    for pat in [r"/api/[\w/?.=&%-]+", r"https?://[^\"' ]*api[^\"' ]*", r"free-proxy[\w/?.=&%-]*", r"data-capo|__NUXT|fetch\(|useFetch|\$fetch|apiBase|baseURL"]:
        found = sorted(set(re.findall(pat, body)))[:15]
        print("proxy.cc", pat, "->", found)
    ipp = set(re.findall(r"\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}", body))
    print("proxy.cc ip:port count:", len(ipp), list(ipp)[:5])
    # inline json blobs
    for pat in [r"\"ip\":\"[\d.]+\"", r"\"port\": ?\d+", r"\{\"data\"", r"proxyList|proxy_list|proxies\s*[:=]"]:
        found = sorted(set(re.findall(pat, body)))[:8]
        print("proxy.cc blob", pat, "->", found)
except Exception as e:
    print("proxy.cc ERR", e)

print("=" * 60)

# ---- proxynova ----
try:
    body = open(os.path.join(RAW, "proxynova.html"), encoding="utf-8", errors="ignore").read()
    writes = re.findall(r'document\.write\([^)]*\)', body)
    print("proxynova document.write count:", len(writes))
    for w in writes[:6]:
        print("   ", w[:220])
    atobs = re.findall(r'atob\("[^"]+"\)', body)
    print("proxynova atob count:", len(atobs))
    # decode one sample manually with python for verification
    sample = writes[0] if writes else ""
    m = re.match(r'document\.write\((.*)\)', sample)
    if m:
        expr = m.group(1)
        print("sample expr:", expr[:200])
    # try to evaluate with simple mapping: atob -> b64decode, repeat, substring
    def js_str(s):
        return s[1:-1].replace("\\'", "'").replace('\\"', '"')
    # show all raw scripts that build IPs
    ipwrites = [w for w in writes if "atob" in w]
    for w in ipwrites[:3]:
        print("IPWRITE:", w[:260])
except Exception as e:
    print("proxynova ERR", e)

print("=" * 60)

# ---- spys.one: dump raw row lines with IP + port script ----
try:
    body = open(os.path.join(RAW, "spys.one.html"), encoding="utf-8", errors="ignore").read()
    rows = re.findall(r'<tr[^>]*class=(?:spy1|spy1x|spy1xx)[^>]*>(.*?)</tr>', body, re.S)
    print("spys rows:", len(rows))
    for row in rows[:3]:
        ip = re.search(r"\d{1,3}(?:\.\d{1,3}){3}", row)
        scr = re.search(r'<script>(.*?)</script>', row, re.S)
        print("IP:", ip.group(0) if ip else "?", "PORTSCRIPT:", scr.group(1)[:160] if scr else "?")
        # type
        typed = re.search(r"HTTP<font class=spy14>S</font>|HTTP", row)
        print("TYPE:", "HTTPS" if "spy14>S</font>" in row else ("HTTP" if "HTTP" in row else "?"))
except Exception as e:
    print("spys ERR", e)
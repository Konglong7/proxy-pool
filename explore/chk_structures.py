import re, os
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
for f in ["advanced.name.html","proxysale.html","proxymix.html"]:
    body = open(os.path.join(BASE,f),encoding="utf-8",errors="ignore").read()
    print("=====", f, "len", len(body))
    for pat in [r"document\.write\([^)]{0,80}\)", r"\d{1,3}(?:\.\d{1,3}){3}", r"class=\"[^\"]*(?:ip|port|proxy)[^\"]*\""]:
        found = re.findall(pat, body)
        print(pat, "-> count", len(found), sorted(set(found))[:10])
    # look at table area
    m = re.search(r"<table[^>]*>.*?</table>", body, re.S)
    if m:
        seg = m.group(0)
        print("table head:", seg[:500].replace("\n", " "))

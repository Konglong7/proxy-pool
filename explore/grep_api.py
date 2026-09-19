import re, os
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
for f in ["advanced.name.html","proxysale.html","proxymix.html","openproxylist.html","proxyo2.html","databay.html"]:
    body = open(os.path.join(BASE,f),encoding="utf-8",errors="ignore").read()
    print("=====", f)
    for pat in [r"fetch\([^)]+\)", r"\$fetch\([^)]+\)", r"axios\([^)]+\)", r"https?://[^\"\' ]*(?:api|json|proxy)[^\"\' ]*", r"url:\s*[\"\'][^\"\']+[\"\']", r"__next|__NUXT|window\.__"]:
        found = sorted(set(re.findall(pat, body)))[:8]
        if found:
            print(pat, "->", [x[:120] for x in found])

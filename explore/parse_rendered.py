# -*- coding: utf-8 -*-
"""Parse proxynova rendered HTML -> ip:port list. Parse proxyo2 comment-stripped HTML."""
import re, os, json

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw")

UA_IP = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def load_rendered(html_path, out_json):
    body = open(html_path, encoding="utf-8", errors="ignore").read()
    data = json.load(open(os.path.join(BASE, out_json), encoding="utf-8"))
    scripts = re.split(r"<script(?![^>]*\bsrc=)[^>]*>", body)  # approximate
    # Rebuild by replacing each inline script block with its captured writes
    rendered = body
    pat = re.compile(r"\s*<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>\s*")
    idx = 0
    # map outputs per script index
    outputs = {}
    for item in data["perScript"]:
        outputs[item["index"]] = "".join(item["outputs"])
    # iterate actual script positions in order
    pos = 0
    counter = -1

    def repl(m):
        nonlocal counter
        counter += 1
        out = outputs.get(counter, "")
        return out

    rendered = pat.sub(repl, body)
    return rendered


def parse_proxynova():
    rendered = load_rendered(os.path.join(RAW, "proxynova.html"), "out_pn.json")
    # rows: <tr>...<td><IP text></td>...<td><a ...>PORT</a></td>
    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>", rendered, re.S
    )
    results = []
    for row in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(tds) < 4:
            continue
        ipm = UA_IP.search(tds[0])
        if not ipm:
            continue
        portm = re.search(r"title=\"Port\s+(\d+)\"|>(\d{2,5})<", tds[1][:200])
        port = portm.group(1) or portm.group(2) if portm else ""
        if port:
            results.append((ipm.group(0), port))
    seen = set()
    out = []
    for ip, port in results:
        if (ip, port) not in seen:
            seen.add((ip, port))
            out.append((ip, port))
    print("proxynova parsed:", len(out))
    for ip, port in out[:15]:
        print("  ", ip, port)
    return out


def parse_proxyo2():
    body = open(os.path.join(RAW, "proxyo2.html"), encoding="utf-8", errors="ignore").read()
    render = re.sub(r"<!--\s*-->\s*", "", body)
    ipp = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})\s*:\s*(\d{2,5})", render)
    seen = set()
    out = []
    for ip, port in ipp:
        if (ip, port) not in seen:
            seen.add((ip, port))
            out.append((ip, port))
    print("proxyo2 parsed:", len(out))
    for ip, port in out[:15]:
        print("  ", ip, port)
    return out


if __name__ == "__main__":
    parse_proxynova()
    print("=" * 40)
    parse_proxyo2()
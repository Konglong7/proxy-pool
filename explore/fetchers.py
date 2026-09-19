# -*- coding: utf-8 -*-
"""Per-source proxy fetchers. Each fetch_* returns list of dicts {ip_port, proto}."""
import re, os, json, subprocess, time
import requests, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_H = {"User-Agent": UA, "Accept": "text/html,application/json,text/plain,*/*;q=0.8",
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}

IPRE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})$")
IP_ONLY = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def http_get(url, timeout=15, retries=2, ua=None):
    headers = dict(_H)
    if ua:
        headers["User-Agent"] = ua
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
            return r
        except Exception as e:
            last = e
            time.sleep(1.2)
    raise RuntimeError(f"GET {url} failed: {last}")


def norm(ip, port):
    if IPRE.match(f"{ip}:{port}"):
        return f"{ip}:{port}"
    return None


def strip_comments(html):
    return re.sub(r"<!--[\s\S]*?-->", "", html)
def parse_html_tables(body):
    """Generic: extract ip/port from table rows (supports separate cells, ip:port cell, 'ip : port')."""
    body = strip_comments(body)
    soup = BeautifulSoup(body, "lxml")
    found = {}
    pair_re = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})\s*[:：]\s*(\d{2,5})")
    for tr in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        texts = [c for c in cells if c]
        if not texts:
            continue
        # strategy A: a single cell contains ip:port / ip : port
        for c in texts:
            m = pair_re.search(c)
            if m:
                ip_port = norm(m.group(1), m.group(2))
                if ip_port and ip_port not in found:
                    found[ip_port] = {"ip_port": ip_port, "proto": "?"}
        # strategy B: separate IP cell + numeric port cell
        for i, c in enumerate(texts):
            m = IP_ONLY.fullmatch(c.strip())
            if not m:
                continue
            for j in range(i + 1, min(len(texts), i + 6)):
                p = texts[j].strip()
                if p.isdigit() and 1 <= int(p) <= 65535:
                    ip_port = norm(m.group(0), p)
                    if ip_port and ip_port not in found:
                        proto = "?"
                        for k in range(j + 1, min(len(texts), j + 4)):
                            if texts[k].strip().upper() in ("HTTP", "HTTPS", "SOCKS4", "SOCKS5"):
                                proto = texts[k].strip().upper()
                                break
                        found[ip_port] = {"ip_port": ip_port, "proto": proto}
                    break
    return list(found.values())


# ---------------- source-specific fetchers ----------------

def fetch_proxyscrape():
    out = []
    urls = [
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=http&timeout=8000",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all",
    ]
    for u in urls:
        try:
            r = http_get(u, timeout=20)
            if r.status_code == 200:
                for line in r.text.strip().splitlines():
                    line = line.strip()
                    if IPRE.fullmatch(line):
                        out.append({"ip_port": line, "proto": "?"})
        except Exception as e:
            print("  proxyscrape ERR", str(e)[:100])
    return out


def fetch_geonode():
    out = []
    try:
        r = http_get("https://proxylist.geonode.com/api/proxy-list?limit=300&page=1&sort_by=lastChecked&sort_type=desc",
                     timeout=25)
        if r.status_code == 200:
            data = r.json()
            for item in data.get("data", []):
                protos = [p.lower() for p in item.get("protocols", [])]
                if not any(p in ("http", "https") for p in protos):
                    continue
                ip_port = norm(item.get("ip"), item.get("port"))
                if ip_port:
                    out.append({"ip_port": ip_port, "proto": "HTTPS" if "https" in protos else "HTTP"})
    except Exception as e:
        print("  geonode ERR", str(e)[:100])
    return out


def fetch_stormsia():
    out = []
    for f in ("http.txt", "working_proxies.txt"):
        for attempt in range(3):
            try:
                r = http_get(f"https://raw.githubusercontent.com/stormsia/proxy-list/main/{f}", timeout=20)
                if r.status_code == 200 and r.text.strip():
                    for line in r.text.splitlines():
                        line = line.strip()
                        m = re.match(r"^(?:https?|socks[45])://(\d{1,3}(?:\.\d{1,3}){3}:\d{2,5})$", line)
                        if m:
                            proto = "HTTP" if line.startswith("http") else "?"
                            out.append({"ip_port": m.group(1), "proto": proto})
                        elif IPRE.fullmatch(line):
                            out.append({"ip_port": line, "proto": "?"})
                    break
            except Exception as e:
                if attempt == 2:
                    print("  stormsia ERR", str(e)[:100])
                time.sleep(1)
    return out


def fetch_zdopen():
    """站大爷 zdopen 免费API（凭据通过环境变量 ZDOPEN_APP_ID / ZDOPEN_AKEY 注入）。"""
    out = []
    app_id = os.environ.get("ZDOPEN_APP_ID", "").strip()
    akey = os.environ.get("ZDOPEN_AKEY", "").strip()
    if not app_id or not akey:
        print("  zdopen SKIP: 未设置 ZDOPEN_APP_ID/ZDOPEN_AKEY")
        return out
    try:
        u = ("http://www.zdopen.com/FreeProxy/Get/?app_id={}&akey={}"
             "&dalu=0&protocol_type=4&return_type=3").format(app_id, akey)
        r = http_get(u, timeout=25)
        if r.status_code == 200:
            data = r.json()
            for item in data.get("data", {}).get("proxy_list", []):
                ip_port = norm(item.get("ip"), item.get("port"))
                if ip_port:
                    out.append({"ip_port": ip_port, "proto": str(item.get("protocol", "")).upper()})
    except Exception as e:
        print("  zdopen ERR", str(e)[:100])
    return out


def fetch_fpln():
    out = []
    for url in ("https://free-proxy-list.net/", "https://free-proxy-list.net/zh-cn/ssl-proxy.html"):
        try:
            r = http_get(url, timeout=25)
            if r.status_code == 200:
                out.extend(parse_html_tables(r.text))
        except Exception as e:
            print("  fpln ERR", str(e)[:100])
    return out
def fetch_proxynova():
    try:
        r = http_get("https://www.proxynova.com/proxy-server-list/", timeout=25)
        if r.status_code != 200:
            return []
        open(os.path.join(RAW, "proxynova.html"), "w", encoding="utf-8").write(r.text)
        subprocess.run(["node", os.path.join(BASE, "js_render.js"), "raw/proxynova.html", "out_pn.json"],
                       cwd=BASE, timeout=120, capture_output=True)
        from parse_rendered import parse_proxynova
        pairs = parse_proxynova()
        return [{"ip_port": f"{ip}:{p}", "proto": "?"} for ip, p in pairs]
    except Exception as e:
        print("  proxynova ERR", str(e)[:150])
        return []


def fetch_hide_mn():
    try:
        r = http_get("https://hide.mn/en/proxy-list/", timeout=25)
        if r.status_code == 200:
            return parse_html_tables(r.text)
    except Exception as e:
        print("  hide.mn ERR", str(e)[:100])
    return []


def fetch_spys():
    try:
        r = http_get("https://spys.one/en/", timeout=25)
        if r.status_code == 200:
            open(os.path.join(RAW, "spys.one.html"), "w", encoding="utf-8").write(r.text)
            subprocess.run(["node", os.path.join(BASE, "spys_eval4.js")], cwd=BASE, timeout=120, capture_output=True)
    except Exception as e:
        print("  spys fetch ERR", str(e)[:120])
    if os.path.exists(os.path.join(BASE, "out_spys.json")):
        try:
            res = json.load(open(os.path.join(BASE, "out_spys.json"), encoding="utf-8"))
            return [{"ip_port": f"{x['ip']}:{x['port']}", "proto": x["type"]} for x in res]
        except Exception:
            pass
    return []


def fetch_proxyo2():
    try:
        r = http_get("https://proxyo2.com/", timeout=25)
        if r.status_code != 200:
            return []
        render = strip_comments(r.text)
        found = []
        for ip, p in set(re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})\s*:\s*(\d{2,5})", render)):
            found.append({"ip_port": f"{ip}:{p}", "proto": "?"})
        return found
    except Exception as e:
        print("  proxyo2 ERR", str(e)[:100])
        return []


def fetch_netvortex():
    out = []
    try:
        r = http_get("https://net-vortex.com/api/free_proxies.php", timeout=30)
        if r.status_code == 200:
            data = r.json()
            for item in data.get("proxies", []):
                protos = [p.lower() for p in item.get("protocols", [])]
                if not any(p in ("http", "https") for p in protos):
                    continue
                ip_port = norm(item.get("ip"), item.get("port"))
                if ip_port:
                    out.append({"ip_port": ip_port,
                                "proto": "HTTPS" if "https" in protos else "HTTP"})
    except Exception as e:
        print("  netvortex ERR", str(e)[:120])
    return out


def fetch_cometvpn():
    try:
        r = http_get("https://cometvpn.com/free-proxy-list/", timeout=25)
        if r.status_code == 200:
            return parse_html_tables(r.text)
    except Exception as e:
        print("  cometvpn ERR", str(e)[:100])
    return []


def fetch_scrappey():
    try:
        r = http_get("https://scrappey.com/tools/free-proxy-lists/http", timeout=30)
        if r.status_code == 200:
            return parse_html_tables(r.text)
    except Exception as e:
        print("  scrappey ERR", str(e)[:100])
    return []


def fetch_socks5proxies():
    try:
        r = http_get("https://socks5proxies.com/free-proxy-list/", timeout=30)
        if r.status_code == 200:
            return parse_html_tables(r.text)
    except Exception as e:
        print("  socks5proxies ERR", str(e)[:100])
    return []
def fetch_databay():
    out = []
    try:
        r = http_get("https://databay.com/api/v1/proxy-list", timeout=30)
        if r.status_code == 200:
            try:
                data = r.json()
                items = data if isinstance(data, list) else data.get("data", data.get("proxies", []))
                for item in items:
                    if isinstance(item, dict):
                        ip = item.get("ip") or item.get("ipAddress")
                        p = item.get("port")
                        if ip and p:
                            ip_port = norm(ip, p)
                            if ip_port:
                                out.append({"ip_port": ip_port, "proto": "?"})
            except Exception:
                for line in r.text.splitlines():
                    if IPRE.fullmatch(line.strip()):
                        out.append({"ip_port": line.strip(), "proto": "?"})
        else:
            r2 = http_get("https://databay.com/free-proxy-list", timeout=30)
            if r2.status_code == 200:
                out.extend(parse_html_tables(r2.text))
    except Exception as e:
        print("  databay ERR", str(e)[:120])
    return out


def fetch_proxmint():
    try:
        r = http_get("https://proxmint.com/free-proxies/http", timeout=30)
        if r.status_code == 200:
            return parse_html_tables(r.text)
    except Exception as e:
        print("  proxmint ERR", str(e)[:100])
    return []


def fetch_playwright_sources():
    pw_file = os.path.join(BASE, "out_pw.json")
    if os.path.exists(pw_file):
        return json.load(open(pw_file, encoding="utf-8"))
    return {}


def fetch_proxy_cc():
    out = []
    try:
        r = http_get("https://proxy.cc/zh/freeproxy/", timeout=30)
        if r.status_code == 200:
            body = r.text
            seen = set()
            for ip, p in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})[:\uFF1A](\d{2,5})", body):
                key = f"{ip}:{p}"
                if key not in seen:
                    seen.add(key)
                    out.append({"ip_port": key, "proto": "?"})
    except Exception as e:
        print("  proxy.cc ERR", str(e)[:120])
    return out


def fetch_proxydb():
    try:
        r = http_get("https://www.proxydb.net/", timeout=25, retries=1)
        if r.status_code == 200:
            return parse_html_tables(r.text)
    except Exception as e:
        print("  proxydb ERR", str(e)[:100])
    return []


def fetch_fineproxy():
    try:
        r = http_get("https://fineproxy.org/free-proxy/", timeout=25, retries=2)
        if r.status_code == 200:
            return parse_html_tables(r.text)
    except Exception as e:
        print("  fineproxy ERR", str(e)[:100])
    return []


def fetch_proxylistfree():
    try:
        r = http_get("https://www.proxylistfree.com/", timeout=30, retries=1)
        if r.status_code == 200:
            return parse_html_tables(r.text)
    except Exception as e:
        print("  proxylistfree ERR", str(e)[:100])
    return []


def fetch_freeproxyworld():
    try:
        r = http_get("https://www.freeproxy.world/", timeout=30, retries=1)
        if r.status_code == 200:
            return parse_html_tables(r.text)
    except Exception as e:
        print("  freeproxy.world ERR", str(e)[:100])
    return []
SOURCES = [
    ("ProxyScrape API (proxyscrape.com)", fetch_proxyscrape),
    ("Geonode API (geonode.com)", fetch_geonode),
    ("Stormsia GitHub (stormsia.github.io)", fetch_stormsia),
    (u"\u7ad9\u5927\u7237 zdopen.com API", fetch_zdopen),
    ("free-proxy-list.net (\u542bSSL\u9875)", fetch_fpln),
    ("ProxyNova (proxynova.com)", fetch_proxynova),
    ("HideMyName (hide.mn)", fetch_hide_mn),
    ("Spys.one (spys.one)", fetch_spys),
    ("ProxyO2 (proxyo2.com)", fetch_proxyo2),
    ("NetVortex API (net-vortex.com)", fetch_netvortex),
    ("CometVPN (cometvpn.com)", fetch_cometvpn),
    ("Scrappey (scrappey.com)", fetch_scrappey),
    ("Socks5Proxies (socks5proxies.com)", fetch_socks5proxies),
    ("Databay API (databay.com)", fetch_databay),
    ("ProxMint (proxmint.com)", fetch_proxmint),
    ("advanced.name", None),
    ("ProxySale (proxysale.biz)", None),
    ("ProxyMix (proxymix.net)", None),
    ("OpenProxyList (openproxylist.com)", None),
    ("PROXY.CC (proxy.cc)", fetch_proxy_cc),
    ("ProxyDB (proxydb.net)", fetch_proxydb),
    ("FineProxy (fineproxy.org)", fetch_fineproxy),
    ("ProxyListFree (proxylistfree.com)", fetch_proxylistfree),
    ("FreeProxy.World (freeproxy.world)", fetch_freeproxyworld),
]


def fetch_all(limit_per_source=200):
    collected = {}
    pw_data = fetch_playwright_sources()
    for name, fn in SOURCES:
        if fn is None:
            if "advanced.name" in name:
                collected[name] = pw_data.get("advanced.name", []) + pw_data.get("advanced.name_socks", [])
            elif "ProxySale" in name:
                collected[name] = pw_data.get("proxysale", [])
            elif "ProxyMix" in name:
                collected[name] = pw_data.get("proxymix", [])
            elif "OpenProxyList" in name:
                collected[name] = pw_data.get("openproxylist", [])
            else:
                collected[name] = []
            continue
        print(f"[fetch] {name} ...")
        try:
            items = fn()
            collected[name] = items[:limit_per_source]
            print(f"  -> {len(collected[name])} candidates")
        except Exception as e:
            print(f"  -> ERROR {str(e)[:120]}")
            collected[name] = []
    return collected


if __name__ == "__main__":
    res = fetch_all()
    with open(os.path.join(BASE, "collected.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    total = 0
    for k, v in res.items():
        total += len(v)
        print(k, len(v))
    print("TOTAL", total)
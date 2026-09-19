# -*- coding: utf-8 -*-
"""Phase 1: 探测所有代理网站/API 的可达性，保存原始HTML供分析。"""
import json, os, re, sys, time, requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(OUT, "raw")
os.makedirs(RAW, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_ZDA = os.environ.get("ZDOPEN_APP_ID", "").strip()
_ZDAK = os.environ.get("ZDOPEN_AKEY", "").strip()

SITES = {
    "proxynova":            "https://www.proxynova.com/proxy-server-list/",
    "hidemyname":           "https://hide.mn/en/proxy-list/",
    "spys.one":             "https://spys.one/en/",
    "proxy5.net":           "https://proxy5.net/cn/free-proxy",
    "proxyscrape.com":      "https://proxyscrape.com/free-proxy-list",
    "openproxylist":        "https://openproxylist.com/",
    "openproxylist_proxy":  "https://openproxylist.com/proxy",
    "proxy.cc":             "https://proxy.cc/zh/freeproxy/",
    "geonode":              "https://geonode.com/free-proxy-list",
    "free-proxy-list.net":  "https://free-proxy-list.net/",
    "free-proxy-list_ssl":  "https://free-proxy-list.net/zh-cn/ssl-proxy.html",
    "proxydb":              "https://www.proxydb.net/",
    "proxifly":             "https://proxifly.dev/tools/proxy-list",
    "freeproxy.world":      "https://www.freeproxy.world/",
    "advanced.name":        "https://advanced.name/freeproxy",
    "proxymix":             "https://proxymix.net/freeproxy",
    "proxysale":            "https://proxysale.biz/freeproxy",
    "proxyo2":              "https://proxyo2.com/",
    "fineproxy":            "https://fineproxy.org/free-proxy/",
    "net-vortex":           "https://net-vortex.com/free-proxies",
    "databay":              "https://databay.com/free-proxy-list",
    "cometvpn":             "https://cometvpn.com/free-proxy-list/",
    "socks5proxies":        "https://socks5proxies.com/free-proxy-list/",
    "proxmint":             "https://proxmint.com/free-proxies/http",
    "scrappey":             "https://scrappey.com/tools/free-proxy-lists/http",
    "proxylistfree":        "https://www.proxylistfree.com/",
    "stormsia":             "https://stormsia.github.io/proxy-list/",
    "zdopen_api": ("http://www.zdopen.com/FreeProxy/Get/?app_id={}&akey={}"
                   "&dalu=0&protocol_type=4&return_type=3").format(_ZDA, _ZDAK),
}
if not (_ZDA and _ZDAK):
    print("[skip] zdopen_api: 未设置 ZDOPEN_APP_ID/ZDOPEN_AKEY")
    SITES.pop("zdopen_api", None)

APIS = {
    "proxyscrape_v4_http": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=http",
    "proxyscrape_v4_all":  "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text",
    "proxyscrape_v2_http": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=4000&country=all",
    "geonode_api":         "https://proxylist.geonode.com/api/proxy-list?limit=200&page=1&sort_by=lastChecked&sort_type=desc",
    "proxifly_txt":        "https://proxifly.dev/api/proxy-list?format=txt&type=http",
    "stormsia_json":       "https://stormsia.github.io/proxy-list/data.json",
    "stormsia_raw":        "https://raw.githubusercontent.com/stormsia/proxy-list/main/proxy_list_data.json",
    "netvortex_api":       "https://net-vortex.com/api/proxies?page=1&limit=100",
    "databay_download":    "https://databay.com/download/free-proxy-list/raw?data=all",
    "openproxylist_api":   "https://openproxylist.com/proxy",
    "fineproxy_txt":       "https://fineproxy.org/wp-content/plugins/fineproxy/api.php?type=https",
}


def probe(name, url, timeout=12):
    rec = {"name": name, "url": url}
    t0 = time.time()
    try:
        r = requests.get(url, headers={"User-Agent": UA,
                        "Accept": "text/html,application/json,text/plain,*/*;q=0.8"},
                         timeout=timeout, verify=False, allow_redirects=True)
        rec["status"] = r.status_code
        rec["ms"] = int((time.time() - t0) * 1000)
        rec["size"] = len(r.content)
        ct = r.headers.get("Content-Type", "")
        rec["ctype"] = ct
        body = r.text
        ip_ports = set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}\b", body))
        rec["ip_port_raw"] = len(ip_ports)
        if name in ("proxynova", "spys.one", "proxyo2", "advanced.name", "proxysale",
                    "fineproxy", "proxylistfree", "proxymix", "freeproxy.world",
                    "cometvpn", "socks5proxies", "proxmint", "scrappey", "databay",
                    "net-vortex", "stormsia", "openproxylist", "openproxylist_proxy"):
            safe = name.replace("/", "_")
            with open(os.path.join(RAW, f"{safe}.html"), "w", encoding="utf-8", errors="ignore") as f:
                f.write(body)
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["ms"] = int((time.time() - t0) * 1000)
    return rec


def main():
    results = []
    for name, url in SITES.items():
        r = probe(name, url)
        results.append({"kind": "site", **r})
        print(f"[site] {name:24s} {r.get('status','ERR'):>3} {r.get('ms','?'):>6}ms "
              f"size={r.get('size','-'):>8} ip:port={r.get('ip_port_raw','?')} {r.get('error','')}")
    for name, url in APIS.items():
        r = probe(name, url)
        results.append({"kind": "api", **r})
        print(f"[api ] {name:24s} {r.get('status','ERR'):>3} {r.get('ms','?'):>6}ms "
              f"size={r.get('size','-'):>8} ip:port={r.get('ip_port_raw','?')} {r.get('error','')}")
    with open(os.path.join(OUT, "probe1_result.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("saved", os.path.join(OUT, "probe1_result.json"))


if __name__ == "__main__":
    main()
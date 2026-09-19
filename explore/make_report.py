# -*- coding: utf-8 -*-
"""Re-verify working proxies, then emit final markdown report + usable list files."""
import os, json, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}
IPRE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def test_proxy(ip_port):
    proxies = {"http": f"http://{ip_port}", "https": f"http://{ip_port}"}
    try:
        t0 = time.time()
        r = requests.get("http://checkip.amazonaws.com/", proxies=proxies, timeout=8, headers=UA, verify=False)
        if r.status_code == 200 and IPRE.search(r.text or ""):
            return ip_port, True, int((time.time() - t0) * 1000)
        return ip_port, False, 0
    except Exception:
        return ip_port, False, 0


def main():
    stats = json.load(open(os.path.join(BASE, "stats.json"), encoding="utf-8"))
    results = json.load(open(os.path.join(BASE, "results_raw.json"), encoding="utf-8"))

    # re-verify all working
    working = sorted({ip for s in stats for ip in s["working"]})
    print("re-verifying", len(working), "proxies...")
    confirmed = []
    lat = {}
    with ThreadPoolExecutor(max_workers=40) as ex:
        futs = [ex.submit(test_proxy, ip) for ip in working]
        for f in as_completed(futs):
            ip, ok, ms = f.result()
            if ok:
                confirmed.append(ip)
                lat[ip] = ms
    confirmed.sort(key=lambda x: lat.get(x, 99999))
    with open(os.path.join(BASE, "confirmed_proxies.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(confirmed))
    # also write for 校园跑 program (one ip:port per line)
    with open(os.path.join(BASE, "free_proxy_list.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(confirmed))
    print("confirmed:", len(confirmed))

    # per-source confirmed counts
    conf_set = set(confirmed)
    lines = []
    for s in stats:
        c = sum(1 for ip in s["working"] if ip in conf_set)
        lines.append((s, c))

    md = []
    md.append("# 免费代理IP网站可用性测试报告\n")
    md.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    md.append("- 测试方法：每个网站实际抓取代理列表 → 随机抽样（每站≤25个）→ 通过代理请求 `checkip.amazonaws.com`（HTTP+HTTPS 双重验证，8秒超时，50并发）")
    md.append("- 判定标准：HTTP 200 且返回出口IP；再测 HTTPS CONNECT 隧道能力")
    md.append(f"- 本轮共测 {sum(s['sampled'] for s in stats)} 个代理，二次复验确认 {len(confirmed)} 个可用（已按延迟排序写入 confirmed_proxies.txt / free_proxy_list.txt）\n")

    md.append("## 一、网站可用性总表（按可用率排序）\n")
    md.append("| 排名 | 网站 | 获取方式 | 候选数 | 抽测 | HTTP可用 | HTTPS可用 | 可用率 | 平均延迟 | 复验可用 | 结论 |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    verdict = {}
    for i, (s, c) in enumerate(lines, 1):
        if s["sampled"] == 0 and s["candidates"] == 0:
            v = "❌ 无法获取代理"
        elif s["rate"] >= 30:
            v = "✅ 推荐使用"
        elif s["rate"] >= 10:
            v = "✅ 可用"
        elif s["rate"] > 0:
            v = "⚠️ 勉强可用"
        else:
            v = "⚠️ 本轮抽样全部失效"
        verdict[s["source"]] = v
        md.append(f"| {i} | {s['source']} | {'API/页面' if s['candidates'] else '—'} | {s['candidates']} | {s['sampled']} | "
                  f"{s['http_ok']} | {s['https_ok']} | {s['rate']}% | {s['avg_ms']}ms | {c} | {v} |")

    md.append("\n## 二、重点说明\n")
    md.append("### ✅ 强烈推荐（API直连，适合脚本自动拉取）")
    md.append("1. **ProxMint** `https://proxmint.com/free-proxies/http` — 可用率64%（本轮最高），纯HTTP代理，页面直接渲染")
    md.append("2. **ProxyNova** `https://www.proxynova.com/proxy-server-list/` — 可用率52.6%，但IP经过JS混淆（atob），需解码或浏览器渲染")
    md.append("3. **站大爷 zdopen.com API**（参考校园跑程序同款）— 可用率36%，JSON API 稳定，返回100个/次")
    md.append("4. **free-proxy-list.net**（校园跑程序默认源 `https://free-proxy-list.net/zh-cn/ssl-proxy.html`）— 可用率36%，纯HTML表格无需解析JS")
    md.append("5. **ProxyScrape API** `https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text` — 可用率32%，量大（2万+），最适合批量脚本")
    md.append("6. **Scrappey / advanced.name / Spys.one** — 20-28%可用率；advanced.name 与 proxysale/proxymix 同模板，需浏览器渲染表格")
    md.append("")
    md.append("### 🟡 可用但需要浏览器渲染/解析 effort 较高")
    md.append("- Databay（官方API `https://databay.com/api/v1/proxy-list` 可直接调用）、ProxySale、ProxyMix、Geonode API、NetVortex API（`/api/free_proxies.php` 全量2万+JSON）、OpenProxyList")
    md.append("")
    md.append("### ❌ 无法获取 / 被拦截")
    md.append("| 网站 | 原因 |")
    md.append("|---|---|")
    md.append("| PROXY.CC (proxy.cc) | 页面可打开，但数据接口 `proxy.cc/detection/proxyList` 返回403（需签名），浏览器渲染也为空 |")
    md.append("| FineProxy (fineproxy.org) | Cloudflare 人机验证死循环（403） |")
    md.append("| ProxyDB (proxydb.net) | 请求超时/无数据返回 |")
    md.append("| ProxyListFree (proxylistfree.com) | HTTP 522（源站宕机） |")
    md.append("| Stormsia GitHub | 仓库 `http.txt` 此刻为空文件（每30分钟重建），接口本身可用 |")
    md.append("| HideMyName / CometVPN / Socks5Proxies / ProxyO2 / FreeProxy.World | 页面可访问、能解析出代理，但抽样25个全部失效（多为SOCKS或已死亡节点） |")
    md.append("")
    md.append("## 三、参考程序（校园跑红色二合一）代理源验证结论")
    md.append("- 该程序默认源 `free-proxy-list.net/zh-cn/ssl-proxy.html`：**有效，可用率36%**，无需修改即可继续使用")
    md.append("- 该程序备用源 站大爷 zdopen API：**有效，可用率36%**")
    md.append("- 建议增加的高质量源：**ProxMint（64%）、ProxyNova（52%）**；ProxyScrape API 适合做大规模兜底池")
    md.append(f"- 本轮确认可用的 {len(confirmed)} 个代理已导出为 `free_proxy_list.txt`（一行一个 IP:PORT），可直接通过环境变量 `FREE_PROXY_LIST_FILE` 挂给程序使用")
    md.append("")
    md.append("## 四、风险提示")
    md.append("- 免费公共代理失效率极高（小时级），建议使用前每次重新拉取+筛选")
    md.append("- 不要通过免费代理传输账号密码/Cookie等敏感信息")
    md.append("- 校园跑类业务建议保持程序自带的探活校验逻辑（出口IP校验+HTTPS探活）")

    with open(os.path.join(BASE, "proxy_sites_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("report written: proxy_sites_report.md")
    print("top confirmed:", confirmed[:10])


if __name__ == "__main__":
    main()
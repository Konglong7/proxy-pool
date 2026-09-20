# -*- coding: utf-8 -*-
"""
proxy_pool.py — 免费动态代理IP池（开箱即用模块）
=================================================
来源：2026-08 对 20+ 免费代理网站实测后的可用源整合。
用法一（命令行，生成可用代理文件）：
    python proxy_pool.py                    # 抓取+验证，写入 working_proxies.txt
    python proxy_pool.py --min 20           # 至少验证出 20 个可用代理才停
    python proxy_pool.py --no-validate      # 只抓取不验证（速度快）
    python proxy_pool.py --out ./list.txt   # 自定义输出路径（相对路径即可）
用法二（代码内调用）：
    from proxy_pool import ProxyPool
    pool = ProxyPool()
    proxies = pool.get_working(min_count=5)   # -> ['1.2.3.4:8080', ...]
    pool.dump('proxies.txt')                  # 写文件（一行一个 IP:PORT）
依赖：requests + beautifulsoup4 + lxml；其它依赖均为 Python 标准库。验证目标默认 checkip.amazonaws.com。
"""
import os, re, sys, json, time, random, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import requests, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/json,text/plain,*/*;q=0.8",
           "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
CHECK_URL = "http://checkip.amazonaws.com/"
IPRE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})\Z")
IP_ONLY = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def http_get(url: str, timeout: int = 15, retries: int = 2):
    last = None
    for _ in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
            if r.status_code == 200 and r.text.strip():
                return r
            last = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:
            last = e
        time.sleep(1)
    raise last if last else RuntimeError("unreachable")


def _norm(ip, port):
    """规范化并校验 `ip:port`；不合法返回 None。

    这里是所有解析路径**唯一**的校验口径（避免“同一份数据换个表格布局结果不同”）：
    - IP 必须是 4 段点分十进制，且**每段都在 0-255 之间**（999.999.999.999 被拒）；
    - 端口必须是**数值 1-65535**（写法上仍要求 2-5 位数字，所以 `:8` / `:99999` 都不接受）；
    - 前导零按原样保留（`010.1.1.1:08080`），不做去零/补零改写 —— 既不丢弃也不编造；
    - 整串匹配（用 `\\Z` 而非 `$`，`$` 会放过尾随换行），脏输入如 `"8080\\n"` 直接拒绝。
    """
    s = f"{ip}:{port}"
    m = IPRE.match(s)
    if not m:
        return None
    if any(int(octet) > 255 for octet in m.group(1).split(".")):
        return None
    if not 1 <= int(m.group(2)) <= 65535:
        return None
    return s


def strip_comments(html: str) -> str:
    """剥离 HTML 注释 —— **防御性冗余**，不是唯一防线。

    实测：当前解析路径用的是 bs4 的 `get_text()` / `find_all()`，它们本来就不会返回
    注释里的内容，所以对正常 HTML 而言剥与不剥的解析结果完全一致，真正挡住
    “注释里塞假数据”的是 bs4 本身；唯一可观测的差异在 `<!-->` 这类畸形注释上
    （见 tests/test_parse.py::test_comment_region_created_by_abrupt_empty_comment_hides_fake_row）。
    保留它的意义是：一旦以后换成基于正则的原始 HTML 解析，这道防线仍然在
    （该“接线”契约由 tests/test_parse.py 固定）。请勿在文档里把它说成主要机制。
    """
    return re.sub(r"<!--[\s\S]*?-->", "", html)


def parse_html_tables(body: str) -> List[Dict]:
    """通用表格解析：支持 IP/Port 分列、单元格内 ip:port、'ip : port' 三种布局。"""
    soup = BeautifulSoup(strip_comments(body), "lxml")
    found = {}
    # 端口分组带 `(?!\d)` 右边界：`1.2.3.4:123456` 必须被**丢弃**，
    # 而不是被截成 `1.2.3.4:12345`（那等于凭空编造一个不存在的代理）。
    pair = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})\s*[:：]\s*(\d{2,5})(?!\d)")
    for tr in soup.find_all("tr"):
        texts = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        texts = [t for t in texts if t]
        for c in texts:  # 布局A：单元格内含 ip:port
            m = pair.search(c)
            if m:
                k = _norm(m.group(1), m.group(2))
                if k and k not in found:
                    found[k] = {"ip_port": k, "proto": "?"}
        for i, c in enumerate(texts):  # 布局B：独立IP列 + 数字端口列
            m = IP_ONLY.fullmatch(c.strip())
            if not m:
                continue
            for j in range(i + 1, min(len(texts), i + 6)):
                p = texts[j].strip()
                if p.isdigit() and 1 <= int(p) <= 65535:
                    k = _norm(m.group(0), p)
                    if k and k not in found:
                        found[k] = {"ip_port": k, "proto": "?"}
                    break
    return list(found.values())

# ==================== 各源抓取函数（均为实测可用源） ====================

def fetch_proxmint() -> List[Dict]:
    """ProxMint — 实测可用率最高(64%)，纯HTTP代理，页面直出。"""
    try:
        r = http_get("https://proxmint.com/free-proxies/http", timeout=30)
        return parse_html_tables(r.text)
    except Exception:
        return []


def fetch_fpln() -> List[Dict]:
    """free-proxy-list.net — 校园跑程序默认源，HTML表格直出，含SSL页。"""
    out = []
    for url in ("https://free-proxy-list.net/", "https://free-proxy-list.net/zh-cn/ssl-proxy.html"):
        try:
            out.extend(parse_html_tables(http_get(url, timeout=25).text))
        except Exception:
            pass
    return out


def fetch_zdopen() -> List[Dict]:
    """站大爷 zdopen 免费API（需自行注册申请 app_id/akey）。

    凭据通过环境变量注入，仓库内不含任何真实凭据：
        ZDOPEN_APP_ID / ZDOPEN_AKEY
    """
    app_id = os.environ.get("ZDOPEN_APP_ID", "").strip()
    akey = os.environ.get("ZDOPEN_AKEY", "").strip()
    if not app_id or not akey:
        # 未配置凭据则跳过该源（其它 7 个源不受影响）
        return []
    try:
        u = ("http://www.zdopen.com/FreeProxy/Get/?app_id={}&akey={}"
             "&dalu=0&protocol_type=4&return_type=3").format(app_id, akey)
        r = http_get(u, timeout=25)
        out = []
        for it in r.json().get("data", {}).get("proxy_list", []):
            k = _norm(it.get("ip"), it.get("port"))
            if k:
                out.append({"ip_port": k, "proto": str(it.get("protocol", "")).upper()})
        return out
    except Exception:
        return []


def fetch_proxyscrape() -> List[Dict]:
    """ProxyScrape v4 API — 量大（2万+），最适合批量兜底。"""
    out = []
    for u in ("https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies"
              "&proxy_format=ipport&format=text&protocol=http&timeout=8000",
              "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all"):
        try:
            for line in http_get(u, timeout=20).text.strip().splitlines():
                m = IPRE.fullmatch(line.strip())
                if m:
                    # 走 _norm 统一口径：越界端口（如 99999）同样在这里被丢掉
                    k = _norm(m.group(1), m.group(2))
                    if k:
                        out.append({"ip_port": k, "proto": "?"})
        except Exception:
            pass
    return out


def fetch_geonode() -> List[Dict]:
    """Geonode 官方API — JSON，带国家/匿名度/延迟元数据。"""
    try:
        r = http_get("https://proxylist.geonode.com/api/proxy-list?limit=300&page=1"
                     "&sort_by=lastChecked&sort_type=desc", timeout=25)
        out = []
        for it in r.json().get("data", []):
            protos = [p.lower() for p in it.get("protocols", [])]
            if not any(p in ("http", "https") for p in protos):
                continue
            k = _norm(it.get("ip"), it.get("port"))
            if k:
                out.append({"ip_port": k, "proto": "HTTPS" if "https" in protos else "HTTP"})
        return out
    except Exception:
        return []


def fetch_netvortex() -> List[Dict]:
    """NetVortex — 全量JSON缓存（2万+），无需鉴权。"""
    try:
        r = http_get("https://net-vortex.com/api/free_proxies.php", timeout=30)
        out = []
        for it in r.json().get("proxies", []):
            protos = [p.lower() for p in it.get("protocols", [])]
            if not any(p in ("http", "https") for p in protos):
                continue
            k = _norm(it.get("ip"), it.get("port"))
            if k:
                out.append({"ip_port": k, "proto": "HTTPS" if "https" in protos else "HTTP"})
        return out
    except Exception:
        return []


def fetch_databay() -> List[Dict]:
    """Databay 官方API /api/v1/proxy-list（每5分钟刷新）。"""
    try:
        r = http_get("https://databay.com/api/v1/proxy-list", timeout=30)
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", data.get("proxies", []))
        out = []
        for it in items:
            if isinstance(it, dict):
                k = _norm(it.get("ip") or it.get("ipAddress"), it.get("port"))
                if k:
                    out.append({"ip_port": k, "proto": "?"})
        return out
    except Exception:
        return []


def fetch_stormsia() -> List[Dict]:
    """Stormsia GitHub raw（每30分钟重建，可能瞬时为空，已做重试）。"""
    out = []
    for f in ("http.txt", "working_proxies.txt"):
        for _ in range(3):
            try:
                r = http_get(f"https://raw.githubusercontent.com/stormsia/proxy-list/main/{f}", timeout=20)
                if r.text.strip():
                    for line in r.text.splitlines():
                        m = re.match(r"^(?:https?|socks[45])://(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})\Z",
                                     line.strip())
                        if m:
                            # 同样经 _norm：越界端口/越界 IP 段一律丢弃
                            k = _norm(m.group(1), m.group(2))
                            if k:
                                out.append({"ip_port": k, "proto": "HTTP" if line.startswith("http") else "?"})
                    break
            except Exception:
                time.sleep(1)
    return out


FETCHERS = {
    "proxmint": fetch_proxmint,
    "free-proxy-list.net": fetch_fpln,
    "zdopen(站大爷)": fetch_zdopen,
    "proxyscrape": fetch_proxyscrape,
    "geonode": fetch_geonode,
    "netvortex": fetch_netvortex,
    "databay": fetch_databay,
    "stormsia": fetch_stormsia,
}

# ==================== 验证 ====================

def test_proxy(ip_port: str, timeout: int = 8, check_https: bool = True) -> Dict:
    """单代理验证：HTTP checkip 200且返回IP => 可用；再测HTTPS隧道。

    `err` 字段只描述**失败原因**，成功时保持空串；填值时的语义：
    - `HTTP <code>`：HTTP 一跳没拿到 200；
    - `no IP in body (HTTP 200)`：拿到了 200 但响应体里没有 IP（被换成了门户页等）；
    - `HTTPS <原因>`：HTTP 通了，但 HTTPS 隧道这一跳失败（`<原因>` 为
      `no IP in body (HTTP 200)` / `HTTP <code>` / 异常类名）。
    """
    rec = {"ip_port": ip_port, "http_ok": False, "https_ok": False, "exit_ip": "", "ms": 0, "err": ""}
    proxies = {"http": f"http://{ip_port}", "https": f"http://{ip_port}"}
    t0 = time.time()
    try:
        r = requests.get(CHECK_URL, proxies=proxies, timeout=timeout, headers={"User-Agent": UA}, verify=False)
        if r.status_code == 200:
            m = IP_ONLY.search(r.text or "")
            if m:
                rec["http_ok"] = True
                rec["exit_ip"] = m.group(0)
                if check_https:
                    try:
                        r2 = requests.get("https://checkip.amazonaws.com/", proxies=proxies,
                                          timeout=timeout, headers={"User-Agent": UA}, verify=False)
                        if r2.status_code == 200 and IP_ONLY.search(r2.text or ""):
                            rec["https_ok"] = True
                        elif r2.status_code == 200:
                            rec["err"] = "HTTPS no IP in body (HTTP 200)"
                        else:
                            rec["err"] = f"HTTPS HTTP {r2.status_code}"
                    except Exception as e2:
                        rec["err"] = f"HTTPS {type(e2).__name__}"
                rec["ms"] = int((time.time() - t0) * 1000)
                return rec
            rec["err"] = "no IP in body (HTTP 200)"
        else:
            rec["err"] = f"HTTP {r.status_code}"
    except Exception as e:
        rec["err"] = type(e).__name__
    return rec


class ProxyPool:
    """聚合多源抓取 + 并发验证的代理池。"""

    def __init__(self, sources=None, timeout: int = 8, workers: int = 50,
                 max_per_source: int = 200, verbose: bool = True):
        # 只有 `sources is None`（未指定）才回退成全部源；显式传 `[]` 表示“一个源都不抓”。
        self.sources = list(FETCHERS.keys()) if sources is None else list(sources)
        self.timeout = timeout
        self.workers = workers
        self.max_per_source = max_per_source
        self.verbose = verbose

    def _log(self, msg):
        if self.verbose:
            print(msg, flush=True)

    def fetch_all(self) -> Dict[str, List[Dict]]:
        """并发抓取所有源，返回 {源名: [ {ip_port, proto}, ... ]}。"""
        if ("zdopen(站大爷)" in self.sources
                and not (os.environ.get("ZDOPEN_APP_ID", "").strip()
                         and os.environ.get("ZDOPEN_AKEY", "").strip())):
            self._log("[skip] zdopen(站大爷)：未设置 ZDOPEN_APP_ID/ZDOPEN_AKEY，已跳过该源")
        unknown = [s for s in self.sources if s not in FETCHERS]
        if unknown:
            self._log(f"[warn] 未注册的源名被忽略：{', '.join(map(str, unknown))}"
                      f"（可用源：{', '.join(FETCHERS)}）")
        result = {}
        # self.sources 可能为空（显式传 []），max_workers 必须 >= 1
        with ThreadPoolExecutor(max_workers=max(1, len(self.sources))) as ex:
            futs = {ex.submit(FETCHERS[s]): s for s in self.sources if s in FETCHERS}
            for fut in as_completed(futs):
                name = futs[fut]
                try:
                    items = fut.result()[: self.max_per_source]
                except Exception:
                    items = []
                result[name] = items
                self._log(f"[fetch] {name:22s} -> {len(items)}")
        return result

    def validate(self, candidates: List[str], check_https: bool = True) -> List[Dict]:
        """并发验证候选代理，返回可用的记录列表（按延迟升序）。"""
        uniq = list(dict.fromkeys(candidates))
        ok = []
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {ex.submit(test_proxy, ip, self.timeout, check_https): ip for ip in uniq}
            for i, fut in enumerate(as_completed(futs), 1):
                rec = fut.result()
                if rec["http_ok"]:
                    ok.append(rec)
                if i % 50 == 0:
                    self._log(f"[validate] {i}/{len(uniq)} 可用{len(ok)}")
        ok.sort(key=lambda r: r["ms"])
        return ok

    def get_working(self, min_count: int = 10, rounds: int = 3, check_https: bool = True) -> List[str]:
        """抓取+验证；不足 min_count 自动重抓（最多 rounds 轮）。返回 IP:PORT 列表。"""
        got: List[str] = []
        for rd in range(1, rounds + 1):
            data = self.fetch_all()
            cands = []
            for items in data.values():
                cands.extend(it["ip_port"] for it in items)
            cands = [c for c in cands if c not in set(got)]
            random.shuffle(cands)
            self._log(f"[round {rd}] 候选 {len(cands)}，开始验证 ...")
            got.extend(r["ip_port"] for r in self.validate(cands, check_https))
            got = list(dict.fromkeys(got))
            if len(got) >= min_count:
                break
        self._log(f"[done] 可用代理 {len(got)} 个")
        return got

    @staticmethod
    def dump(proxies: List[str], path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(proxies))
        print(f"saved {len(proxies)} -> {path}")


def main():
    ap = argparse.ArgumentParser(description="免费动态代理IP池")
    ap.add_argument("--out", default="working_proxies.txt", help="输出文件（一行一个IP:PORT）")
    ap.add_argument("--min", type=int, default=10, help="最少验证出多少个可用代理")
    ap.add_argument("--rounds", type=int, default=3, help="最多抓取轮数")
    ap.add_argument("--no-validate", action="store_true", help="只抓取不验证")
    ap.add_argument("--no-https", action="store_true", help="跳过HTTPS隧道检测（更快）")
    ap.add_argument("--json", default="", help="同时输出详细JSON（含延迟/出口IP）")
    args = ap.parse_args()

    pool = ProxyPool()
    if args.no_validate:
        data = pool.fetch_all()
        ips = list(dict.fromkeys(ip for items in data.values() for ip in
                                 (it["ip_port"] for it in items)))
        ProxyPool.dump(ips, args.out)
        return

    working = pool.get_working(min_count=args.min, rounds=args.rounds,
                               check_https=not args.no_https)
    if working:
        ProxyPool.dump(working, args.out)
    if args.json:
        recs = pool.validate(working, check_https=not args.no_https)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(recs, f, ensure_ascii=False, indent=1)
    if not working:
        sys.exit(1)


if __name__ == "__main__":
    main()
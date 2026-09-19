# 动态代理IP 快速接入指南

> 基于 2026-08-30 对 20+ 免费代理网站的实测结果整理。所有接口均经过真实抓取 + 代理连通性双重验证（HTTP + HTTPS）。
> 配套工具：`proxy_pool.py`（开箱即用代理池模块）、`explore/`（建站期探查脚本）。

---

## 一、结论速查表（30秒看完）

| 优先级 | 来源 | 可用率* | 接入方式 | 更新频率 | 接入难度 |
|---|---|---|---|---|---|
| ⭐⭐⭐ | ProxMint | 64% | HTML表格解析 | 30分钟 | 简单 |
| ⭐⭐⭐ | ProxyNova | 52% | HTML+JS混淆解码 | 60秒 | 中等 |
| ⭐⭐⭐ | 站大爷 zdopen API | 36% | JSON API | 实时 | 极简单 |
| ⭐⭐⭐ | free-proxy-list.net | 36% | HTML表格解析 | 10分钟 | 极简单 |
| ⭐⭐⭐ | ProxyScrape API | 32% | 纯文本API（2万+） | 每分钟 | 极简单 |
| ⭐⭐ | Scrappey | 28% | HTML表格解析 | 每小时 | 简单 |
| ⭐⭐ | advanced.name | 28% | 需浏览器渲染 | 15分钟 | 中等 |
| ⭐⭐ | Spys.one | 20% | HTML+XOR混淆解码 | 实时 | 较难 |
| ⭐ | Databay API | 12% | JSON API | 5分钟 | 极简单 |
| ⭐ | Geonode / NetVortex API | 8% | JSON API（量大） | 持续 | 极简单 |
| ⭐ | ProxySale / ProxyMix | 12%/8% | 需浏览器渲染 | — | 中等 |

\* 可用率 = 通过代理成功请求 checkip.amazonaws.com 的比例（8秒超时）。免费代理失效率高，此数据仅代表当日实测，**每次使用前应重新验证**。

**建议组合**：`ProxMint + free-proxy-list.net + zdopen + ProxyScrape` 四源聚合（proxy_pool.py 已内置），正常情况 1 分钟可验证出 **200+ 个可用代理**（实测 245 个）。

---

## 二、最快接入路径（5分钟）

直接使用本项目提供的代理池模块 `proxy_pool.py`（依赖 requests + beautifulsoup4 + lxml）：

```bash
# 方式1：命令行 —— 抓取+验证+输出文件
python proxy_pool.py --min 20 --out working_proxies.txt

# 常用参数
python proxy_pool.py --min 20 --rounds 3      # 不足20个自动重抓（最多3轮）
python proxy_pool.py --no-https               # 跳过HTTPS检测，速度更快
python proxy_pool.py --no-validate            # 只抓取不验证（秒出几千个）
python proxy_pool.py --json detail.json       # 同时输出带延迟/出口IP的JSON
```

```python
# 方式2：代码内调用
from proxy_pool import ProxyPool

pool = ProxyPool()
proxies = pool.get_working(min_count=10)   # 返回 ['1.2.3.4:8080', ...] 按延迟升序
pool.dump(proxies, 'proxies.txt')          # 写文件，一行一个 IP:PORT

# 只要某个源：
pool2 = ProxyPool(sources=["proxmint", "zdopen(站大爷)"])
```

实测输出（2026-08-30）：
```
[fetch] zdopen(站大爷)  -> 100    [fetch] proxmint -> 50
[fetch] geonode -> 196            [fetch] netvortex -> 200
[fetch] proxyscrape -> 200        [fetch] free-proxy-list.net -> 200
[round 1] 候选 1146，开始验证 ...
[done] 可用代理 245 个   （全程约1分钟）
```

---

## 三、各源详细接入说明

### 3.1 ProxMint —— 可用率最高（64%）⭐首选

- 页面：`https://proxmint.com/free-proxies/http`
- 格式：服务端直出 HTML 表格，无 JS 混淆
- 解析：IP 和端口在同一单元格 `209.174.97.162 : 5999 | http | United States | elite | 195ms`

```python
import requests, re
from bs4 import BeautifulSoup

def fetch_proxmint():
    r = requests.get("https://proxmint.com/free-proxies/http",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30, verify=False)
    soup = BeautifulSoup(re.sub(r"<!--[\s\S]*?-->", "", r.text), "lxml")
    out = []
    for tr in soup.find_all("tr"):
        for td in tr.find_all("td"):
            m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})\s*:\s*(\d{2,5})", td.get_text())
            if m:
                out.append(f"{m.group(1)}:{m.group(2)}")
    return list(dict.fromkeys(out))
```

- 注意：仅 HTTP 代理；页面约 50 个/页

### 3.2 站大爷 zdopen API —— 校园跑程序同款备用源

- 接口：`http://www.zdopen.com/FreeProxy/Get/?app_id=<ZDOPEN_APP_ID>&akey=<ZDOPEN_AKEY>&dalu=0&protocol_type=4&return_type=3`（凭据需自行注册申请，通过环境变量 `ZDOPEN_APP_ID` / `ZDOPEN_AKEY` 注入，仓库内不含真实凭据）
- 返回：JSON，`data.proxy_list[]`，每次 100 个
- 字段：`ip` / `port` / `adr`(地区) / `protocol`(http) / `level`(高匿/未知)

```python
r = requests.get(ZDOPEN_URL, timeout=15)
for it in r.json()["data"]["proxy_list"]:
    print(it["ip"], it["port"], it["protocol"], it["level"])
```

- 注意：同一 app_id 有调用间隔限制（参考程序设为 10 秒/次）；免费代理"速度与有效率毫无保障"（官方声明）

### 3.3 free-proxy-list.net —— 校园跑程序默认源（免解析JS）

- 页面：`https://free-proxy-list.net/`（通用）、`https://free-proxy-list.net/zh-cn/ssl-proxy.html`（SSL/HTTPS 专用，程序内置）
- 格式：纯 HTML 表格（IP、Port 分列，HTTPS 列为 yes/no），约 300 个
- 解析：任何 HTML 表格解析器均可；程序 `parse_free_proxy_html()` 已内置

```python
r = requests.get("https://free-proxy-list.net/zh-cn/ssl-proxy.html",
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
# 行结构: <tr><td>IP</td><td>PORT</td><td>国家</td>...<td>yes</td></tr>
```

- 优点：更新约每10分钟、无需处理JS；缺点：单页数量有限

### 3.4 ProxyScrape API —— 量最大（2万+），批量兜底首选

- 接口（v4，推荐）：
  `https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=http&timeout=8000`
- 接口（v2 兼容旧版）：
  `https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all`
- 返回：纯文本，一行一个 `IP:PORT`，**无需解析**

```python
r = requests.get(V4_URL, timeout=20)
proxies = [l.strip() for l in r.text.splitlines() if ":" in l]
```

- 可选参数：`protocol=http|https|socks4|socks5`、`country=cn,us`、`anonymity=elite`、`format=text|json|csv`
- GitHub 镜像（每5分钟）：`https://github.com/proxyscrape/free-proxy-list`
- 注意：量极大但单条质量一般，**必须配验证过滤**

### 3.5 Geonode API —— 元数据最全（国家/延迟/匿名度）

- 接口：`https://proxylist.geonode.com/api/proxy-list?limit=300&page=1&sort_by=lastChecked&sort_type=desc`
- 返回：`data[]`，字段 `ip` / `port` / `protocols[]` / `anonymityLevel` / `latency` / `upTime` / `country`

```python
d = requests.get(GEONODE_URL, timeout=25).json()
for it in d["data"]:
    if "http" in it["protocols"] or "https" in it["protocols"]:
        print(f'{it["ip"]}:{it["port"]}', it["anonymityLevel"], it["latency"], "ms")
```

### 3.6 NetVortex API —— 全量 JSON 缓存（2万+，无鉴权）

- 接口：`https://net-vortex.com/api/free_proxies.php`
- 返回：`{"updated_at":..., "proxies":[{"ip","port","country","anonymity","protocols":[...],"uptime",...}]}`
- 页面版（服务端直出200个）：`https://net-vortex.com/free-proxies`

### 3.7 Databay API —— 官方 REST（每5分钟刷新）

- 接口：`https://databay.com/api/v1/proxy-list`（Swagger 文档：`https://api.databay.com/swagger/index.html`）
- 实测可用率 12%，但接口规范、稳定

### 3.8 Stormsia GitHub raw —— 开源、免注册免限流

- `https://raw.githubusercontent.com/stormsia/proxy-list/main/http.txt`（另有 `socks4.txt` / `socks5.txt` / `working_proxies.txt`）
- 格式：一行一个，**带协议前缀**：`http://1.2.3.4:3128`（解析时需去掉前缀）
- 注意：每30分钟由验证守护进程重建文件，**可能瞬时为空**（HTTP 200 + 空内容），需重试逻辑

---

## 四、特殊源：JS混淆解码方案（现成脚本在 explore/）

部分高可用站点故意混淆 IP/端口，需要解码。**现成可运行的解码脚本**：

| 站点 | 混淆方式 | 解码脚本 | 依赖 |
|---|---|---|---|
| ProxyNova（52%可用） | IP 用 `atob()` + `repeat/substring` 拼接 | `explore/js_render.js`（Node vm 执行页面内联脚本并捕获 document.write）→ `explore/parse_rendered.py` 解析 | Node.js |
| Spys.one（20%可用） | 端口用 XOR 变量 + Dean Edwards packer | `explore/spys_eval4.js`（Node vm 先跑 packer 再逐行解端口） | Node.js |
| advanced.name / proxysale / proxymix | 表格由浏览器 JS 填充 | `explore/pw_fetch.py`（playwright 无头渲染，未随仓库保留） | playwright + chromium |
| proxy.cc | Nuxt SSR + 接口签名（`/detection/proxyList` 返回403） | **无公开解法**，放弃 | — |
| fineproxy.org | Cloudflare 人机验证死循环 | **无解**，放弃 | — |

ProxyNova 解码流程（如需接入）：
```bash
cd explore
# 1. 抓页面存到 raw/proxynova.html（fetchers.py 里有完整逻辑）
node js_render.js raw/proxynova.html out_pn.json   # Node 执行页面JS，捕获35个document.write
python parse_rendered.py                            # 重建渲染后HTML -> 提取 IP+端口
```

---

## 五、代理验证标准（重要！）

免费代理列表 **必须验证后使用**。本项目实测标准（与校园跑程序逻辑一致）：

```python
import requests, re, time
IPRE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")

def test_proxy(ip_port, timeout=8):
    proxies = {"http": f"http://{ip_port}", "https": f"http://{ip_port}"}
    try:
        t0 = time.time()
        r = requests.get("http://checkip.amazonaws.com/", proxies=proxies,
                         timeout=timeout, verify=False)
        if r.status_code == 200 and IPRE.search(r.text or ""):
            ok_http = True
            # 可选：再测 HTTPS 隧道（CONNECT）
            try:
                r2 = requests.get("https://checkip.amazonaws.com/", proxies=proxies,
                                  timeout=timeout, verify=False)
                ok_https = r2.status_code == 200
            except Exception:
                ok_https = False
            return {"ok": True, "https": ok_https, "ms": int((time.time()-t0)*1000)}
    except Exception:
        pass
    return {"ok": False}
```

要点：
1. **并发验证**：50 线程 + 8 秒超时，1000 个候选约 1 分钟
2. **双重验证**：HTTP 200 且返回真实出口 IP → HTTPS CONNECT 隧道（校园跑业务必须 HTTPS 可用）
3. **出口 IP 校验**（参考程序做法）：出口 IP 不能等于本机公网 IP、不能是内网地址
4. **坏代理冷却**：验证失败的 IP 缓存 24h 不再测试（参考程序 `FREE_PROXY_BAD_CACHE_FILE`）

---

## 六、与校园跑程序对接

参考程序 `校园跑红色二合一_站大爷代理版2.0.py` 的代理体系：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `PROXY_PROVIDER` | `free_list` | `free_list`=免费列表模式 |
| `FREE_PROXY_LIST_FILE` | （空） | **指定外部代理文件（一行一个 IP:PORT）→ 用本指南产出文件对接的最简方式** |
| （默认） | 程序同目录 `free_proxy_list.txt` | 不设环境变量时自动读取的同名文件 |
| `FREE_PROXY_SOURCE_URL` | `https://free-proxy-list.net/zh-cn/ssl-proxy.html` | 程序每 120s 自动刷新的远程源 |
| `FREE_PROXY_AUTO_UPDATE` | `1` | 远程源自动刷新开关 |
| `ZDOPEN_PROXY_API_URL` | 站大爷免费API | 备用源（见3.2） |
| `FREE_PROXY_FILTER_BEFORE_RUN` | `0` | `1`=跑前先全量筛选 |
| `FREE_PROXY_TEST_TIMEOUT_SECONDS` | `4` | 单代理测试超时 |

**推荐对接方式**（二选一）：
1. 定时任务：`python proxy_pool.py --min 30 --out <校园跑目录>/free_proxy_list.txt`（程序会自动读取同目录文件）
2. 设置 `FREE_PROXY_LIST_FILE=<项目根目录>\working_proxies.txt`

程序内置的 20 个硬编码代理在 `proxy_list = [...]`（约第 329 行），可整段替换为 `proxy_pool.py` 的最新产出。

---

## 七、不可用/受限站点清单（避免浪费时间）

| 站点 | 状态 | 具体原因 |
|---|---|---|
| proxy.cc | ❌ | 页面可打开，数据接口 `proxy.cc/detection/proxyList` 返回 403（签名保护），无头浏览器渲染也为空 |
| fineproxy.org | ❌ | Cloudflare 人机验证（403），无头浏览器也过不去 |
| proxydb.net | ❌ | 请求超时 / 404，无有效数据返回 |
| proxylistfree.com | ❌ | HTTP 522 源站宕机 |
| proxy5.net | ❌ | Cloudflare 403 |
| hide.mn / cometvpn / socks5proxies / proxyo2 / freeproxy.world | ⚠️ | 页面可访问、能解析出列表，但抽样全部失效（多为 SOCKS 协议或死节点；hide.mn 的 TXT 导出还需付费订阅） |

## 八、维护建议

1. **刷新节奏**：免费代理小时级失效。建议：每次业务运行前跑一次 `proxy_pool.py`；长期运行的业务用定时任务每 30~60 分钟刷新一次输出文件
2. **验证阈值**：HTTP 可用即可入池；校园跑等 HTTPS 业务要求 `https_ok=True`（`--no-https` 不要开）
3. **并发参数**：验证 50 线程 / 8 秒超时是实测平衡点；网络差可降到 30 线程 / 10 秒
4. **多源冗余**：proxy_pool.py 默认 8 源，任一源临时失效不影响整体（如 stormsia 瞬时空文件）
5. **失败缓存**：把验证失败的 IP 存入冷却名单（24h），避免重复浪费验证时间
6. **系统代理干扰**：本机如开着 Clash 等（127.0.0.1:7897），requests 会走系统代理抓源页面；若某源抓取异常，可尝试 `requests.get(url, proxies={"http": None, "https": None})` 直连

## 九、风险提示

- 免费公共代理由陌生第三方运营，**可能记录流量、注入内容**，严禁用于登录账号、支付、传输 Cookie/密码等敏感操作
- 免费代理 IP 大多已被主流网站风控标记，业务成功率另计
- 校园跑类业务务必保留程序自带的"出口 IP 校验 + HTTPS 探活"逻辑，不要直接信任列表
- 站大爷等平台声明：免费代理仅供学习测试，法律责任自负

---

## 附：项目文件索引

```
<项目根目录>\
├── README.md                    ← 项目说明
├── proxy_pool.py                ← 开箱即用代理池模块（8源聚合+验证）
├── requirements.txt             ← 运行依赖（requests / beautifulsoup4 / lxml）
├── docs\
│   └── INTEGRATION-GUIDE.md     ← 本文档
└── explore\                     ← 建站期对 20+ 代理源的反爬探查脚本（非运行时依赖）
    ├── README.md                ← 探查脚本说明
    ├── proxy_sites_report.md    ← 当日实测报告（24源详细数据）
    ├── fetchers.py              ← 代理源完整抓取器（含 playwright/node 特殊源）
    ├── main_collect.py          ← 批量验证脚本
    ├── make_report.py           ← 报告生成器
    ├── probe1.py / inspect*.py  ← 可达性/结构探查
    ├── js_render.js / spys_eval*.js / parse_rendered.py ← JS 混淆解码
    └── module_test.txt          ← 模块测试记录
```
# 免费代理IP网站可用性测试报告

- 测试时间：2026-08-30 04:53:22
- 测试方法：每个网站实际抓取代理列表 → 随机抽样（每站≤25个）→ 通过代理请求 `checkip.amazonaws.com`（HTTP+HTTPS 双重验证，8秒超时，50并发）
- 判定标准：HTTP 200 且返回出口IP；再测 HTTPS CONNECT 隧道能力
- 本轮共测 444 个代理，二次复验确认 51 个可用（已按延迟排序写入 confirmed_proxies.txt / free_proxy_list.txt）

## 一、网站可用性总表（按可用率排序）

| 排名 | 网站 | 获取方式 | 候选数 | 抽测 | HTTP可用 | HTTPS可用 | 可用率 | 平均延迟 | 复验可用 | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ProxMint (proxmint.com) | API/页面 | 50 | 25 | 16 | 15 | 64.0% | 3310ms | 16 | ✅ 推荐使用 |
| 2 | ProxyNova (proxynova.com) | API/页面 | 19 | 19 | 10 | 10 | 52.6% | 7547ms | 8 | ✅ 推荐使用 |
| 3 | 站大爷 zdopen.com API | API/页面 | 100 | 25 | 9 | 5 | 36.0% | 5482ms | 7 | ✅ 推荐使用 |
| 4 | free-proxy-list.net (含SSL页) | API/页面 | 200 | 25 | 9 | 3 | 36.0% | 5441ms | 6 | ✅ 推荐使用 |
| 5 | ProxyScrape API (proxyscrape.com) | API/页面 | 200 | 25 | 8 | 5 | 32.0% | 5933ms | 6 | ✅ 推荐使用 |
| 6 | Scrappey (scrappey.com) | API/页面 | 200 | 25 | 7 | 1 | 28.0% | 9126ms | 5 | ✅ 可用 |
| 7 | advanced.name | API/页面 | 175 | 25 | 7 | 3 | 28.0% | 8133ms | 2 | ✅ 可用 |
| 8 | Spys.one (spys.one) | API/页面 | 28 | 25 | 5 | 2 | 20.0% | 6700ms | 3 | ✅ 可用 |
| 9 | Databay API (databay.com) | API/页面 | 200 | 25 | 3 | 0 | 12.0% | 11349ms | 1 | ✅ 可用 |
| 10 | ProxySale (proxysale.biz) | API/页面 | 100 | 25 | 3 | 1 | 12.0% | 11249ms | 1 | ✅ 可用 |
| 11 | Geonode API (geonode.com) | API/页面 | 196 | 25 | 2 | 0 | 8.0% | 11845ms | 1 | ⚠️ 勉强可用 |
| 12 | NetVortex API (net-vortex.com) | API/页面 | 200 | 25 | 2 | 0 | 8.0% | 9755ms | 1 | ⚠️ 勉强可用 |
| 13 | ProxyMix (proxymix.net) | API/页面 | 100 | 25 | 2 | 0 | 8.0% | 13306ms | 1 | ⚠️ 勉强可用 |
| 14 | OpenProxyList (openproxylist.com) | API/页面 | 29 | 25 | 1 | 1 | 4.0% | 8500ms | 0 | ⚠️ 勉强可用 |
| 15 | Stormsia GitHub (stormsia.github.io) | — | 0 | 0 | 0 | 0 | 0% | 0ms | 0 | ❌ 无法获取代理 |
| 16 | HideMyName (hide.mn) | API/页面 | 64 | 25 | 0 | 0 | 0.0% | 0ms | 0 | ⚠️ 本轮抽样全部失效 |
| 17 | ProxyO2 (proxyo2.com) | API/页面 | 5 | 5 | 0 | 0 | 0.0% | 0ms | 0 | ⚠️ 本轮抽样全部失效 |
| 18 | CometVPN (cometvpn.com) | API/页面 | 20 | 20 | 0 | 0 | 0.0% | 0ms | 0 | ⚠️ 本轮抽样全部失效 |
| 19 | Socks5Proxies (socks5proxies.com) | API/页面 | 25 | 25 | 0 | 0 | 0.0% | 0ms | 0 | ⚠️ 本轮抽样全部失效 |
| 20 | PROXY.CC (proxy.cc) | — | 0 | 0 | 0 | 0 | 0% | 0ms | 0 | ❌ 无法获取代理 |
| 21 | ProxyDB (proxydb.net) | — | 0 | 0 | 0 | 0 | 0% | 0ms | 0 | ❌ 无法获取代理 |
| 22 | FineProxy (fineproxy.org) | — | 0 | 0 | 0 | 0 | 0% | 0ms | 0 | ❌ 无法获取代理 |
| 23 | ProxyListFree (proxylistfree.com) | — | 0 | 0 | 0 | 0 | 0% | 0ms | 0 | ❌ 无法获取代理 |
| 24 | FreeProxy.World (freeproxy.world) | API/页面 | 50 | 25 | 0 | 0 | 0.0% | 0ms | 0 | ⚠️ 本轮抽样全部失效 |

## 二、重点说明

### ✅ 强烈推荐（API直连，适合脚本自动拉取）
1. **ProxMint** `https://proxmint.com/free-proxies/http` — 可用率64%（本轮最高），纯HTTP代理，页面直接渲染
2. **ProxyNova** `https://www.proxynova.com/proxy-server-list/` — 可用率52.6%，但IP经过JS混淆（atob），需解码或浏览器渲染
3. **站大爷 zdopen.com API**（参考校园跑程序同款）— 可用率36%，JSON API 稳定，返回100个/次
4. **free-proxy-list.net**（校园跑程序默认源 `https://free-proxy-list.net/zh-cn/ssl-proxy.html`）— 可用率36%，纯HTML表格无需解析JS
5. **ProxyScrape API** `https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text` — 可用率32%，量大（2万+），最适合批量脚本
6. **Scrappey / advanced.name / Spys.one** — 20-28%可用率；advanced.name 与 proxysale/proxymix 同模板，需浏览器渲染表格

### 🟡 可用但需要浏览器渲染/解析 effort 较高
- Databay（官方API `https://databay.com/api/v1/proxy-list` 可直接调用）、ProxySale、ProxyMix、Geonode API、NetVortex API（`/api/free_proxies.php` 全量2万+JSON）、OpenProxyList

### ❌ 无法获取 / 被拦截
| 网站 | 原因 |
|---|---|
| PROXY.CC (proxy.cc) | 页面可打开，但数据接口 `proxy.cc/detection/proxyList` 返回403（需签名），浏览器渲染也为空 |
| FineProxy (fineproxy.org) | Cloudflare 人机验证死循环（403） |
| ProxyDB (proxydb.net) | 请求超时/无数据返回 |
| ProxyListFree (proxylistfree.com) | HTTP 522（源站宕机） |
| Stormsia GitHub | 仓库 `http.txt` 此刻为空文件（每30分钟重建），接口本身可用 |
| HideMyName / CometVPN / Socks5Proxies / ProxyO2 / FreeProxy.World | 页面可访问、能解析出代理，但抽样25个全部失效（多为SOCKS或已死亡节点） |

## 三、参考程序（校园跑红色二合一）代理源验证结论
- 该程序默认源 `free-proxy-list.net/zh-cn/ssl-proxy.html`：**有效，可用率36%**，无需修改即可继续使用
- 该程序备用源 站大爷 zdopen API：**有效，可用率36%**
- 建议增加的高质量源：**ProxMint（64%）、ProxyNova（52%）**；ProxyScrape API 适合做大规模兜底池
- 本轮确认可用的 51 个代理已导出为 `free_proxy_list.txt`（一行一个 IP:PORT），可直接通过环境变量 `FREE_PROXY_LIST_FILE` 挂给程序使用

## 四、风险提示
- 免费公共代理失效率极高（小时级），建议使用前每次重新拉取+筛选
- 不要通过免费代理传输账号密码/Cookie等敏感信息
- 校园跑类业务建议保持程序自带的探活校验逻辑（出口IP校验+HTTPS探活）
# explore/ —— 建站期反爬探查脚本（非运行时依赖）

这里的脚本是 2026-08 建站期，对 20+ 个免费代理站点做**反爬探查与结构分析**时留下的工作底稿。
它们**不是运行时依赖**：`proxy_pool.py` 本身只依赖 `requests` / `beautifulsoup4` / `lxml`，
不需要本目录下的任何文件。保留这些脚本的目的，是展示当时的探查方法，以及几种 JS 混淆解码思路。

## 不能开箱即跑

部分脚本依赖已从仓库移除的抓取快照与数据文件（`raw/*.html`、`collected.json`、
`results_raw.json`、`*_out.txt` 等），这些文件包含真实代理 IP 与第三方站点原始 HTML，
已按脱敏要求删除。因此本目录脚本**多数无法直接运行**，仅作方法参考：

- 依赖 `raw/` 快照的：`inspect_raw.py`、`inspect2.py`、`chk_spys8.py`、
  `chk_structures.py`、`grep_api.py`、`parse_rendered.py`、`js_render.js`
- 依赖已删除数据文件的：`make_report.py`（读 `collected.json` / `stats.json`）
- 会写入 `raw/` 或输出文件的：`probe1.py`、`main_collect.py`、`chk_*.py`、`dbg_retry.py`

## 环境变量

站大爷 zdopen 相关脚本（`fetchers.py`、`inspect_raw.py`、`probe1.py`）的 API 凭据已外置，
不在仓库中保留任何真实值；需自行注册申请后通过环境变量注入：

```
ZDOPEN_APP_ID=<你的 app_id>
ZDOPEN_AKEY=<你的 akey>
```

未设置时，依赖该源的脚本会打印 `SKIP` 提示并跳过，不影响其它源。

## 脚本一览

| 脚本 | 作用 |
|---|---|
| `fetchers.py` | 各代理源抓取器（含 zdopen API、github raw 等） |
| `probe1.py` | 批量探测站点/API 可达性，保存原始 HTML |
| `inspect_raw.py` / `inspect2.py` | 分析抓取到的 HTML 结构，设计解析规则 |
| `chk_structures.py` / `chk_spys8.py` | 表格/字段结构探查 |
| `grep_api.py` | 在页面里搜 API 端点（fetch/axios/NUXT 等） |
| `main_collect.py` | 批量抓取 + 验证 |
| `make_report.py` | 汇总生成实测报告（`proxy_sites_report.md`） |
| `js_render.js` / `parse_rendered.py` | Node vm 执行页面内联 JS，解码 ProxyNova 的 `atob()` 拼接 |
| `spys_eval*.js` | Spys.one 端口 XOR 变量 + Dean Edwards packer 解码 |
| `chk_api.py` / `chk_pcc.py` / `chk_pn.py` / `chk_pw.py` | 单站点接口/结构定点排查 |
| `dbg_retry.py` | 重试与直连（绕过系统代理）调试 |
| `proxy_sites_report.md` | 当日实测报告（24 源详细数据） |
| `module_test.txt` | 模块自测记录 |

# -*- coding: utf-8 -*-
"""抓取编排层单元测试：源注册表 / zdopen 缺凭据降级 / fetch_all / get_working / dump。

全部离线：`http_get` 与 `FETCHERS` 都被 monkeypatch 替换（conftest 里还有全局网络护栏）。
"""
import pytest

import proxy_pool
from proxy_pool import ProxyPool

# 假凭据：仅用于断言 URL 拼接，不含任何真实值
FAKE_APP_ID = "fake-app-id-0000"
FAKE_AKEY = "f" * 32

README_SOURCE_KEYS = {
    "proxmint",
    "free-proxy-list.net",
    "zdopen(站大爷)",
    "proxyscrape",
    "geonode",
    "netvortex",
    "databay",
    "stormsia",
}


class FakeTextResponse:
    def __init__(self, text=""):
        self.text = text
        self.status_code = 200


class FakeJsonResponse(FakeTextResponse):
    def __init__(self, payload, text=""):
        super().__init__(text)
        self._payload = payload

    def json(self):
        return self._payload


def _items(*ip_ports):
    return [{"ip_port": ip, "proto": "?"} for ip in ip_ports]


# ============================================================================
# 源注册表
# ============================================================================

def test_fetchers_registry_is_exactly_eight_sources():
    assert isinstance(proxy_pool.FETCHERS, dict)
    assert len(proxy_pool.FETCHERS) == 8
    assert set(proxy_pool.FETCHERS) == README_SOURCE_KEYS


def test_every_registered_source_is_callable():
    for name, fn in proxy_pool.FETCHERS.items():
        assert callable(fn), name
        assert fn.__name__.startswith("fetch_"), name


def test_zdopen_is_registered_but_needs_credentials():
    """zdopen 必须在册（README 与 CI 都依赖这个 key 名），但缺凭据时降级为空。"""
    assert "zdopen(站大爷)" in proxy_pool.FETCHERS


def test_pool_with_empty_sources_fetches_nothing():
    """`sources=[]` 表示“一个源都不抓”（修复前被 `or` 当成假值，静默回退成全部 8 个源）。

    `fetch_all()` 也必须能承受空源列表（不能因为 max_workers=0 而抛异常）。
    """
    pool = ProxyPool(sources=[], verbose=False)

    assert pool.sources == []
    assert pool.fetch_all() == {}


def test_pool_with_none_sources_falls_back_to_all_registered_sources():
    """只有未指定（None）时才回退成全部源。"""
    pool = ProxyPool(verbose=False)

    assert pool.sources == list(proxy_pool.FETCHERS.keys())
    assert len(pool.sources) == 8


# ============================================================================
# fetch_zdopen：凭据缺失 / 凭据注入
# ============================================================================

def _clear_zdopen_env(monkeypatch):
    monkeypatch.delenv("ZDOPEN_APP_ID", raising=False)
    monkeypatch.delenv("ZDOPEN_AKEY", raising=False)


def test_fetch_zdopen_without_credentials_does_no_request(monkeypatch):
    _clear_zdopen_env(monkeypatch)
    # conftest 的护栏已让 http_get 抛异常，这里再显式记录一次调用
    called = []

    def boom(url, timeout=15):
        called.append(url)
        raise AssertionError("未配置凭据时不应发起网络请求")

    monkeypatch.setattr(proxy_pool, "http_get", boom)

    assert proxy_pool.fetch_zdopen() == []
    assert called == []


@pytest.mark.parametrize("app_id,akey", [
    ("", ""),
    ("only-app-id", ""),
    ("", "only-akey"),
    ("   ", "   "),          # 只有空白字符也视同未配置（实现里做了 .strip()）
])
def test_fetch_zdopen_partial_credentials_are_treated_as_missing(monkeypatch, app_id, akey):
    monkeypatch.setenv("ZDOPEN_APP_ID", app_id)
    monkeypatch.setenv("ZDOPEN_AKEY", akey)
    monkeypatch.setattr(proxy_pool, "http_get",
                        lambda url, timeout=15: pytest.fail("不应发起请求"))

    assert proxy_pool.fetch_zdopen() == []


def test_fetch_zdopen_with_credentials_builds_url_and_parses_json(monkeypatch):
    monkeypatch.setenv("ZDOPEN_APP_ID", FAKE_APP_ID)
    monkeypatch.setenv("ZDOPEN_AKEY", FAKE_AKEY)

    payload = {"data": {"proxy_list": [
        {"ip": "1.2.3.4", "port": "8080", "protocol": "http"},
        {"ip": "5.6.7.8", "port": 3128, "protocol": "https"},
        {"ip": "bad-ip", "port": "8080"},          # _norm 过滤
        {"ip": "9.9.9.9"},                         # 缺 port -> _norm 过滤
        {"ip": "7.7.7.7", "port": "8"},            # 1 位端口 -> _norm 过滤
    ]}}
    seen = {}

    def fake_http_get(url, timeout=15):
        seen["url"] = url
        seen["timeout"] = timeout
        return FakeJsonResponse(payload)

    monkeypatch.setattr(proxy_pool, "http_get", fake_http_get)

    out = proxy_pool.fetch_zdopen()

    assert out == [
        {"ip_port": "1.2.3.4:8080", "proto": "HTTP"},
        {"ip_port": "5.6.7.8:3128", "proto": "HTTPS"},
    ]
    assert "app_id=" + FAKE_APP_ID in seen["url"]
    assert "akey=" + FAKE_AKEY in seen["url"]
    assert seen["url"].startswith("http://www.zdopen.com/FreeProxy/Get/?")
    assert "dalu=0" in seen["url"] and "protocol_type=4" in seen["url"] and "return_type=3" in seen["url"]
    assert seen["timeout"] == 25


def test_fetch_zdopen_survives_unexpected_payload_shape(monkeypatch):
    monkeypatch.setenv("ZDOPEN_APP_ID", FAKE_APP_ID)
    monkeypatch.setenv("ZDOPEN_AKEY", FAKE_AKEY)
    monkeypatch.setattr(proxy_pool, "http_get",
                        lambda url, timeout=15: FakeJsonResponse({"code": 0}))

    assert proxy_pool.fetch_zdopen() == []


def test_fetch_zdopen_swallows_transport_errors(monkeypatch):
    monkeypatch.setenv("ZDOPEN_APP_ID", FAKE_APP_ID)
    monkeypatch.setenv("ZDOPEN_AKEY", FAKE_AKEY)

    def boom(url, timeout=15):
        raise ConnectionError("network down")

    monkeypatch.setattr(proxy_pool, "http_get", boom)

    assert proxy_pool.fetch_zdopen() == []


# ============================================================================
# 纯文本源的按行过滤（proxyscrape / stormsia：ip:port 每行一个）
# ============================================================================

def test_fetch_proxyscrape_keeps_only_lines_with_valid_ip_port(monkeypatch):
    body = ("1.2.3.4:8080\n"
            "99.99.99.99:99999\n"      # 越界端口 -> 经 _norm 丢弃（修复前会被当成候选）
            "https://5.6.7.8:3128\n"   # 带协议前缀 -> IPRE 不匹配
            "9.9.9.9\n"                # 只有 IP
            "7.7.7.7:80\n"
            "\n")
    seen = []

    def fake_http_get(url, timeout=15):
        seen.append(url)
        return FakeTextResponse(body)

    monkeypatch.setattr(proxy_pool, "http_get", fake_http_get)

    out = proxy_pool.fetch_proxyscrape()

    assert len(seen) == 2                      # 两个端点依次尝试
    # 每个端点产出相同的 2 条（带协议前缀、纯 IP、空行、越界端口都被丢弃）
    assert [r["ip_port"] for r in out] == ["1.2.3.4:8080", "7.7.7.7:80"] * 2
    assert {r["proto"] for r in out} == {"?"}


def test_fetch_stormsia_strips_scheme_prefix_and_drops_out_of_range_port(monkeypatch):
    body = ("http://1.2.3.4:8080\n"
            "https://5.6.7.8:3128\n"
            "socks5://9.9.9.9:99999\n"     # 越界端口 -> 经 _norm 丢弃
            "not-a-proxy\n")
    seen = []

    def fake_http_get(url, timeout=15):
        seen.append(url)
        return FakeTextResponse(body)

    monkeypatch.setattr(proxy_pool, "http_get", fake_http_get)

    out = proxy_pool.fetch_stormsia()

    # 依次尝试两个文件，各自第一次成功即停止重试
    assert seen == [
        "https://raw.githubusercontent.com/stormsia/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/main/working_proxies.txt",
    ]
    assert [(r["ip_port"], r["proto"]) for r in out] == [
        ("1.2.3.4:8080", "HTTP"),
        ("5.6.7.8:3128", "HTTP"),
    ] * 2


# ============================================================================
# fetch_all
# ============================================================================

def test_fetch_all_swallows_failing_source_and_keeps_the_rest(monkeypatch):
    def good():
        return _items("1.1.1.1:8080", "2.2.2.2:8080")

    def bad():
        raise RuntimeError("源挂了")

    monkeypatch.setattr(proxy_pool, "FETCHERS", {"good": good, "bad": bad})

    data = ProxyPool(sources=["good", "bad"], verbose=False).fetch_all()

    assert set(data) == {"good", "bad"}
    assert data["bad"] == []                                   # 异常被吞掉，降级为空列表
    assert [r["ip_port"] for r in data["good"]] == ["1.1.1.1:8080", "2.2.2.2:8080"]


def test_fetch_all_applies_max_per_source(monkeypatch):
    def good():
        return _items(*[f"10.0.0.{i}:8080" for i in range(10)])

    monkeypatch.setattr(proxy_pool, "FETCHERS", {"good": good})

    data = ProxyPool(sources=["good"], max_per_source=3, verbose=False).fetch_all()

    assert len(data["good"]) == 3
    assert [r["ip_port"] for r in data["good"]] == ["10.0.0.0:8080", "10.0.0.1:8080",
                                                   "10.0.0.2:8080"]


def test_fetch_all_only_runs_configured_sources(monkeypatch):
    calls = []

    def make(name):
        def _f():
            calls.append(name)
            return _items(f"{name}:80")
        return _f

    monkeypatch.setattr(proxy_pool, "FETCHERS", {"a": make("a"), "b": make("b")})

    data = ProxyPool(sources=["b"], verbose=False).fetch_all()

    assert calls == ["b"]
    assert set(data) == {"b"}


def test_fetch_all_warns_about_unknown_source_name(monkeypatch, capsys):
    """修复前：self.sources 里不在 FETCHERS 的名字被**静默**忽略，用户会误以为“该源返回 0 条”。

    现在会打一行 `[warn]`，结果里依旧不会出现该 key（无该源可抓）。
    """
    monkeypatch.setattr(proxy_pool, "FETCHERS", {"a": lambda: _items("1.1.1.1:80")})

    data = ProxyPool(sources=["a", "ghost"], verbose=True).fetch_all()

    out = capsys.readouterr().out
    assert "[warn]" in out
    assert "ghost" in out
    assert set(data) == {"a"}


def test_fetch_all_unknown_source_warning_is_silenced_when_verbose_false(monkeypatch, capsys):
    """verbose=False 时不打印任何东西（_log 的既有语义不变）。"""
    monkeypatch.setattr(proxy_pool, "FETCHERS", {"a": lambda: _items("1.1.1.1:80")})

    data = ProxyPool(sources=["ghost"], verbose=False).fetch_all()

    assert capsys.readouterr().out == ""
    assert data == {}


def test_fetch_all_logs_zdopen_skip_when_credentials_missing(monkeypatch, capsys):
    _clear_zdopen_env(monkeypatch)

    data = ProxyPool(sources=["zdopen(站大爷)"], verbose=True).fetch_all()

    out = capsys.readouterr().out
    assert "[skip]" in out
    assert "ZDOPEN_APP_ID" in out and "ZDOPEN_AKEY" in out
    assert data == {"zdopen(站大爷)": []}          # 真跑 fetch_zdopen，缺凭据返回空且不联网


def test_fetch_all_is_silent_when_verbose_false(monkeypatch, capsys):
    def good():
        return _items("1.1.1.1:80")

    monkeypatch.setattr(proxy_pool, "FETCHERS", {"good": good})

    ProxyPool(sources=["good"], verbose=False).fetch_all()

    assert capsys.readouterr().out == ""


# ============================================================================
# get_working：多轮补足
# ============================================================================

def test_get_working_stops_after_first_round_when_min_count_reached(monkeypatch):
    rounds = []

    def fake_fetch_all():
        rounds.append(1)
        return {"s": _items("1.1.1.1:80")}

    def fake_validate(cands, check_https=True):
        return [{"ip_port": ip, "http_ok": True, "ms": 10} for ip in cands]

    pool = ProxyPool(verbose=False)
    monkeypatch.setattr(pool, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pool, "validate", fake_validate)

    got = pool.get_working(min_count=1, rounds=3)

    assert got == ["1.1.1.1:80"]
    assert len(rounds) == 1                     # 凑够 min_count 立即结束
    assert len(got) == len(set(got))


def test_get_working_keeps_rounding_until_rounds_exhausted(monkeypatch):
    fetched = _items(*[f"10.0.0.{i}:8080" for i in range(4)])
    validate_calls = []

    def fake_fetch_all():
        return {"s": list(fetched)}

    def fake_validate(cands, check_https=True):
        validate_calls.append(sorted(cands))
        if len(validate_calls) == 1:
            return [{"ip_port": "10.0.0.0:8080", "http_ok": True, "ms": 10},
                    {"ip_port": "10.0.0.1:8080", "http_ok": True, "ms": 20}]
        # 第二轮故意把已获得的代理再返回一次
        return [{"ip_port": "10.0.0.0:8080", "http_ok": True, "ms": 10},
                {"ip_port": "10.0.0.2:8080", "http_ok": True, "ms": 30}]

    pool = ProxyPool(verbose=False)
    monkeypatch.setattr(pool, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pool, "validate", fake_validate)

    got = pool.get_working(min_count=5, rounds=2)

    assert len(validate_calls) == 2                                   # 两轮都跑了
    assert validate_calls[0] == [f"10.0.0.{i}:8080" for i in range(4)]
    # 第二轮候选里不再包含已获得的两个代理
    assert validate_calls[1] == ["10.0.0.2:8080", "10.0.0.3:8080"]
    # 重复返回的代理不会在结果里出现两次
    assert got == ["10.0.0.0:8080", "10.0.0.1:8080", "10.0.0.2:8080"]


def test_get_working_never_returns_duplicates_across_rounds(monkeypatch):
    def fake_fetch_all():
        return {"s": _items("5.5.5.5:8080", "6.6.6.6:8080")}

    def fake_validate(cands, check_https=True):
        return [{"ip_port": "5.5.5.5:8080", "http_ok": True, "ms": 10},
                {"ip_port": "6.6.6.6:8080", "http_ok": True, "ms": 20}]

    pool = ProxyPool(verbose=False)
    monkeypatch.setattr(pool, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pool, "validate", fake_validate)

    got = pool.get_working(min_count=99, rounds=3)

    assert got == ["5.5.5.5:8080", "6.6.6.6:8080"]
    assert len(got) == len(set(got))


def test_get_working_merges_candidates_from_all_sources(monkeypatch):
    seen_candidates = []

    def fake_fetch_all():
        return {"a": _items("1.1.1.1:80"), "b": _items("2.2.2.2:80")}

    def fake_validate(cands, check_https=True):
        seen_candidates.append(sorted(cands))
        return []

    pool = ProxyPool(verbose=False)
    monkeypatch.setattr(pool, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pool, "validate", fake_validate)

    assert pool.get_working(min_count=1, rounds=1) == []
    assert seen_candidates == [["1.1.1.1:80", "2.2.2.2:80"]]


def test_get_working_passes_check_https_to_validate(monkeypatch):
    seen = {}

    def fake_fetch_all():
        return {"s": _items("1.1.1.1:80")}

    def fake_validate(cands, check_https=True):
        seen["check_https"] = check_https
        return []

    pool = ProxyPool(verbose=False)
    monkeypatch.setattr(pool, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pool, "validate", fake_validate)

    pool.get_working(min_count=1, rounds=1, check_https=False)

    assert seen["check_https"] is False


def test_get_working_always_runs_at_least_one_round(monkeypatch):
    """现状：min_count=0 时也会先跑一轮（round 循环是 for，不做前置判断）。"""
    rounds = []

    def fake_fetch_all():
        rounds.append(1)
        return {"s": []}

    pool = ProxyPool(verbose=False)
    monkeypatch.setattr(pool, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(pool, "validate", lambda cands, check_https=True: [])

    assert pool.get_working(min_count=0, rounds=3) == []
    assert len(rounds) == 1


# ============================================================================
# dump
# ============================================================================

def test_dump_writes_one_proxy_per_line(tmp_path, capsys):
    target = tmp_path / "working_proxies.txt"

    ProxyPool.dump(["1.2.3.4:8080", "5.6.7.8:3128"], str(target))

    assert target.read_text(encoding="utf-8") == "1.2.3.4:8080\n5.6.7.8:3128"
    assert "saved 2" in capsys.readouterr().out


def test_dump_of_empty_list_creates_empty_file(tmp_path, capsys):
    target = tmp_path / "empty.txt"

    ProxyPool.dump([], str(target))

    assert target.exists()
    assert target.read_text(encoding="utf-8") == ""
    assert "saved 0" in capsys.readouterr().out


def test_dump_round_trip_reads_back_as_list(tmp_path):
    ips = ["9.9.9.9:1080", "8.8.8.8:80"]

    ProxyPool.dump(ips, str(tmp_path / "out.txt"))

    content = (tmp_path / "out.txt").read_text(encoding="utf-8")
    assert content.split("\n") == ips
    assert not content.endswith("\n")     # 现状：无尾随换行

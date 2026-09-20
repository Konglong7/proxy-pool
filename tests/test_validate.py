# -*- coding: utf-8 -*-
"""验证层单元测试：`test_proxy()` 与 `ProxyPool.validate()`。

全部离线：用 monkeypatch 替换 `requests.get`（以及 conftest 里的全局网络护栏），
断言的是真实实现里的具体行为 —— 双协议语义、错误字段、调用次数、排序与去重。
"""
import time

import pytest
import requests

import proxy_pool
from proxy_pool import CHECK_URL, UA, ProxyPool

# 注意：不能写成 `from proxy_pool import test_proxy` —— 该名字以 test_ 开头，
# 会被 pytest 收集成测试函数（报 fixture 'ip_port' not found）。用别名绕开。
verify_proxy = proxy_pool.test_proxy


class FakeResponse:
    """requests.Response 的最小替身（test_proxy 只用到 status_code / text）。"""

    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def patch_requests_get(monkeypatch, handler):
    """替换 requests.get，返回调用记录列表（每项含 url 与 kwargs）。"""
    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return handler(url, kwargs)

    monkeypatch.setattr(proxy_pool.requests, "get", fake_get)
    return calls


def handler_const(status_code=200, text="", delay=0.0, exc=None):
    def _h(url, kwargs):
        if delay:
            time.sleep(delay)
        if exc is not None:
            raise exc
        return FakeResponse(status_code, text)
    return _h


# ============================================================================
# test_proxy：单代理验证
# ============================================================================

def test_http_ok_sets_exit_ip_and_ms(monkeypatch):
    calls = patch_requests_get(monkeypatch, handler_const(200, "203.0.113.7\n", delay=0.02))

    rec = verify_proxy("10.0.0.1:3128", timeout=1, check_https=False)

    assert rec["ip_port"] == "10.0.0.1:3128"
    assert rec["http_ok"] is True
    assert rec["https_ok"] is False          # check_https=False 时不检测 HTTPS
    assert rec["exit_ip"] == "203.0.113.7"   # 从响应体里提取出口 IP
    assert rec["err"] == ""
    assert isinstance(rec["ms"], int) and rec["ms"] >= 10   # 真实测量了耗时
    # 网络调用只发生一次，且请求被正确指向检查 URL 与该代理
    assert len(calls) == 1
    assert calls[0]["url"] == CHECK_URL
    assert calls[0]["kwargs"]["proxies"] == {"http": "http://10.0.0.1:3128",
                                             "https": "http://10.0.0.1:3128"}
    assert calls[0]["kwargs"]["timeout"] == 1
    assert calls[0]["kwargs"]["headers"] == {"User-Agent": UA}
    assert calls[0]["kwargs"]["verify"] is False


def test_http_ok_without_ip_in_body_is_not_ok(monkeypatch):
    """200 但响应体里没有 IP（例如被换成了 HTML 门户页）→ 不算可用。

    修复前 `err` 写成 `"HTTP 200"`（看起来像成功），现在写成能说明情形的
    `"no IP in body (HTTP 200)"`。
    """
    patch_requests_get(monkeypatch, handler_const(200, "<html>portal</html>"))

    rec = verify_proxy("10.0.0.1:3128", check_https=False)

    assert rec["http_ok"] is False
    assert rec["exit_ip"] == ""
    assert rec["ms"] == 0
    assert rec["err"] == "no IP in body (HTTP 200)"


def test_non_200_sets_err_with_status_code(monkeypatch):
    for status in (403, 503, 500):
        patch_requests_get(monkeypatch, handler_const(status, "1.2.3.4"))
        rec = verify_proxy("10.0.0.1:3128", check_https=False)
        assert rec["http_ok"] is False
        assert rec["err"] == f"HTTP {status}"


def test_exception_sets_err_to_exception_class_name(monkeypatch):
    patch_requests_get(monkeypatch, handler_const(exc=requests.exceptions.ConnectTimeout("boom")))

    rec = verify_proxy("10.0.0.1:3128", check_https=False)

    assert rec["http_ok"] is False
    assert rec["https_ok"] is False
    assert rec["exit_ip"] == ""
    assert rec["ms"] == 0
    assert rec["err"] == "ConnectTimeout"    # 只记录异常类名，不带 message


def test_proxy_error_class_name_is_recorded(monkeypatch):
    patch_requests_get(monkeypatch, handler_const(exc=requests.exceptions.ProxyError("refused")))
    rec = verify_proxy("10.0.0.1:3128", check_https=False)
    assert rec["err"] == "ProxyError"

    patch_requests_get(monkeypatch, handler_const(exc=ValueError("weird")))
    rec2 = verify_proxy("10.0.0.1:3128", check_https=False)
    assert rec2["err"] == "ValueError"


def test_check_https_true_marks_https_tunnel_available(monkeypatch):
    """HTTP 与 HTTPS 都 200 且都回显 IP → 两个维度都为真。"""
    calls = patch_requests_get(monkeypatch, handler_const(200, "203.0.113.7\n", delay=0.05))

    rec = verify_proxy("10.0.0.1:3128", timeout=1, check_https=True)

    assert rec["http_ok"] is True
    assert rec["https_ok"] is True
    assert rec["exit_ip"] == "203.0.113.7"
    assert rec["ms"] >= 80                   # ms 覆盖 HTTP + HTTPS 两跳总耗时
    assert len(calls) == 2
    assert calls[0]["url"] == CHECK_URL                      # 第一次：明文 HTTP
    assert calls[1]["url"] == "https://checkip.amazonaws.com/"  # 第二次：HTTPS 隧道
    assert calls[1]["kwargs"]["proxies"] == calls[0]["kwargs"]["proxies"]
    assert rec["err"] == ""                  # 两条都成功时 err 保持空串


def test_check_https_true_but_https_fails_keeps_http_ok(monkeypatch):
    """双协议校验的核心语义：HTTPS 隧道挂了，http_ok 仍为真、https_ok 为假。

    `err` 会写明是 HTTPS 这一跳失败（修复前是空的、看不出发生了什么）。
    """
    def handler(url, kwargs):
        if url.startswith("https://"):
            raise requests.exceptions.ProxyError("CONNECT failed")
        time.sleep(0.02)
        return FakeResponse(200, "203.0.113.7\n")

    calls = patch_requests_get(monkeypatch, handler)

    rec = verify_proxy("10.0.0.1:3128", timeout=1, check_https=True)

    assert rec["http_ok"] is True
    assert rec["https_ok"] is False
    assert rec["exit_ip"] == "203.0.113.7"
    assert rec["err"] == "HTTPS ProxyError"   # 修复后：区分出是 HTTPS 隧道失败及原因
    assert rec["ms"] >= 10                   # 成功路径才填 ms，且把 HTTPS 那一跳也算进去


def test_check_https_true_but_https_body_has_no_ip(monkeypatch):
    """HTTPS 返回 200 但响应体里没有 IP → https_ok 仍为假，err 说明情形。"""
    def handler(url, kwargs):
        if url.startswith("https://"):
            return FakeResponse(200, "not an ip")
        return FakeResponse(200, "203.0.113.7\n")

    patch_requests_get(monkeypatch, handler)
    rec = verify_proxy("10.0.0.1:3128", check_https=True)

    assert rec["http_ok"] is True
    assert rec["https_ok"] is False
    assert rec["err"] == "HTTPS no IP in body (HTTP 200)"


def test_check_https_true_but_https_status_not_200(monkeypatch):
    def handler(url, kwargs):
        if url.startswith("https://"):
            return FakeResponse(403, "203.0.113.7\n")
        return FakeResponse(200, "203.0.113.7\n")

    patch_requests_get(monkeypatch, handler)
    rec = verify_proxy("10.0.0.1:3128", check_https=True)

    assert rec["http_ok"] is True
    assert rec["https_ok"] is False
    assert rec["err"] == "HTTPS HTTP 403"


def test_check_https_false_makes_exactly_one_request(monkeypatch):
    calls = patch_requests_get(monkeypatch, handler_const(200, "203.0.113.7\n"))

    rec = verify_proxy("10.0.0.1:3128", check_https=False)

    assert rec["http_ok"] is True and rec["https_ok"] is False
    assert len(calls) == 1
    assert all(c["url"] == CHECK_URL for c in calls)


def test_exit_ip_extraction_ignores_surrounding_text(monkeypatch):
    patch_requests_get(monkeypatch, handler_const(200, "  your ip is 198.51.100.42 \n\n"))
    rec = verify_proxy("10.0.0.1:3128", check_https=False)
    assert rec["exit_ip"] == "198.51.100.42"


# ============================================================================
# ProxyPool.validate
# ============================================================================

def _rec(ip_port, ok, ms, exit_ip="203.0.113.1"):
    return {"ip_port": ip_port, "http_ok": ok, "https_ok": ok,
            "exit_ip": exit_ip if ok else "", "ms": ms if ok else 0,
            "err": "" if ok else "HTTP 403"}


def test_validate_keeps_only_ok_and_sorts_by_latency(monkeypatch):
    table = {
        "a:1": _rec("a:1", True, 300),
        "b:1": _rec("b:1", False, 0),
        "c:1": _rec("c:1", True, 120),
        "d:1": _rec("d:1", True, 500),
    }
    seen = []

    def fake_test_proxy(ip_port, timeout, check_https):
        seen.append((ip_port, timeout, check_https))
        return table[ip_port]

    monkeypatch.setattr(proxy_pool, "test_proxy", fake_test_proxy)

    out = ProxyPool(timeout=3, workers=4, verbose=False).validate(
        ["a:1", "b:1", "c:1", "d:1"], check_https=False)

    assert [r["ip_port"] for r in out] == ["c:1", "a:1", "d:1"]   # 升序，失败项被剔除
    assert len(seen) == 4
    assert {t for _, t, _ in seen} == {3}            # self.timeout 被透传
    assert {h for _, _, h in seen} == {False}        # check_https 被透传


def test_validate_passes_check_https_true(monkeypatch):
    seen = []

    def fake_test_proxy(ip_port, timeout, check_https):
        seen.append(check_https)
        return _rec(ip_port, True, 10)

    monkeypatch.setattr(proxy_pool, "test_proxy", fake_test_proxy)

    ProxyPool(verbose=False).validate(["a:1"], check_https=True)

    assert seen == [True]


def test_validate_dedups_candidates_before_probing(monkeypatch):
    seen = []

    def fake_test_proxy(ip_port, timeout, check_https):
        seen.append(ip_port)
        return _rec(ip_port, True, 100)

    monkeypatch.setattr(proxy_pool, "test_proxy", fake_test_proxy)

    out = ProxyPool(verbose=False).validate(["x:1", "x:1", "y:1", "x:1"], check_https=False)

    assert sorted(seen) == ["x:1", "y:1"]            # 每个唯一候选只验一次
    assert len(seen) == 2
    assert sorted(r["ip_port"] for r in out) == ["x:1", "y:1"]


def test_validate_returns_empty_for_empty_candidates(monkeypatch):
    called = []

    def fake_test_proxy(ip_port, timeout, check_https):
        called.append(ip_port)
        return _rec(ip_port, True, 1)

    monkeypatch.setattr(proxy_pool, "test_proxy", fake_test_proxy)

    assert ProxyPool(verbose=False).validate([], check_https=True) == []
    assert called == []


def test_validate_returns_records_unchanged(monkeypatch):
    """validate 不加工记录内容（延迟/出口 IP 原样返回），只过滤 + 排序。"""
    rec = _rec("z:1", True, 42, exit_ip="198.51.100.9")

    monkeypatch.setattr(proxy_pool, "test_proxy",
                        lambda ip_port, timeout, check_https: rec)

    out = ProxyPool(verbose=False).validate(["z:1"], check_https=False)

    assert out == [rec]


def test_validate_keeps_records_that_failed_https_tunnel(monkeypatch):
    """现状：筛选条件只看 `http_ok`，`https_ok=False` 的代理照样进入可用列表。

    也就是说 `check_https` 只影响记录内容、不影响筛选结果。只走 HTTPS 的使用者
    必须自己按 `https_ok` 再过滤一遍（README 5.2 只解释了字段含义，没有提醒这点）。
    """
    rec = {"ip_port": "1.2.3.4:8080", "http_ok": True, "https_ok": False,
           "exit_ip": "203.0.113.9", "ms": 88, "err": ""}

    monkeypatch.setattr(proxy_pool, "test_proxy",
                        lambda ip_port, timeout, check_https: rec)

    assert ProxyPool(verbose=False).validate(["1.2.3.4:8080"], check_https=True) == [rec]

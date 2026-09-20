# -*- coding: utf-8 -*-
"""pytest 全局配置（tests 目录）。

作用：
1) 把仓库根加入 sys.path，保证从仓库根运行 `python -m pytest tests` 或
   直接 `pytest` 时 `import proxy_pool` 都可用（仓库根没有 conftest.py，
   本文件即 rootdir 下 tests/ 的入口）。
2) 提供 autouse 的“禁止真实网络”护栏：任何未显式 monkeypatch 的网络调用都会
   直接失败，确保整套测试**离线可跑**。
"""
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import proxy_pool  # noqa: E402  （需要先把仓库根放进 sys.path）

import requests  # noqa: E402


def _forbidden(*_args, **_kwargs):
    raise AssertionError("单元测试禁止发起真实网络请求：请 monkeypatch http_get / requests.get")


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """全局护栏：默认把网络出口全部封死，测试自行用 monkeypatch 覆盖。

    测试内部再 monkeypatch 同一个属性时会覆盖本护栏（同一个 monkeypatch 实例，
    teardown 时按逆序回滚），因此护栏只影响“忘了打桩”的调用路径。
    """
    monkeypatch.setattr(proxy_pool, "http_get", _forbidden)
    monkeypatch.setattr(requests, "get", _forbidden)
    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    yield

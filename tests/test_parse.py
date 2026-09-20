# -*- coding: utf-8 -*-
"""纯函数层单元测试（完全离线）：_norm / strip_comments / parse_html_tables。

所有断言以 proxy_pool.py 的**修复后真实行为**为准，核心事实：

- `IPRE = ^(\\d{1,3}(?:\\.\\d{1,3}){3}):(\\d{2,5})\\Z`，端口写法仍是 **2-5 位数字**
  （1 位端口被拒、前导零被接受），但 `_norm()` 会额外校验：
  - IP 每段必须在 0-255；端口数值必须在 1-65535；
  - 用 `\\Z` 而不是 `$`，因此尾随换行的脏输入被拒。
- `parse_html_tables()` 先调用 `strip_comments()`（对 bs4 解析路径是防御性冗余），
  再按 3 种布局解析表格；两种布局的端口校验口径已统一（都经 `_norm()`），
  且布局A 的端口分组带右边界，6 位端口会被**丢弃**而不是被截断。
"""
import pytest

import proxy_pool
from proxy_pool import _norm, parse_html_tables, strip_comments


# ============================================================================
# _norm(ip, port)
# ============================================================================

@pytest.mark.parametrize("ip,port,expected", [
    ("1.2.3.4", "8080", "1.2.3.4:8080"),
    ("1.2.3.4", 8080, "1.2.3.4:8080"),          # 端口是 int 时同样成立
    ("1.2.3.4", "80", "1.2.3.4:80"),            # 端口位数下限：2 位
    ("1.2.3.4", "65535", "1.2.3.4:65535"),      # 端口位数上限 & 合法上界
    ("10.0.0.1", "3128", "10.0.0.1:3128"),
    ("255.255.255.255", "8080", "255.255.255.255:8080"),
])
def test_norm_accepts_valid_ip_port(ip, port, expected):
    assert _norm(ip, port) == expected


@pytest.mark.parametrize("ip,port", [
    # ---- 端口不合法（写法层面）----
    ("1.2.3.4", "8"),          # 1 位数字：IPRE 要求 2-5 位
    ("1.2.3.4", ""),           # 空端口
    ("1.2.3.4", None),         # None -> "1.2.3.4:None"
    ("1.2.3.4", "808000"),     # 6 位数字：超过 5 位
    ("1.2.3.4", "80a"),        # 非纯数字
    ("1.2.3.4", "80:80"),
    ("1.2.3.4", " 8080"),      # 前导空格不会被 strip
    ("1.2.3.4", "-80"),
    ("1.2.3.4", "8.5"),
    # ---- 端口不合法（数值越界；修复前这些会原样通过）----
    ("1.2.3.4", "0"),
    ("1.2.3.4", "00"),         # int("00") == 0，同样越界
    ("1.2.3.4", "65536"),
    ("1.2.3.4", "99999"),
    # ---- 端口带尾随换行（IPRE 用 \\Z 而非 $）----
    ("1.2.3.4", "8080\n"),
    ("1.2.3.4", "8080\n\n"),
    # ---- IP 不合法（结构）----
    ("1.2.3", "8080"),         # 段数不足
    ("1.2.3.4.5", "8080"),     # 段数过多
    ("1.2.3.4.5.6", "8080"),
    ("abc", "8080"),
    ("", "8080"),
    (" 1.2.3.4", "8080"),      # 前导空格
    ("1.2.3.4 ", "8080"),      # 尾随空格
    ("1.2.3.4\n", "8080"),
    ("2001:db8::1", "8080"),   # IPv6 不支持
    ("1.2.3.4/path", "8080"),
    # ---- IP 不合法（每段必须 <= 255；修复前这些会原样通过）----
    ("256.1.1.1", "8080"),
    ("1.2.3.256", "8080"),
    ("999.999.999.999", "8080"),
])
def test_norm_rejects_malformed(ip, port):
    assert _norm(ip, port) is None


def test_norm_rejects_out_of_range_port():
    """端口必须落在 1-65535（修复前只查位数，65536/99999/0 都会原样通过）。

    这与 parse_html_tables 布局B 的口径已统一到 `_norm()` 里。
    """
    assert _norm("1.2.3.4", "65536") is None
    assert _norm("1.2.3.4", "99999") is None
    assert _norm("1.2.3.4", "00") is None                   # int("00") == 0，越界
    assert _norm("1.2.3.4", "65535") == "1.2.3.4:65535"     # 上界本身合法
    # 前导零端口：数值合法则保留原样（不丢、不编造）
    assert _norm("1.2.3.4", "08080") == "1.2.3.4:08080"
    assert _norm("1.2.3.4", "00080") == "1.2.3.4:00080"


def test_norm_rejects_ip_octets_above_255():
    """每段必须在 0-255（修复前 999.999.999.999 会原样通过）。"""
    assert _norm("999.999.999.999", "8080") is None
    assert _norm("256.1.1.1", "8080") is None
    assert _norm("1.2.3.256", "8080") is None
    assert _norm("255.255.255.255", "8080") == "255.255.255.255:8080"
    # 前导零按原样保留（既有行为，未被本次修复改变）
    assert _norm("010.1.1.1", "8080") == "010.1.1.1:8080"
    assert _norm("0.0.0.0", "8080") == "0.0.0.0:8080"


def test_norm_rejects_trailing_newline_in_port():
    """修复后 IPRE 用 `\\Z` 结尾，端口带 `\\n` 的脏输入被拒（修复前会返回带换行的字符串）。"""
    assert _norm("1.2.3.4", "8080\n") is None
    assert _norm("1.2.3.4", " 8080\n") is None


def test_ipre_is_strictly_anchored():
    """IPRE 用 `\\Z` 锚定整串：match 与 fullmatch 语义等价，尾随换行不再被放过。"""
    assert proxy_pool.IPRE.match("1.2.3.4:8080")
    assert proxy_pool.IPRE.match("1.2.3.4:8080x") is None
    assert proxy_pool.IPRE.match("x1.2.3.4:8080") is None
    # 修复前这里是 `$`，match 会放过尾随换行
    assert proxy_pool.IPRE.match("1.2.3.4:8080\n") is None
    assert proxy_pool.IPRE.match("1.2.3.4:8080\nx") is None
    assert proxy_pool.IPRE.fullmatch("1.2.3.4:8080\n") is None
    assert proxy_pool.IPRE.fullmatch("1.2.3.4:8080").group(2) == "8080"


# ============================================================================
# strip_comments(html)
# ============================================================================

def test_strip_comments_removes_single_inline_comment():
    assert strip_comments("<div>a<!-- 1.2.3.4:8080 -->b</div>") == "<div>ab</div>"


def test_strip_comments_removes_multiline_comment():
    html = "<table><!--\n<tr><td>9.9.9.9:9999</td></tr>\n--><tr><td>1.2.3.4:8080</td></tr></table>"
    out = strip_comments(html)
    assert "9.9.9.9:9999" not in out
    assert "1.2.3.4:8080" in out
    assert out == "<table><tr><td>1.2.3.4:8080</td></tr></table>"


def test_strip_comments_removes_every_comment():
    assert strip_comments("a<!--x-->b<!--y-->c<!--z-->d") == "abcd"


def test_strip_comments_returns_plain_html_unchanged():
    html = "<table><tr><td>1.2.3.4:8080</td></tr></table>"
    assert strip_comments(html) == html


def test_strip_comments_is_non_greedy_between_markers():
    """非贪婪：第一个 `-->` 就结束，不会把后面的正文一起吞掉。"""
    assert strip_comments("<!--a<!--b-->c") == "c"


def test_strip_comments_leaves_unclosed_comment_untouched():
    """现状：没有配对的 `-->` 时正则不匹配，注释内容原样保留（不会做补救性剥离）。"""
    src = "<div><!-- 1.2.3.4:8080"
    assert strip_comments(src) == src


# ============================================================================
# parse_html_tables(body)
# ============================================================================

def _ips(rows):
    return [r["ip_port"] for r in rows]


def test_layout_a_cell_contains_ip_port():
    html = "<table><tr><td>1.2.3.4:8080</td><td>CN</td></tr></table>"
    assert _ips(parse_html_tables(html)) == ["1.2.3.4:8080"]


@pytest.mark.parametrize("cell", [
    "1.2.3.4:8080",              # 半角冒号
    "1.2.3.4：8080",             # 全角冒号
    "1.2.3.4 : 8080",            # 冒号两侧空格
    "1.2.3.4：  8080",           # 全角冒号 + 多空格
    "IP: 1.2.3.4:8080 (CN)",     # 单元格内含其它文本（search 而非 fullmatch）
    "1.2.3.4:8080<br/>",         # 尾随标记
])
def test_layout_a_accepts_various_separators(cell):
    html = f"<table><tr><td>{cell}</td></tr></table>"
    assert _ips(parse_html_tables(html)) == ["1.2.3.4:8080"]


def test_layout_b_ip_cell_followed_by_port_cell():
    html = "<table><tr><td>1.2.3.4</td><td>8080</td></tr></table>"
    assert _ips(parse_html_tables(html)) == ["1.2.3.4:8080"]


def test_layout_b_th_cells_and_header_row_do_not_produce_entries():
    html = ("<table>"
            "<tr><th>IP Address</th><th>Port</th><th>Country</th></tr>"
            "<tr><td>1.2.3.4</td><td>8080</td><td>CN</td></tr>"
            "</table>")
    assert _ips(parse_html_tables(html)) == ["1.2.3.4:8080"]


def test_layout_b_port_search_window_is_five_cells():
    """端口列搜索窗口：IP 之后的 5 个单元格内找端口，第 6 个之后不再看。"""
    inside = ("<table><tr><td>1.2.3.4</td>"
              "<td>x</td><td>y</td><td>z</td><td>w</td><td>8080</td></tr></table>")
    outside = ("<table><tr><td>1.2.3.4</td>"
               "<td>x</td><td>y</td><td>z</td><td>w</td><td>v</td><td>8080</td></tr></table>")
    assert _ips(parse_html_tables(inside)) == ["1.2.3.4:8080"]
    assert _ips(parse_html_tables(outside)) == []


def test_layout_b_skips_out_of_range_port_cell_and_keeps_looking():
    """端口列取值必须落在 1-65535；70000 / 0 这类单元格被跳过（不是终止搜索）。"""
    html = "<table><tr><td>1.2.3.4</td><td>70000</td><td>3128</td></tr></table>"
    assert _ips(parse_html_tables(html)) == ["1.2.3.4:3128"]

    html0 = "<table><tr><td>1.2.3.4</td><td>0</td><td>3128</td></tr></table>"
    assert _ips(parse_html_tables(html0)) == ["1.2.3.4:3128"]


def test_layout_b_ignores_ip_cell_without_any_port():
    html = "<table><tr><td>1.2.3.4</td><td>CN</td></tr></table>"
    assert parse_html_tables(html) == []


def test_record_shape_is_ip_port_and_unknown_proto():
    html = "<table><tr><td>1.2.3.4:8080</td></tr></table>"
    assert parse_html_tables(html) == [{"ip_port": "1.2.3.4:8080", "proto": "?"}]


def test_dedups_same_ip_port_across_layouts_and_rows():
    same_row = "<table><tr><td>1.2.3.4:8080</td><td>1.2.3.4</td><td>8080</td></tr></table>"
    assert _ips(parse_html_tables(same_row)) == ["1.2.3.4:8080"]

    two_rows = ("<table><tr><td>1.2.3.4:8080</td></tr>"
                "<tr><td>1.2.3.4</td><td>8080</td></tr>"
                "<tr><td>1.2.3.4:8080</td></tr></table>")
    assert _ips(parse_html_tables(two_rows)) == ["1.2.3.4:8080"]


def test_returns_empty_list_when_no_ip_found():
    assert parse_html_tables("<table><tr><td>China</td><td>Beijing</td></tr></table>") == []
    assert parse_html_tables("") == []
    assert parse_html_tables("<div>no table here</div>") == []


def test_multiple_rows_keep_document_order():
    html = ("<table>"
            "<tr><td>3.3.3.3</td><td>8080</td></tr>"
            "<tr><td>1.1.1.1:3128</td></tr>"
            "<tr><td>2.2.2.2:1080</td></tr>"
            "</table>")
    assert _ips(parse_html_tables(html)) == ["3.3.3.3:8080", "1.1.1.1:3128", "2.2.2.2:1080"]


# ---------------------------------------------------------------------------
# 反爬对抗：注释里塞的假数据必须被丢掉（strip_comments 的存在意义）
# ---------------------------------------------------------------------------

def test_commented_rows_do_not_pollute_result():
    html = ("<table>"
            "<!--<tr><td>9.9.9.9:9999</td><td>8.8.8.8</td><td>8888</td></tr>-->"
            "<tr><td>1.2.3.4</td><td>8080</td></tr>"
            "</table>")
    got = _ips(parse_html_tables(html))
    assert got == ["1.2.3.4:8080"]
    assert "9.9.9.9:9999" not in got
    assert "8.8.8.8:8888" not in got


def test_commented_cell_inside_live_row_do_not_pollute_result():
    html = ("<table><tr>"
            "<!--<td>9.9.9.9:9999</td>-->"
            "<td>1.2.3.4</td><!--<td>7.7.7.7</td><td>7777</td>--><td>8080</td>"
            "</tr></table>")
    assert _ips(parse_html_tables(html)) == ["1.2.3.4:8080"]


def test_commented_section_spanning_lines_is_ignored():
    html = ("<table>\n"
            "<!--\n"
            "<tr><td>9.9.9.9:9999</td></tr>\n"
            "<tr><td>8.8.8.8</td><td>8888</td></tr>\n"
            "-->\n"
            "<tr><td>1.2.3.4:8080</td></tr>\n"
            "</table>")
    assert _ips(parse_html_tables(html)) == ["1.2.3.4:8080"]


def test_parse_html_tables_feeds_raw_body_through_strip_comments(monkeypatch):
    """契约（README 5.1 声称的反爬防线）：解析的输入必须来自 strip_comments(body)。

    用桩替换 strip_comments 并让它返回**另一张表**：
    - 若 parse_html_tables 用的是 strip_comments 的返回值 -> 只会看到桩里的哨兵条目；
    - 若直接吃原始 body -> 会看到原始表里的 1.2.3.4:8080。
    同时断言桩收到的是未经处理的原始 HTML。

    （为什么需要这条“接线”测试：bs4 的 get_text()/find_all() 本来就不会读到注释内容，
    所以对绝大多数输入而言，剥不剥注释的结果是一样的 —— 见交付报告“疑似缺陷”。
    这条测试把这一步本身固定住，避免以后换成原始 HTML 正则解析时丢掉该防线。）
    """
    sentinel = "<table><tr><td>5.5.5.5:5555</td></tr></table>"
    seen = []

    def fake_strip_comments(html):
        seen.append(html)
        return sentinel

    monkeypatch.setattr(proxy_pool, "strip_comments", fake_strip_comments)

    raw = ("<table><!--<tr><td>9.9.9.9:9999</td></tr>-->"
           "<tr><td>1.2.3.4:8080</td></tr></table>")

    assert _ips(parse_html_tables(raw)) == ["5.5.5.5:5555"]
    assert seen == [raw]


def test_comment_region_created_by_abrupt_empty_comment_hides_fake_row():
    """现状（剥离逻辑与 DOM 解析的唯一已知差异点）：`<!-->` 是 HTML5 的“空注释”。

    lxml 会在此处结束注释，把紧随其后的 `<tr>` 当真实行解析；而 strip_comments
    的正则会把它当成注释开始、一直吃到后面的 `-->`，于是整段（含假数据）都被当作
    注释丢掉。
    结果：注释区里的假数据不会进结果（符合反爬意图），代价是同一段里按 HTML5
    规范本该算真实的那一行也被一并丢弃（少一个候选，属保守方向的偏差）。
    """
    html = ("<table><!--><tr><td>9.9.9.9:9999</td></tr>-->"
            "<tr><td>1.2.3.4:8080</td></tr></table>")
    assert _ips(parse_html_tables(html)) == ["1.2.3.4:8080"]


# ---------------------------------------------------------------------------
# 两种布局的端口/IP 校验口径已统一（都经 _norm）
# ---------------------------------------------------------------------------

def test_layout_a_and_layout_b_agree_on_out_of_range_port():
    """修复前不一致：布局A 会接受端口 99999，布局B 会拒绝。现在两者都拒绝。"""
    assert _ips(parse_html_tables("<table><tr><td>1.2.3.4:99999</td></tr></table>")) == []
    assert _ips(parse_html_tables("<table><tr><td>1.2.3.4</td><td>99999</td></tr></table>")) == []
    assert _ips(parse_html_tables("<table><tr><td>1.2.3.4:65536</td></tr></table>")) == []
    # 上界本身仍然合法
    assert _ips(parse_html_tables("<table><tr><td>1.2.3.4:65535</td></tr></table>")) == \
        ["1.2.3.4:65535"]


def test_layout_a_rejects_6_digit_port_without_truncating():
    """`(\\d{2,5})(?!\\d)`：6 位端口必须被**丢弃**，不能被截成前 5 位（那是编造代理）。"""
    got = _ips(parse_html_tables("<table><tr><td>1.2.3.4:123456</td></tr></table>"))

    assert got == []
    assert "1.2.3.4:12345" not in got
    assert "1.2.3.4:123456" not in got
    # 端口后面紧跟非数字（如 HTML 标记/括号）时仍然正常解析
    assert _ips(parse_html_tables("<table><tr><td>1.2.3.4:8080<br/></td></tr></table>")) == \
        ["1.2.3.4:8080"]


def test_layout_a_rejects_invalid_ip_segments():
    """`_norm` 校验每段的 0-255 范围，999.999.999.999 在两种布局下都被丢弃。"""
    assert _ips(parse_html_tables("<table><tr><td>999.999.999.999:8080</td></tr></table>")) == []
    assert _ips(parse_html_tables("<table><tr><td>999.999.999.999</td><td>8080</td></tr></table>")) == []


def test_layout_a_requires_two_digit_port():
    """现状：1 位端口在两种布局下都会被丢掉。"""
    assert parse_html_tables("<table><tr><td>1.2.3.4:8</td></tr></table>") == []
    assert parse_html_tables("<table><tr><td>1.2.3.4</td><td>8</td></tr></table>") == []


def test_cell_with_space_separator_is_not_parsed():
    """现状：同一单元格内用空格分隔（`1.2.3.4 8080`）不被任何布局覆盖。"""
    assert parse_html_tables("<table><tr><td>1.2.3.4 8080</td></tr></table>") == []

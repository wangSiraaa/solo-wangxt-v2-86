#!/usr/bin/env python3
"""三组虚构案例的逐期核对脚本。

通过 REST API 执行业务动作（逐期确认订阅、录入验收证据、录入用量），
每一步后断言：合同金额、已确认收入、递延余额（收款-确认）与剩余履约义务。

案例一 HT-2026-001 星辰科技：跨月订阅（1-6 月）+ 实施 2 月验收
案例二 HT-2026-002 蓝鲸制造：两个实施模块仅部分验收，未验收的保持待确认
案例三 HT-2026-003 云帆贸易：全额预收但订阅未开通，按量服务按已录用量确认
"""

import json
import sys
import urllib.request
from decimal import Decimal

BASE = "http://127.0.0.1:8000/api"
D = Decimal
ZERO = D("0.00")

PASS, FAIL = 0, 0


def api(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def money(x) -> Decimal:
    return D(str(x)).quantize(D("0.01"))


def check(label, actual, expected):
    global PASS, FAIL
    actual, expected = money(actual), money(expected)
    if actual == expected:
        PASS += 1
        print(f"    ✓ {label:<38} = {actual:>10}")
    else:
        FAIL += 1
        print(f"    ✗ {label:<38} = {actual:>10}  预期 {expected}")


def totals(number, as_of=None):
    qs = f"?as_of={as_of}" if as_of else ""
    for c in api("GET", f"/summary/{qs}")["contracts"]:
        if c["number"] == number:
            return c
    raise AssertionError(f"合同 {number} 不存在")


def show_period(number, period, expect_recognized, expect_deferred, expect_remaining):
    t = totals(number, as_of=period)
    print(f"  [{period}] {number}")
    check("当期已确认收入", t["recognized_by_period"].get(period, 0), expect_recognized)
    check("递延余额（累计收款-累计确认）", t["deferred_balance"], expect_deferred)
    check("剩余履约义务（分摊-累计确认）", t["remaining_obligation"], expect_remaining)


def contract_id(number):
    for c in api("GET", "/contracts/"):
        if c["number"] == number:
            return c["id"]
    raise AssertionError(f"合同 {number} 不存在")


def line_id(number, name_kw):
    for c in api("GET", "/contracts/"):
        if c["number"] == number:
            for l in c["lines"]:
                if name_kw in l["name"]:
                    return l["id"]
    raise AssertionError(f"{number} 找不到行 {name_kw}")


print("=" * 78)
print("第 0 步：核对分摊结果（相对独立售价比例，尾差倒挤）")
print("=" * 78)
t1, t2, t3 = totals("HT-2026-001"), totals("HT-2026-002"), totals("HT-2026-003")
print("  HT-2026-001：13500 × (12000/15000, 3000/15000) → 订阅 10800，实施 2700")
check("案例一分摊合计 = 合同价", t1["allocated_total"], "13500.00")
print("  HT-2026-002：32400 × (20000,10000,6000)/36000 → 18000 / 9000 / 5400")
check("案例二分摊合计 = 合同价", t2["allocated_total"], "32400.00")
print("  HT-2026-003：无折扣 → 订阅 4800，按量 2000（单价 0.20/次）")
check("案例三分摊合计 = 合同价", t3["allocated_total"], "6800.00")

print()
print("=" * 78)
print("案例一：跨月订阅（2026-01 ~ 06）——订阅按月确认，实施凭 2 月验收确认")
print("=" * 78)
cid1 = contract_id("HT-2026-001")
impl_a = line_id("HT-2026-001", "实施")
# 1 月：确认订阅 1800；收款 6750 → 递延 4950
api("POST", f"/contracts/{cid1}/recognize_period/", {"period": "2026-01"})
show_period("HT-2026-001", "2026-01", "1800.00", "4950.00", "11700.00")
# 2 月：订阅 1800 + 实施验收 2700；收款累计 13500
api("POST", f"/contracts/{cid1}/recognize_period/", {"period": "2026-02"})
api("POST", f"/lines/{impl_a}/acceptance/",
    {"accepted_on": "2026-02-10", "reference": "YS-A-2026-0210", "note": "部署完成，客户签收"})
show_period("HT-2026-001", "2026-02", "4500.00", "7200.00", "7200.00")
# 3~6 月：每月订阅 1800（两笔收款 2 月底前已全部到账，累计收款 13500）
cum_def, cum_rem = D("7200.00"), D("7200.00")
for p in ["2026-03", "2026-04", "2026-05", "2026-06"]:
    api("POST", f"/contracts/{cid1}/recognize_period/", {"period": p})
    cum_def -= D("1800.00")
    cum_rem -= D("1800.00")
    show_period("HT-2026-001", p, "1800.00", str(cum_def), str(cum_rem))
t = totals("HT-2026-001")
check("案例一全期累计确认 = 合同价", t["recognized_total"], "13500.00")

print()
print("=" * 78)
print("案例二：部分验收——模块一 2 月验收确认，模块二无验收证据保持待确认")
print("=" * 78)
cid2 = contract_id("HT-2026-002")
impl_b1 = line_id("HT-2026-002", "模块一")
# 1 月：订阅 1800；预收 9720 → 递延 7920
api("POST", f"/contracts/{cid2}/recognize_period/", {"period": "2026-01"})
show_period("HT-2026-002", "2026-01", "1800.00", "7920.00", "30600.00")
# 2 月：订阅 1800 + 模块一验收 18000；模块二 9000 不确认
api("POST", f"/contracts/{cid2}/recognize_period/", {"period": "2026-02"})
api("POST", f"/lines/{impl_b1}/acceptance/",
    {"accepted_on": "2026-02-05", "reference": "YS-B1-2026-0205", "note": "生产看板上线验收"})
show_period("HT-2026-002", "2026-02", "19800.00", "-11880.00", "10800.00")
# 3 月：订阅 1800；模块二依旧挂起
api("POST", f"/contracts/{cid2}/recognize_period/", {"period": "2026-03"})
show_period("HT-2026-002", "2026-03", "1800.00", "-13680.00", "9000.00")
t = totals("HT-2026-002")
check("模块二未验收 → 剩余履约义务恰为 9000", t["remaining_obligation"], "9000.00")
check("案例二累计确认（不含未验收模块）", t["recognized_total"], "23400.00")

print()
print("=" * 78)
print("案例三：预收未开通——收款≠收入；订阅 7 月才开通，按量按已录用量确认")
print("=" * 78)
usage_c = line_id("HT-2026-003", "按量")
# 1 月：预收款 2-28 才到账 → 递延 0；2~3 月：款在手但未履约 → 递延 6800
show_period("HT-2026-003", "2026-01", "0.00", "0.00", "6800.00")
for p in ["2026-02", "2026-03"]:
    show_period("HT-2026-003", p, "0.00", "6800.00", "6800.00")
# 4 月：录入用量 3000 次 × 0.20 = 600
api("POST", f"/lines/{usage_c}/usage/", {"period": "2026-04", "quantity": "3000"})
show_period("HT-2026-003", "2026-04", "600.00", "6200.00", "6200.00")
# 5 月：录入用量 2500 次 × 0.20 = 500
api("POST", f"/lines/{usage_c}/usage/", {"period": "2026-05", "quantity": "2500"})
show_period("HT-2026-003", "2026-05", "500.00", "5700.00", "5700.00")
# 6 月：无用量 → 确认 0；订阅计划（7-9 月）虽存在但未到履约期
show_period("HT-2026-003", "2026-06", "0.00", "5700.00", "5700.00")
t = totals("HT-2026-003")
check("订阅未开通 → 订阅部分确认始终为 0",
      t["recognized_total"], "1100.00")  # 仅按量 600+500

print()
print("=" * 78)
print(f"核对完成：{PASS} 项通过，{FAIL} 项失败")
print("=" * 78)
sys.exit(1 if FAIL else 0)

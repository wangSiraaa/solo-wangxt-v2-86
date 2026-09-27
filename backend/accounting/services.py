"""
收入确认引擎（示例政策，仅用于本项目）。

交易价格分摊（相对独立售价比例法）
  SSP_i = SSP 单价 × 计量数量（订阅按服务月数、实施按项目数、按量按预估用量）
  分摊_i = round( 合同固定对价 × SSP_i / ΣSSP, 2 )
  最后一项吸收尾差，保证 Σ分摊 = 合同固定对价。

确认计划
  订阅：按服务月平均确认，月内最后一项吸收尾差；月末为确认依据日。
  实施：每录入一份验收证据生成一行已确认（分摊价 × 验收比例，逐项保留两位），
        未验收部分为待确认行（依据：待录入验收证据）。
  按量：每录入一条用量生成一行已确认（分摊单价 × 用量，分摊单价 = 分摊价 / 预估总量）；
        已分摊但尚无用量的部分为待确认。预收未开通时没有任何已确认行。

注意：开票(Invoice)与收款(Payment)不参与确认金额计算，只用于余额对照。
"""
import calendar
import datetime
from decimal import Decimal, ROUND_HALF_UP

from .models import (
    PerformanceObligation,
    RevenueRecognitionLine,
)

TWO = Decimal("0.01")
FAR_FUTURE = "9999-12-31"


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def month_iter(start, end):
    """逐自然月产出 (月初, 月末)。"""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        last_day = calendar.monthrange(y, m)[1]
        yield datetime.date(y, m, 1), datetime.date(y, m, last_day)
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1


def allocate_transaction_price(contract) -> None:
    """按 SSP 比例把合同固定对价分摊到各履约义务（尾差由最后一项吸收）。"""
    obligations = list(contract.obligations.order_by("code"))
    total_ssp = sum((o.standalone_selling_price for o in obligations), Decimal("0"))
    if total_ssp <= 0:
        for o in obligations:
            o.allocated_price = Decimal("0")
            o.save(update_fields=["allocated_price"])
        return

    allocated_total = Decimal("0")
    for index, o in enumerate(obligations):
        if index == len(obligations) - 1:
            allocated = money(Decimal(contract.fixed_price) - allocated_total)
        else:
            allocated = money(
                Decimal(contract.fixed_price) * o.standalone_selling_price / total_ssp
            )
        allocated_total += allocated
        o.allocated_price = allocated
        o.save(update_fields=["allocated_price"])


def rebuild_recognition_plan(obligation: PerformanceObligation) -> None:
    """重建单个履约义务的确认计划行（先删后建，保证幂等）。"""
    # 防止调用方持有的是分摊前的过期实例（allocated_price=0）
    obligation.refresh_from_db()
    RevenueRecognitionLine.objects.filter(obligation=obligation).delete()

    if obligation.obligation_type == "subscription":
        _rebuild_subscription(obligation)
    elif obligation.obligation_type == "implementation":
        _rebuild_implementation(obligation)
    elif obligation.obligation_type == "usage":
        _rebuild_usage(obligation)


def _rebuild_subscription(o: PerformanceObligation) -> None:
    months = list(month_iter(o.service_start, o.service_end))
    count = len(months)
    lines = []
    cumulative = Decimal("0")
    for index, (m_start, m_end) in enumerate(months):
        if index == count - 1:
            amount = money(o.allocated_price - cumulative)
        else:
            amount = money(o.allocated_price / count)
        cumulative += amount
        lines.append(
            RevenueRecognitionLine(
                obligation=o,
                period_start=m_start,
                period_end=m_end,
                amount=amount,
                status="pending",
                basis=f"{m_end:%Y年%m月}订阅服务月完结（按月直线）",
            )
        )
    RevenueRecognitionLine.objects.bulk_create(lines)


def _rebuild_implementation(o: PerformanceObligation) -> None:
    evidences = list(o.acceptance_evidences.order_by("accepted_on", "id"))
    lines = []
    recognized = Decimal("0")
    for ev in evidences:
        amount = money(o.allocated_price * ev.portion)
        recognized += amount
        lines.append(
            RevenueRecognitionLine(
                obligation=o,
                period_start=ev.accepted_on,
                period_end=ev.accepted_on,
                amount=amount,
                status="recognized",
                basis=f"验收单据 {ev.document_ref}（验收比例 {ev.portion}）",
                evidence=ev,
            )
        )
    remaining = money(o.allocated_price - recognized)
    if remaining > 0:
        lines.append(
            RevenueRecognitionLine(
                obligation=o,
                period_start=o.service_start or FAR_FUTURE,
                period_end=FAR_FUTURE,
                amount=remaining,
                status="pending",
                basis="待录入验收证据（无证据不确认）",
            )
        )
    RevenueRecognitionLine.objects.bulk_create(lines)


def _rebuild_usage(o: PerformanceObligation) -> None:
    records = list(o.usage_records.order_by("usage_month"))
    estimated = Decimal(o.ssp_quantity)
    unit = money(o.allocated_price / estimated) if estimated > 0 else Decimal("0")

    lines = []
    recognized = Decimal("0")
    for rec in records:
        amount = money(unit * Decimal(rec.quantity))
        recognized += amount
        month_end_day = calendar.monthrange(rec.usage_month.year, rec.usage_month.month)[1]
        lines.append(
            RevenueRecognitionLine(
                obligation=o,
                period_start=rec.usage_month,
                period_end=rec.usage_month.replace(day=month_end_day),
                amount=amount,
                status="recognized",
                basis=f"用量单 {rec.source_ref}：{rec.quantity}{o.usage_unit} × 分摊单价",
                usage=rec,
            )
        )
    remaining = money(o.allocated_price - recognized)
    if remaining > 0:
        lines.append(
            RevenueRecognitionLine(
                obligation=o,
                period_start=FAR_FUTURE,
                period_end=FAR_FUTURE,
                amount=remaining,
                status="pending",
                basis="已预收/已分摊但用量尚未发生（按已录入用量确认）",
            )
        )
    RevenueRecognitionLine.objects.bulk_create(lines)


def rebuild_contract(contract) -> None:
    """合同级重建：先分摊，再重建每一项的确认计划。"""
    allocate_transaction_price(contract)
    for o in contract.obligations.order_by("code"):
        rebuild_recognition_plan(o)

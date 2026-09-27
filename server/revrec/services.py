"""核算服务层：示例政策下的交易价格分摊与确认计划生成。

示例政策（仅用于本项目演示，不宣称覆盖任何具体会计准则）：
1. 交易价格按各项履约义务的相对独立售价（relative SSP）比例分摊，
   尾差由最后一行倒挤，保证分摊合计 = 合同交易价格。
2. 账号订阅：在服务期覆盖的每个自然月等额确认（直线法，按月）。
3. 一次性实施：录入验收证据后，在验收所属期间一次性确认；未验收不确认。
4. 按量服务：分摊单价 = 分摊价 / 预估总量；按已录入用量确认，
   累计确认不超过该行的分摊价。
5. 收款只形成递延（合同负债），绝不直接确认为收入。
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    AcceptanceEvidence,
    BasisType,
    Contract,
    ContractLine,
    EntryStatus,
    LineType,
    ScheduleEntry,
    UsageRecord,
)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def q2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def month_iter(start, end):
    """生成起止日期覆盖的自然月 (year, month) 序列。"""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def period_of(d) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def to_date(value) -> date:
    """接受 date 或 'YYYY-MM-DD' 字符串。"""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def period_end(period: str) -> date:
    """'YYYY-MM' 所属自然月的最后一天。"""
    import calendar

    y, m = int(period[:4]), int(period[5:7])
    return date(y, m, calendar.monthrange(y, m)[1])


class PolicyError(Exception):
    """违反示例政策或数据不满足前提时抛出。"""


@transaction.atomic
def allocate_contract(contract: Contract) -> Contract:
    """按相对独立售价比例分摊交易价格，并为订阅行生成月度确认计划。"""
    lines = list(contract.lines.order_by("sort", "id"))
    if not lines:
        raise PolicyError("合同没有履约义务行，无法分摊。")
    total_ssp = sum((l.ssp for l in lines), ZERO)
    if total_ssp <= 0:
        raise PolicyError("独立售价合计必须大于零。")

    # 重新分摊前清除旧的订阅计划与分摊结果
    ScheduleEntry.objects.filter(
        line__contract=contract, basis_type=BasisType.TIME_ELAPSED,
        status=EntryStatus.PLANNED,
    ).delete()

    running = ZERO
    last = lines[-1]
    for line in lines:
        if line is last:
            allocated = q2(contract.total_price - running)  # 尾差倒挤
        else:
            allocated = q2(contract.total_price * line.ssp / total_ssp)
            running += allocated
        line.allocated_price = allocated
        if line.line_type == LineType.USAGE:
            if not line.estimated_units or line.estimated_units <= 0:
                raise PolicyError(f"按量行「{line.name}」缺少预估总量。")
            line.usage_unit_price = (
                allocated / line.estimated_units
            ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        line.save()

    for line in lines:
        if line.line_type == LineType.SUBSCRIPTION:
            _build_subscription_schedule(line)
    return contract


def _build_subscription_schedule(line: ContractLine) -> None:
    """订阅行：服务期覆盖的每个自然月生成一条待确认计划（末月倒挤尾差）。"""
    if not (line.service_start and line.service_end):
        raise PolicyError(f"订阅行「{line.name}」缺少服务起止日期。")
    if line.service_end < line.service_start:
        raise PolicyError(f"订阅行「{line.name}」服务结束日早于开始日。")

    months = [f"{y:04d}-{m:02d}" for y, m in month_iter(line.service_start, line.service_end)]
    n = len(months)
    per_month = q2(line.allocated_price / n)
    running = ZERO
    for i, period in enumerate(months):
        if i == n - 1:
            amount = q2(line.allocated_price - running)
        else:
            amount = per_month
            running += amount
        ScheduleEntry.objects.update_or_create(
            line=line,
            period=period,
            basis_type=BasisType.TIME_ELAPSED,
            defaults={
                "amount": amount,
                "status": EntryStatus.PLANNED,
                "basis_note": f"订阅服务期 {line.service_start} ~ {line.service_end}，"
                f"共 {n} 个月直线分摊（第 {i + 1}/{n} 期）",
            },
        )


@transaction.atomic
def record_acceptance(line: ContractLine, accepted_on, reference: str, note: str = ""):
    """录入验收证据：实施行在验收所属期间一次性确认全部分摊价。"""
    if line.line_type != LineType.IMPLEMENTATION:
        raise PolicyError("只有一次性实施行可以录入验收证据。")
    if line.allocated_price is None:
        raise PolicyError("合同尚未分摊，请先执行分摊。")
    if hasattr(line, "acceptance"):
        raise PolicyError("该行已存在验收证据，首版不支持重复验收。")

    evidence = AcceptanceEvidence.objects.create(
        line=line, accepted_on=to_date(accepted_on), reference=reference, note=note
    )
    entry = ScheduleEntry.objects.create(
        line=line,
        period=period_of(to_date(accepted_on)),
        amount=line.allocated_price,
        status=EntryStatus.RECOGNIZED,
        basis_type=BasisType.ACCEPTANCE,
        basis_note=f"验收单号 {reference}，验收日期 {accepted_on}",
        recognized_at=timezone.now(),
    )
    return evidence, entry


@transaction.atomic
def record_usage(line: ContractLine, period: str, quantity: Decimal):
    """录入用量：按 用量×分摊单价 确认，累计不超过该行分摊价。"""
    if line.line_type != LineType.USAGE:
        raise PolicyError("只有按量服务行可以录入用量。")
    if line.allocated_price is None or line.usage_unit_price is None:
        raise PolicyError("合同尚未分摊，请先执行分摊。")
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise PolicyError("用量必须大于零。")

    record = UsageRecord.objects.create(line=line, period=period, quantity=quantity)

    # 该期全部用量对应的应确认金额
    period_qty = sum(
        (r.quantity for r in line.usage_records.filter(period=period)), ZERO
    )
    period_amount = q2(period_qty * line.usage_unit_price)

    # 全行累计已确认（含其他期间），cap 在分摊价
    recognized_other = sum(
        (
            e.amount
            for e in line.schedule.filter(status=EntryStatus.RECOGNIZED).exclude(
                period=period, basis_type=BasisType.USAGE
            )
        ),
        ZERO,
    )
    cap_remaining = q2(line.allocated_price - recognized_other)
    if period_amount > cap_remaining:
        period_amount = cap_remaining  # 累计确认不超过分摊价

    entry, _ = ScheduleEntry.objects.update_or_create(
        line=line,
        period=period,
        basis_type=BasisType.USAGE,
        defaults={
            "amount": period_amount,
            "status": EntryStatus.RECOGNIZED,
            "basis_note": (
                f"期间用量 {period_qty} {line.unit_label or '单位'} × "
                f"分摊单价 {line.usage_unit_price}"
            ),
            "recognized_at": timezone.now(),
        },
    )
    return record, entry


@transaction.atomic
def recognize_period(contract: Contract, period: str) -> int:
    """把合同在指定期间的订阅类待确认计划标记为已确认（月度服务已提供）。"""
    entries = ScheduleEntry.objects.filter(
        line__contract=contract,
        period=period,
        basis_type=BasisType.TIME_ELAPSED,
        status=EntryStatus.PLANNED,
    )
    now = timezone.now()
    count = entries.update(status=EntryStatus.RECOGNIZED, recognized_at=now)
    return count


# ---------- 汇总 / 对照 ----------

def line_recognized(line: ContractLine, as_of: str | None = None) -> Decimal:
    entries = line.schedule.filter(status=EntryStatus.RECOGNIZED)
    if as_of:
        entries = entries.filter(period__lte=as_of)
    return sum((e.amount for e in entries), ZERO)


def contract_totals(contract: Contract, as_of: str | None = None) -> dict:
    """合同汇总。as_of='YYYY-MM' 时给出该期间末的时点快照：
    收款只计期间末之前到账的，确认只计该期间及以前的。"""
    lines = list(contract.lines.all())
    recognized = sum((line_recognized(l, as_of) for l in lines), ZERO)
    payments = contract.payments.all()
    if as_of:
        payments = payments.filter(received_on__lte=period_end(as_of))
    received = sum((p.amount for p in payments), ZERO)
    allocated = sum((l.allocated_price or ZERO for l in lines), ZERO)
    return {
        "total_price": contract.total_price,
        "allocated_total": allocated,
        "received_total": received,
        "recognized_total": recognized,
        # 递延余额（合同负债口径）：已收款但尚未确认收入的部分
        "deferred_balance": q2(received - recognized),
        # 剩余履约义务：已分摊但尚未确认的部分
        "remaining_obligation": q2(allocated - recognized),
    }


def period_matrix(as_of: str | None = None):
    """期间 × 合同 的已确认金额矩阵，供逐期核对；汇总列按 as_of 截止。"""
    contracts = list(Contract.objects.prefetch_related("lines__schedule").all())
    periods = sorted(
        {
            e.period
            for c in contracts
            for l in c.lines.all()
            for e in l.schedule.all()
        }
    )
    rows = []
    for c in contracts:
        by_period = {p: ZERO for p in periods}
        planned = {p: ZERO for p in periods}
        for l in c.lines.all():
            for e in l.schedule.all():
                if e.status == EntryStatus.RECOGNIZED:
                    by_period[e.period] = by_period.get(e.period, ZERO) + e.amount
                else:
                    planned[e.period] = planned.get(e.period, ZERO) + e.amount
        rows.append(
            {
                "contract_id": c.id,
                "number": c.number,
                "customer": c.customer,
                "recognized_by_period": {p: by_period.get(p, ZERO) for p in periods},
                "planned_by_period": {p: planned.get(p, ZERO) for p in periods},
                **contract_totals(c, as_of),
            }
        )
    return {"as_of": as_of, "periods": periods, "contracts": rows}

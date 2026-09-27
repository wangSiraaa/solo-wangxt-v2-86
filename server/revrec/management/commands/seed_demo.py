"""写入三组虚构演示案例（仅建合同、履约义务与收款，并执行分摊）。

业务流程动作（逐期确认、验收、用量录入）由 scripts/verify_cases.py
通过 REST API 执行并逐期断言，保证 API 与核算逻辑端到端一致。
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from revrec.models import Contract, ContractLine, PaymentReceipt
from revrec.services import allocate_contract

D = Decimal


def build_cases():
    """三组虚构案例的静态数据定义。"""
    return [
        # 案例一：跨月订阅 —— 含折扣，检验相对 SSP 分摊与按月确认
        {
            "number": "HT-2026-001",
            "customer": "星辰科技（虚构）",
            "signed_on": date(2025, 12, 28),
            "total_price": D("13500.00"),  # ΣSSP=15000，折扣 1500
            "note": "案例一：跨月订阅 + 实施，合同价低于独立售价合计，检验分摊。",
            "lines": [
                {
                    "name": "账号订阅（2026-01 ~ 2026-06）",
                    "line_type": "SUBSCRIPTION",
                    "ssp": D("12000.00"),
                    "service_start": date(2026, 1, 1),
                    "service_end": date(2026, 6, 30),
                },
                {
                    "name": "一次性实施部署",
                    "line_type": "IMPLEMENTATION",
                    "ssp": D("3000.00"),
                },
            ],
            "payments": [
                {"received_on": date(2026, 1, 5), "amount": D("6750.00"), "reference": "SK-001"},
                {"received_on": date(2026, 2, 15), "amount": D("6750.00"), "reference": "SK-002"},
            ],
        },
        # 案例二：部分验收 —— 模块一验收、模块二始终未验收保持待确认
        {
            "number": "HT-2026-002",
            "customer": "蓝鲸制造（虚构）",
            "signed_on": date(2026, 1, 8),
            "total_price": D("32400.00"),  # ΣSSP=36000，折扣 3600
            "note": "案例二：两个实施模块仅部分验收，未验收模块保持待确认。",
            "lines": [
                {
                    "name": "实施模块一（生产看板）",
                    "line_type": "IMPLEMENTATION",
                    "ssp": D("20000.00"),
                },
                {
                    "name": "实施模块二（质量追溯）",
                    "line_type": "IMPLEMENTATION",
                    "ssp": D("10000.00"),
                },
                {
                    "name": "账号订阅（2026-01 ~ 2026-03）",
                    "line_type": "SUBSCRIPTION",
                    "ssp": D("6000.00"),
                    "service_start": date(2026, 1, 1),
                    "service_end": date(2026, 3, 31),
                },
            ],
            "payments": [
                {"received_on": date(2026, 1, 10), "amount": D("9720.00"), "reference": "SK-101"},
            ],
        },
        # 案例三：预收未开通 —— 全额预收，订阅核对期内未开始，按量按已录用量确认
        {
            "number": "HT-2026-003",
            "customer": "云帆贸易（虚构）",
            "signed_on": date(2026, 2, 20),
            "total_price": D("6800.00"),  # ΣSSP=6800，无折扣
            "note": "案例三：全额预收但订阅 7 月才开通；按量服务按已录用量确认。",
            "lines": [
                {
                    "name": "账号订阅（2026-07 ~ 2026-09，未开通）",
                    "line_type": "SUBSCRIPTION",
                    "ssp": D("4800.00"),
                    "service_start": date(2026, 7, 1),
                    "service_end": date(2026, 9, 30),
                },
                {
                    "name": "按量服务（API 调用包）",
                    "line_type": "USAGE",
                    "ssp": D("2000.00"),
                    "estimated_units": D("10000.00"),
                    "unit_label": "次",
                },
            ],
            "payments": [
                {"received_on": date(2026, 2, 28), "amount": D("6800.00"), "reference": "SK-201"},
            ],
        },
    ]


class Command(BaseCommand):
    help = "写入三组虚构演示案例（合同 + 履约义务 + 收款 + 分摊）"

    @transaction.atomic
    def handle(self, *args, **options):
        Contract.objects.all().delete()  # 级联清除行、计划、收款、证据、用量
        for case in build_cases():
            lines = case.pop("lines")
            payments = case.pop("payments")
            contract = Contract.objects.create(**case)
            for i, line in enumerate(lines, start=1):
                ContractLine.objects.create(contract=contract, sort=i, **line)
            for payment in payments:
                PaymentReceipt.objects.create(contract=contract, **payment)
            allocate_contract(contract)
            self.stdout.write(
                self.style.SUCCESS(
                    f"已创建 {contract.number} {contract.customer}，"
                    f"合同价 {contract.total_price}，{len(lines)} 项履约义务"
                )
            )

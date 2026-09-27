"""
虚构演示数据（仅用于本项目的示例政策，不宣称覆盖任何会计准则）。

案例 A  HT-2026-A01 跨月订阅：4 个月订阅 + 实施，15% 折扣，全验收
案例 B  HT-2026-B02 部分验收：12 个月订阅 + 实施，仅 60% 验收
案例 C  HT-2026-C03 预收未开通：按量服务预存，11 月才开通用量
"""
from datetime import date

from django.core.management.base import BaseCommand

from accounting.models import (
    AcceptanceEvidence,
    Contract,
    Invoice,
    Payment,
    PerformanceObligation,
    UsageRecord,
)
from accounting.services import rebuild_contract


def D(value):
    return value


class Command(BaseCommand):
    help = "灌入三组虚构合同/履约义务/验收/用量/开票/收款案例"

    def handle(self, *args, **options):
        # 允许重复执行
        Contract.objects.filter(number__in=["HT-2026-A01", "HT-2026-B02", "HT-2026-C03"]).delete()

        # ---------- 案例 A：跨月订阅 + 一次性实施（全验收） ----------
        a = Contract.objects.create(
            number="HT-2026-A01",
            customer="蓝鲸电商有限公司",
            signed_on=date(2026, 3, 25),
            fixed_price=D("117000.00"),  # SSP 120,000，整体折扣 15,000
        )
        a_sub = PerformanceObligation.objects.create(
            contract=a, code="A-SUB", name="账号订阅(20账号×4个月)",
            obligation_type="subscription",
            ssp_unit_price=D("1125.00"), ssp_quantity=80,
            standalone_selling_price=D("90000.00"),
            service_start=date(2026, 4, 1), service_end=date(2026, 7, 31),
        )
        a_impl = PerformanceObligation.objects.create(
            contract=a, code="A-IMP", name="一次性实施与上线培训",
            obligation_type="implementation",
            ssp_unit_price=D("30000.00"), ssp_quantity=1,
            standalone_selling_price=D("30000.00"),
            service_start=date(2026, 4, 1), service_end=date(2026, 4, 30),
        )
        AcceptanceEvidence.objects.create(
            obligation=a_impl, accepted_on=date(2026, 4, 20),
            portion=D("1.0000"), document_ref="YS-A01-01",
            note="上线培训完成，客户签字验收",
        )
        Invoice.objects.create(
            contract=a, issued_on=date(2026, 4, 1),
            amount=D("117000.00"), note="合同签订即全额开票（开票≠收入）",
        )
        Payment.objects.create(
            contract=a, received_on=date(2026, 4, 10),
            amount=D("117000.00"), is_prepayment=False, note="全额回款",
        )
        rebuild_contract(a)

        # ---------- 案例 B：跨 12 个月订阅 + 实施部分验收 ----------
        b = Contract.objects.create(
            number="HT-2026-B02",
            customer="赤兔物流股份公司",
            signed_on=date(2025, 12, 20),
            fixed_price=D("150000.00"),  # SSP 160,000，折扣 10,000
        )
        b_sub = PerformanceObligation.objects.create(
            contract=b, code="B-SUB", name="账号订阅(50账号×12个月)",
            obligation_type="subscription",
            ssp_unit_price=D("200.00"), ssp_quantity=600,
            standalone_selling_price=D("120000.00"),
            service_start=date(2026, 1, 1), service_end=date(2026, 12, 31),
        )
        b_impl = PerformanceObligation.objects.create(
            contract=b, code="B-IMP", name="一次性实施(两期)",
            obligation_type="implementation",
            ssp_unit_price=D("40000.00"), ssp_quantity=1,
            standalone_selling_price=D("40000.00"),
            service_start=date(2026, 1, 1), service_end=date(2026, 6, 30),
        )
        AcceptanceEvidence.objects.create(
            obligation=b_impl, accepted_on=date(2026, 3, 15),
            portion=D("0.6000"), document_ref="YS-B02-01",
            note="一期主数据迁移验收，二期尚未验收",
        )
        Invoice.objects.create(
            contract=b, issued_on=date(2026, 1, 1),
            amount=D("120000.00"), note="首期开票",
        )
        Invoice.objects.create(
            contract=b, issued_on=date(2026, 7, 1),
            amount=D("30000.00"), note="二期开票（此时收入仍只认已履约部分）",
        )
        Payment.objects.create(
            contract=b, received_on=date(2026, 1, 10),
            amount=D("150000.00"), is_prepayment=False, note="首期回款",
        )
        Payment.objects.create(
            contract=b, received_on=date(2026, 7, 10),
            amount=D("80000.00"), is_prepayment=False, note="二期回款（多付10,000为预收性质）",
        )
        rebuild_contract(b)

        # ---------- 案例 C：按量服务预收未开通，11 月才产生用量 ----------
        c = Contract.objects.create(
            number="HT-2026-C03",
            customer="云杉智能科技",
            signed_on=date(2026, 9, 20),
            fixed_price=D("90000.00"),  # 预存，SSP 与成交价一致：0.90/次 × 100,000
        )
        c_use = PerformanceObligation.objects.create(
            contract=c, code="C-USE", name="智能审核按量服务(预估100,000次)",
            obligation_type="usage",
            ssp_unit_price=D("0.90"), ssp_quantity=100000,
            standalone_selling_price=D("90000.00"),
            usage_unit="次",
        )
        UsageRecord.objects.create(
            obligation=c_use, usage_month=date(2026, 11, 1),
            quantity=D("60000.00"), source_ref="USG-C03-202611",
        )
        # 10 月服务未开通：没有任何用量记录 -> 0 确认
        Invoice.objects.create(
            contract=c, issued_on=date(2026, 9, 25),
            amount=D("90000.00"), note="预存全额开票，服务尚未开通",
        )
        Payment.objects.create(
            contract=c, received_on=date(2026, 9, 26),
            amount=D("90000.00"), is_prepayment=True, note="预收款，11 月才开通",
        )
        rebuild_contract(c)

        self.stdout.write(self.style.SUCCESS(
            "已灌入 3 组虚构案例：A 跨月订阅 / B 部分验收 / C 预收未开通"
        ))

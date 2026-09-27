"""
引擎单元测试：SSP 分摊、订阅逐月、实施凭验收、按量凭用量、无证据待确认。
全部使用独立的测试数据库（Decimal 精确断言）。
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import (
    AcceptanceEvidence,
    Contract,
    Invoice,
    Payment,
    PerformanceObligation,
    UsageRecord,
)
from accounting.serializers import line_is_recognized
from accounting.services import rebuild_contract, rebuild_recognition_plan


def D(v):
    return Decimal(v)


class AllocationTests(TestCase):
    def test_ssp_allocation_with_discount_and_rounding_absorbed(self):
        c = Contract.objects.create(
            number="T-1", customer="x", signed_on=date(2026, 1, 1),
            fixed_price=D("100.00"),
        )
        o1 = PerformanceObligation.objects.create(
            contract=c, code="1", name="a", obligation_type="subscription",
            ssp_unit_price=D("1.00"), ssp_quantity=1,
            standalone_selling_price=D("1.00"),
            service_start=date(2026, 1, 1), service_end=date(2026, 1, 1),
        )
        o2 = PerformanceObligation.objects.create(
            contract=c, code="2", name="b", obligation_type="implementation",
            ssp_unit_price=D("3.00"), ssp_quantity=1,
            standalone_selling_price=D("3.00"),
        )
        rebuild_contract(c)
        o1.refresh_from_db(); o2.refresh_from_db()
        # 100 × 1/4 = 25.00；尾差由最后一项吸收
        self.assertEqual(o1.allocated_price, D("25.00"))
        self.assertEqual(o2.allocated_price, D("75.00"))
        self.assertEqual(
            o1.allocated_price + o2.allocated_price, c.fixed_price
        )

    def test_allocation_rounding_remainder_goes_to_last(self):
        # 10 / 3 不能整除：33.34 + 33.33 + 33.33
        c = Contract.objects.create(
            number="T-2", customer="x", signed_on=date(2026, 1, 1),
            fixed_price=D("100.00"),
        )
        obs = []
        for i, code in enumerate(["1", "2", "3"]):
            obs.append(PerformanceObligation.objects.create(
                contract=c, code=code, name=code, obligation_type="implementation",
                ssp_unit_price=D("1.00"), ssp_quantity=1,
                standalone_selling_price=D("1.00"),
            ))
        rebuild_contract(c)
        allocations = [o.allocated_price for o in PerformanceObligation.objects.order_by("code")]
        # 尾差由最后一项吸收
        self.assertEqual(allocations, [D("33.33"), D("33.33"), D("33.34")])


class RecognitionTests(TestCase):
    def _contract(self):
        c = Contract.objects.create(
            number="T-3", customer="x", signed_on=date(2026, 1, 1),
            fixed_price=D("120.00"),
        )
        sub = PerformanceObligation.objects.create(
            contract=c, code="S", name="订阅3个月", obligation_type="subscription",
            ssp_unit_price=D("30.00"), ssp_quantity=3,
            standalone_selling_price=D("90.00"),
            service_start=date(2026, 2, 1), service_end=date(2026, 4, 30),
        )
        impl = PerformanceObligation.objects.create(
            contract=c, code="I", name="实施", obligation_type="implementation",
            ssp_unit_price=D("30.00"), ssp_quantity=1,
            standalone_selling_price=D("30.00"),
        )
        rebuild_contract(c)
        return c, sub, impl

    def test_subscription_monthly_recognition(self):
        _, sub, _ = self._contract()
        # 90 / (120*90/120)=90 分摊后仍是 90，每月 30
        sub = PerformanceObligation.objects.get(pk=sub.pk)
        lines = list(sub.recognition_lines.order_by("period_end"))
        self.assertEqual([ln.amount for ln in lines], [D("30.00")] * 3)
        self.assertFalse(line_is_recognized(lines[0], date(2026, 2, 27)))
        self.assertTrue(line_is_recognized(lines[0], date(2026, 2, 28)))
        self.assertFalse(line_is_recognized(lines[2], date(2026, 3, 31)))
        self.assertTrue(line_is_recognized(lines[2], date(2026, 4, 30)))

    def test_implementation_without_evidence_stays_pending(self):
        _, _, impl = self._contract()
        impl = PerformanceObligation.objects.get(pk=impl.pk)
        lines = list(impl.recognition_lines.all())
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].status, "pending")
        self.assertEqual(lines[0].amount, D("30.00"))
        # 无论截止日多晚，无证据不确认
        self.assertFalse(line_is_recognized(lines[0], date(2030, 1, 1)))

    def test_partial_acceptance_recognizes_only_portion(self):
        _, _, impl = self._contract()
        AcceptanceEvidence.objects.create(
            obligation=impl, accepted_on=date(2026, 3, 10),
            portion=D("0.6000"), document_ref="EV-1",
        )
        rebuild_recognition_plan(impl)
        lines = list(impl.recognition_lines.order_by("period_end"))
        # 9999 待确认行排在后
        self.assertEqual(lines[0].status, "recognized")
        self.assertEqual(lines[0].amount, D("18.00"))
        self.assertEqual(lines[1].status, "pending")
        self.assertEqual(lines[1].amount, D("12.00"))
        self.assertFalse(line_is_recognized(lines[0], date(2026, 3, 9)))
        self.assertTrue(line_is_recognized(lines[0], date(2026, 3, 10)))

    def test_usage_recognized_only_when_recorded(self):
        c = Contract.objects.create(
            number="T-4", customer="x", signed_on=date(2026, 9, 1),
            fixed_price=D("100.00"),
        )
        use = PerformanceObligation.objects.create(
            contract=c, code="U", name="按量", obligation_type="usage",
            ssp_unit_price=D("1.00"), ssp_quantity=100,
            standalone_selling_price=D("100.00"), usage_unit="次",
        )
        rebuild_contract(c)
        # 未录入用量：全部待确认
        lines = list(use.recognition_lines.all())
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].status, "pending")
        # 录入 40 次：分摊单价 1.00 × 40 = 40
        UsageRecord.objects.create(
            obligation=use, usage_month=date(2026, 11, 1),
            quantity=D("40.00"), source_ref="U-1",
        )
        rebuild_recognition_plan(use)
        lines = list(use.recognition_lines.order_by("period_end"))
        self.assertEqual(lines[0].amount, D("40.00"))
        self.assertEqual(lines[0].status, "recognized")
        self.assertEqual(lines[1].amount, D("60.00"))
        self.assertEqual(lines[1].status, "pending")
        # 月末前不确认
        self.assertFalse(line_is_recognized(lines[0], date(2026, 11, 29)))

    def test_invoice_does_not_drive_revenue(self):
        c, _, impl = self._contract()
        Invoice.objects.create(contract=c, issued_on=date(2026, 1, 5), amount=D("120.00"))
        Payment.objects.create(contract=c, received_on=date(2026, 1, 6), amount=D("120.00"))
        # 实施无证据 + 订阅未开始：开了全额票、收了全款，已确认收入仍为 0
        as_of = date(2026, 1, 31)
        recognized = D("0")
        for o in c.obligations.all():
            for ln in o.recognition_lines.all():
                if line_is_recognized(ln, as_of):
                    recognized += ln.amount
        self.assertEqual(recognized, D("0.00"))

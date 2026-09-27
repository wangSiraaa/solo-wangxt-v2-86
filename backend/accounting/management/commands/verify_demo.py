"""
三组虚构案例的逐期核对脚本（独立于 HTTP，直接走 ORM + 确认引擎）。

运行：python3 manage.py verify_demo
断言失败会非零退出。示例政策仅用于本项目，不宣称覆盖任何会计准则。
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from accounting.models import Contract
from accounting.serializers import line_is_recognized


def q2(value):
    return Decimal(value).quantize(Decimal("0.01"))


class Command(BaseCommand):
    help = "逐期核对跨月订阅 / 部分验收 / 预收未开通三组案例"

    def handle(self, *args, **options):
        failures = []

        def check(contract, as_of, expected_rev, expected_deferred,
                  billed=None, received=None):
            recognized = Decimal("0")
            for o in contract.obligations.all():
                for line in o.recognition_lines.all():
                    if line_is_recognized(line, as_of):
                        recognized += line.amount
            received = sum(
                (p.amount for p in contract.payments.all() if p.received_on <= as_of),
                Decimal("0"),
            )
            billed = sum(
                (i.amount for i in contract.invoices.all() if i.issued_on <= as_of),
                Decimal("0"),
            )
            deferred = received - recognized

            actual = {
                "rev": q2(recognized), "deferred": q2(deferred),
                "billed": q2(billed), "received": q2(received),
            }
            expected = {
                "rev": q2(expected_rev), "deferred": q2(expected_deferred),
                "billed": q2(billed if billed is not None else Decimal("0")),
                "received": q2(received if received is not None else Decimal("0")),
            }
            label = f"{contract.number} @ {as_of}"
            ok = (
                actual["rev"] == expected["rev"]
                and actual["deferred"] == expected["deferred"]
                and (billed is None or actual["billed"] == expected["billed"])
                and (received is None or actual["received"] == expected["received"])
            )
            if ok:
                self.stdout.write(self.style.SUCCESS(
                    f"  PASS {label}: 已确认 {actual['rev']}，递延 {actual['deferred']}"
                ))
            else:
                failures.append(f"{label}: actual={actual} expected={expected}")
                self.stdout.write(self.style.ERROR(
                    f"  FAIL {label}: actual={actual} expected={expected}"
                ))

        by_number = {c.number: c for c in Contract.objects.prefetch_related(
            "obligations__recognition_lines", "invoices", "payments"
        )}

        # 案例 A：跨月订阅 + 全验收实施
        # 分摊：订阅 87,750（4×21,937.50）、实施 29,250（4/20 验收）
        a = by_number["HT-2026-A01"]
        self.stdout.write("案例 A 跨月订阅（蓝鲸电商）")
        check(a, date(2026, 3, 31), "0", "0", billed="0", received="0")
        check(a, date(2026, 4, 30), "51187.50", "65812.50", billed="117000", received="117000")
        check(a, date(2026, 5, 31), "73125.00", "43875.00")
        check(a, date(2026, 7, 31), "117000.00", "0.00")
        check(a, date(2026, 8, 31), "117000.00", "0.00")

        # 案例 B：12 个月订阅 + 实施仅 60% 验收
        # 分摊：订阅 112,500（12×9,375）、实施 37,500，已验收 22,500
        b = by_number["HT-2026-B02"]
        self.stdout.write("案例 B 部分验收（赤兔物流）")
        check(b, date(2026, 3, 31), "50625.00", "99375.00", billed="120000", received="150000")
        check(b, date(2026, 7, 31), "88125.00", "141875.00", billed="150000", received="230000")
        check(b, date(2026, 9, 30), "106875.00", "123125.00")
        check(b, date(2026, 12, 31), "135000.00", "95000.00")

        # 案例 C：按量预收未开通，11 月才有 60,000 次用量；分摊单价 0.90
        c = by_number["HT-2026-C03"]
        self.stdout.write("案例 C 预收未开通（云杉智能）")
        check(c, date(2026, 9, 30), "0", "90000.00", billed="90000", received="90000")
        check(c, date(2026, 10, 31), "0", "90000.00")
        check(c, date(2026, 11, 30), "54000.00", "36000.00")

        if failures:
            self.stdout.write(self.style.ERROR(f"\n{len(failures)} 项核对失败"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("\n全部逐期核对通过"))

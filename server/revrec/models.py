from django.db import models


class LineType(models.TextChoices):
    SUBSCRIPTION = "SUBSCRIPTION", "账号订阅"
    IMPLEMENTATION = "IMPLEMENTATION", "一次性实施"
    USAGE = "USAGE", "按量服务"


class EntryStatus(models.TextChoices):
    PLANNED = "PLANNED", "待确认"
    RECOGNIZED = "RECOGNIZED", "已确认"


class BasisType(models.TextChoices):
    TIME_ELAPSED = "TIME_ELAPSED", "期间服务已提供（按月）"
    ACCEPTANCE = "ACCEPTANCE", "验收证据"
    USAGE = "USAGE", "已录入用量"


class Contract(models.Model):
    """合同：签了多少合同（交易价格总额）。"""

    number = models.CharField("合同编号", max_length=40, unique=True)
    customer = models.CharField("客户名称", max_length=120)
    signed_on = models.DateField("签订日期")
    total_price = models.DecimalField("合同交易价格", max_digits=14, decimal_places=2)
    note = models.TextField("备注", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"{self.number} {self.customer}"


class ContractLine(models.Model):
    """履约义务：合同内可明确区分的承诺，含独立售价与分摊后交易价格。"""

    contract = models.ForeignKey(Contract, related_name="lines", on_delete=models.CASCADE)
    sort = models.PositiveSmallIntegerField("行序", default=0)
    name = models.CharField("义务名称", max_length=120)
    line_type = models.CharField("义务类型", max_length=20, choices=LineType.choices)
    ssp = models.DecimalField("独立售价 SSP", max_digits=14, decimal_places=2)
    allocated_price = models.DecimalField(
        "分摊后交易价格", max_digits=14, decimal_places=2, null=True, blank=True
    )
    # 订阅类
    service_start = models.DateField("服务开始日", null=True, blank=True)
    service_end = models.DateField("服务结束日", null=True, blank=True)
    # 按量类
    estimated_units = models.DecimalField(
        "预估总量", max_digits=14, decimal_places=2, null=True, blank=True
    )
    unit_label = models.CharField("计量单位", max_length=20, blank=True, default="")
    usage_unit_price = models.DecimalField(
        "分摊单价", max_digits=14, decimal_places=6, null=True, blank=True
    )

    class Meta:
        ordering = ["contract", "sort"]

    def __str__(self):
        return f"{self.contract.number}-{self.sort} {self.name}"


class PaymentReceipt(models.Model):
    """收款记录：收了多少合同款。收款 ≠ 收入，只影响递延余额。"""

    contract = models.ForeignKey(Contract, related_name="payments", on_delete=models.CASCADE)
    received_on = models.DateField("收款日期")
    amount = models.DecimalField("收款金额", max_digits=14, decimal_places=2)
    reference = models.CharField("收款单号", max_length=60, blank=True, default="")

    class Meta:
        ordering = ["contract", "received_on", "id"]


class AcceptanceEvidence(models.Model):
    """验收证据：实施类履约义务确认收入的前提。"""

    line = models.OneToOneField(
        ContractLine, related_name="acceptance", on_delete=models.CASCADE
    )
    accepted_on = models.DateField("验收日期")
    reference = models.CharField("验收单号", max_length=60)
    note = models.TextField("说明", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class UsageRecord(models.Model):
    """用量记录：按量服务的确认依据。"""

    line = models.ForeignKey(ContractLine, related_name="usage_records", on_delete=models.CASCADE)
    period = models.CharField("所属期间", max_length=7)  # YYYY-MM
    quantity = models.DecimalField("用量", max_digits=14, decimal_places=2)
    recorded_on = models.DateField("录入日期", auto_now_add=True)

    class Meta:
        ordering = ["line", "period", "id"]


class ScheduleEntry(models.Model):
    """确认计划条目：某履约义务在某期间应/已确认的金额及确认依据。"""

    line = models.ForeignKey(ContractLine, related_name="schedule", on_delete=models.CASCADE)
    period = models.CharField("所属期间", max_length=7)  # YYYY-MM
    amount = models.DecimalField("金额", max_digits=14, decimal_places=2)
    status = models.CharField(
        "状态", max_length=12, choices=EntryStatus.choices, default=EntryStatus.PLANNED
    )
    basis_type = models.CharField("确认依据", max_length=20, choices=BasisType.choices)
    basis_note = models.CharField("依据说明", max_length=200, blank=True, default="")
    recognized_at = models.DateTimeField("确认时间", null=True, blank=True)

    class Meta:
        ordering = ["line", "period", "id"]

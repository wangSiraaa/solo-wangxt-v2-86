"""
核算数据模型（PostgreSQL）。

三条主线严格分开：
  1. 合同：签约金额（合同 + 履约义务上的独立售价/交易价格分摊）
  2. 收款/开票：Invoice / Payment（开票不等于收入）
  3. 收入确认：RevenueRecognitionLine（满足履约进度后才生成确认行）

所有金额一律 DecimalField，max_digits=14, decimal_places=2。
"""
from django.db import models

MONEY_KWARGS = dict(max_digits=14, decimal_places=2)

OBLIGATION_TYPES = [
    ("subscription", "账号订阅"),
    ("implementation", "一次性实施"),
    ("usage", "按量服务"),
]

LINE_STATUS = [
    ("recognized", "已确认"),
    ("pending", "待确认"),
]


class Contract(models.Model):
    number = models.CharField("合同编号", max_length=32, unique=True)
    customer = models.CharField("客户", max_length=128)
    signed_on = models.DateField("签订日期")
    # 合同约定的固定对价（按量部分按 0 计入，待用量发生时确认）
    fixed_price = models.DecimalField("合同固定对价", **MONEY_KWARGS)

    class Meta:
        verbose_name = "合同"
        verbose_name_plural = verbose_name
        ordering = ["number"]

    def __str__(self):
        return f"{self.number} - {self.customer}"


class PerformanceObligation(models.Model):
    """合同中的单项履约义务及其独立售价(SSP)与分摊后的交易价格。"""

    contract = models.ForeignKey(
        Contract, verbose_name="合同", related_name="obligations",
        on_delete=models.CASCADE,
    )
    code = models.CharField("合同项编号", max_length=16)
    name = models.CharField("履约义务", max_length=128)
    obligation_type = models.CharField("类型", max_length=16, choices=OBLIGATION_TYPES)

    # 独立售价（示例政策：由合同基础数据直接给出的 SSP 单价 × 数量/月数）
    ssp_unit_price = models.DecimalField("SSP 单价", **MONEY_KWARGS)
    ssp_quantity = models.IntegerField("SSP 计量数量(月/项/预估用量)", default=1)
    standalone_selling_price = models.DecimalField("独立售价 SSP 合计", **MONEY_KWARGS)

    # 按 SSP 比例分摊折扣后的交易价格（rebuild 时重算）
    allocated_price = models.DecimalField("分摊交易价格", **MONEY_KWARGS, default=0)

    # 订阅起止 / 实施验收基准日 / 按量预估期间
    service_start = models.DateField("服务开始日", null=True, blank=True)
    service_end = models.DateField("服务结束日", null=True, blank=True)

    # 按量服务：用量计量单位，例如「次」「千次调用」
    usage_unit = models.CharField("用量单位", max_length=16, blank=True, default="")

    class Meta:
        verbose_name = "履约义务"
        verbose_name_plural = verbose_name
        unique_together = ("contract", "code")
        ordering = ["contract_id", "code"]

    def __str__(self):
        return f"{self.contract_id}/{self.code} {self.name}"


class AcceptanceEvidence(models.Model):
    """实施验收证据。没有证据的实施部分保持「待确认」。"""

    obligation = models.ForeignKey(
        PerformanceObligation, verbose_name="实施义务",
        related_name="acceptance_evidences", on_delete=models.CASCADE,
        limit_choices_to={"obligation_type": "implementation"},
    )
    accepted_on = models.DateField("验收日期")
    portion = models.DecimalField(
        "验收比例", max_digits=6, decimal_places=4,
        help_text="0~1，例如部分验收 0.6",
    )
    document_ref = models.CharField("验收单据号", max_length=64)
    note = models.CharField("说明", max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "验收证据"
        verbose_name_plural = verbose_name
        ordering = ["accepted_on", "id"]

    def __str__(self):
        return f"{self.obligation_id} {self.accepted_on} {self.portion}"


class UsageRecord(models.Model):
    """按量服务的已录入用量。仅按已录入用量确认收入。"""

    obligation = models.ForeignKey(
        PerformanceObligation, verbose_name="按量义务",
        related_name="usage_records", on_delete=models.CASCADE,
        limit_choices_to={"obligation_type": "usage"},
    )
    usage_month = models.DateField("用量所属月份(取每月1日)")
    quantity = models.DecimalField("用量", max_digits=12, decimal_places=2)
    source_ref = models.CharField("用量单据号", max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "用量记录"
        verbose_name_plural = verbose_name
        unique_together = ("obligation", "usage_month")
        ordering = ["usage_month"]

    def __str__(self):
        return f"{self.obligation_id} {self.usage_month:%Y-%m} qty={self.quantity}"


class Invoice(models.Model):
    """开票记录。开票只形成待转销项/应收的核对口径，绝不等同于收入。"""

    contract = models.ForeignKey(
        Contract, verbose_name="合同", related_name="invoices",
        on_delete=models.CASCADE,
    )
    issued_on = models.DateField("开票日期")
    amount = models.DecimalField("开票金额(不含税口径)", **MONEY_KWARGS)
    note = models.CharField("说明", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "开票"
        verbose_name_plural = verbose_name
        ordering = ["issued_on", "id"]


class Payment(models.Model):
    """收款记录（含预收）。现金口径，用于计算递延（现金未履约）余额。"""

    contract = models.ForeignKey(
        Contract, verbose_name="合同", related_name="payments",
        on_delete=models.CASCADE,
    )
    received_on = models.DateField("收款日期")
    amount = models.DecimalField("收款金额", **MONEY_KWARGS)
    is_prepayment = models.BooleanField("预收(服务未开通)", default=False)
    note = models.CharField("说明", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "收款"
        verbose_name_plural = verbose_name
        ordering = ["received_on", "id"]


class RevenueRecognitionLine(models.Model):
    """
    收入确认计划表行。每次依据录入的验收/用量数据重建（幂等）。
      - 订阅：每个服务月一行，月末为确认依据日，整月通过后已确认
      - 实施：每份验收证据一行，确认依据日=验收日
      - 按量：每条用量一行，确认依据日=用量月末
    """

    obligation = models.ForeignKey(
        PerformanceObligation, verbose_name="履约义务",
        related_name="recognition_lines", on_delete=models.CASCADE,
    )
    period_start = models.DateField("确认期间起")
    period_end = models.DateField("确认期间止/确认依据日")
    amount = models.DecimalField("确认金额", **MONEY_KWARGS)
    status = models.CharField("状态", max_length=16, choices=LINE_STATUS)
    basis = models.CharField("确认依据", max_length=255)
    # 关联生成该行的证据/用量，便于从页面追到合同项与依据
    evidence = models.OneToOneField(
        AcceptanceEvidence, null=True, blank=True,
        related_name="recognition_line", on_delete=models.SET_NULL,
    )
    usage = models.OneToOneField(
        UsageRecord, null=True, blank=True,
        related_name="recognition_line", on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "收入确认计划行"
        verbose_name_plural = verbose_name
        ordering = ["period_end", "id"]
        indexes = [models.Index(fields=["status"])]

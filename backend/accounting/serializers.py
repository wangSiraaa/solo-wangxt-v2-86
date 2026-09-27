from datetime import date
from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import (
    AcceptanceEvidence,
    Contract,
    Invoice,
    Payment,
    PerformanceObligation,
    RevenueRecognitionLine,
    UsageRecord,
)
from .services import rebuild_contract


class ObligationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceObligation
        fields = [
            "id", "code", "name", "obligation_type",
            "ssp_unit_price", "ssp_quantity", "standalone_selling_price",
            "allocated_price",
            "service_start", "service_end", "usage_unit",
        ]
        read_only_fields = ["allocated_price"]


class ContractSerializer(serializers.ModelSerializer):
    obligations = ObligationSerializer(many=True)

    class Meta:
        model = Contract
        fields = ["id", "number", "customer", "signed_on", "fixed_price", "obligations"]

    def validate_obligations(self, value):
        if not value:
            raise serializers.ValidationError("合同至少包含一项履约义务。")
        return value

    def create(self, validated_data):
        obligations_data = validated_data.pop("obligations")
        contract = Contract.objects.create(**validated_data)
        for item in obligations_data:
            PerformanceObligation.objects.create(contract=contract, **item)
        rebuild_contract(contract)
        return contract

    def update(self, instance, validated_data):
        obligations_data = validated_data.pop("obligations", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if obligations_data is not None:
            instance.obligations.all().delete()
            for item in obligations_data:
                PerformanceObligation.objects.create(contract=instance, **item)
        rebuild_contract(instance)
        return instance


class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcceptanceEvidence
        fields = ["id", "obligation", "accepted_on", "portion", "document_ref", "note"]

    def validate(self, attrs):
        obligation = attrs["obligation"]
        if obligation.obligation_type != "implementation":
            raise serializers.ValidationError("只有一次性实施义务可以录入验收证据。")
        total = obligation.acceptance_evidences.exclude(
            pk=getattr(self.instance, "pk", None)
        ).aggregate(total=Sum("portion"))["total"] or Decimal("0")
        if total + attrs["portion"] > Decimal("1.0001"):
            raise serializers.ValidationError(
                f"累计验收比例不得超过 100%（已有 {total}）。"
            )
        return attrs


class UsageRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageRecord
        fields = ["id", "obligation", "usage_month", "quantity", "source_ref"]

    def validate(self, attrs):
        obligation = attrs["obligation"]
        if obligation.obligation_type != "usage":
            raise serializers.ValidationError("只能对按量服务义务录入用量。")
        # 用量统一记为所属月 1 日
        attrs["usage_month"] = attrs["usage_month"].replace(day=1)
        return attrs


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ["id", "issued_on", "amount", "note"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "received_on", "amount", "is_prepayment", "note"]


class RecognitionLineSerializer(serializers.ModelSerializer):
    contract_id = serializers.IntegerField(source="obligation.contract_id", read_only=True)
    contract_number = serializers.CharField(source="obligation.contract.number", read_only=True)
    customer = serializers.CharField(source="obligation.contract.customer", read_only=True)
    obligation_code = serializers.CharField(source="obligation.code", read_only=True)
    obligation_name = serializers.CharField(source="obligation.name", read_only=True)
    obligation_type = serializers.CharField(source="obligation.obligation_type", read_only=True)

    class Meta:
        model = RevenueRecognitionLine
        fields = [
            "id", "contract_id", "contract_number", "customer",
            "obligation_code", "obligation_name", "obligation_type",
            "period_start", "period_end", "amount", "status", "basis",
        ]


def line_is_recognized(line: RevenueRecognitionLine, as_of: date | None) -> bool:
    """
    统一的截止日门控：确认依据日(period_end)已到才算已确认。
      - 订阅：status=pending，但月末≤as_of 即已确认
      - 实施/按量：status=recognized，但验收日/用量月末>as_of 时仍不得确认
      - 待确认行 period_end=9999-12-31，永不计入
    """
    if as_of is None:
        as_of = date.today()
    return line.period_end <= as_of


def recognized_amount(lines, as_of: date) -> Decimal:
    total = Decimal("0")
    for line in lines:
        if line_is_recognized(line, as_of):
            total += line.amount
    return total

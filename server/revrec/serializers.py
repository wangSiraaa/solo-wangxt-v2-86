from rest_framework import serializers

from .models import (
    AcceptanceEvidence,
    Contract,
    ContractLine,
    PaymentReceipt,
    ScheduleEntry,
    UsageRecord,
)
from .services import contract_totals, line_recognized


class ScheduleEntrySerializer(serializers.ModelSerializer):
    basis_type_display = serializers.CharField(source="get_basis_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ScheduleEntry
        fields = [
            "id", "period", "amount", "status", "status_display",
            "basis_type", "basis_type_display", "basis_note", "recognized_at",
        ]


class AcceptanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcceptanceEvidence
        fields = ["id", "accepted_on", "reference", "note", "created_at"]


class UsageRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageRecord
        fields = ["id", "period", "quantity", "recorded_on"]


class ContractLineSerializer(serializers.ModelSerializer):
    line_type_display = serializers.CharField(source="get_line_type_display", read_only=True)
    schedule = ScheduleEntrySerializer(many=True, read_only=True)
    acceptance = AcceptanceSerializer(read_only=True)
    usage_records = UsageRecordSerializer(many=True, read_only=True)
    recognized_amount = serializers.SerializerMethodField()
    pending_amount = serializers.SerializerMethodField()

    class Meta:
        model = ContractLine
        fields = [
            "id", "sort", "name", "line_type", "line_type_display",
            "ssp", "allocated_price",
            "service_start", "service_end",
            "estimated_units", "unit_label", "usage_unit_price",
            "recognized_amount", "pending_amount",
            "schedule", "acceptance", "usage_records",
        ]

    def get_recognized_amount(self, obj):
        return line_recognized(obj)

    def get_pending_amount(self, obj):
        if obj.allocated_price is None:
            return None
        return obj.allocated_price - line_recognized(obj)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentReceipt
        fields = ["id", "received_on", "amount", "reference"]


class ContractLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractLine
        fields = [
            "sort", "name", "line_type", "ssp",
            "service_start", "service_end",
            "estimated_units", "unit_label",
        ]


class ContractSerializer(serializers.ModelSerializer):
    lines = ContractLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    totals = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "id", "number", "customer", "signed_on", "total_price", "note",
            "lines", "payments", "totals",
        ]

    def get_totals(self, obj):
        return contract_totals(obj)


class ContractCreateSerializer(serializers.ModelSerializer):
    lines = ContractLineWriteSerializer(many=True)

    class Meta:
        model = Contract
        fields = ["number", "customer", "signed_on", "total_price", "note", "lines"]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        contract = Contract.objects.create(**validated_data)
        for i, line in enumerate(lines_data):
            line.setdefault("sort", i + 1)
            ContractLine.objects.create(contract=contract, **line)
        return contract

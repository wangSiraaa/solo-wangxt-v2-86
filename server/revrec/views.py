from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Contract, ContractLine, PaymentReceipt
from .serializers import (
    ContractCreateSerializer,
    ContractSerializer,
)
from .services import (
    PolicyError,
    allocate_contract,
    period_matrix,
    recognize_period,
    record_acceptance,
    record_usage,
)


def policy_error(exc: PolicyError) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.prefetch_related(
        "lines__schedule", "lines__usage_records", "lines__acceptance", "payments"
    )

    def get_serializer_class(self):
        if self.action == "create":
            return ContractCreateSerializer
        return ContractSerializer

    def create(self, request, *args, **kwargs):
        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contract = serializer.save()
        try:
            allocate_contract(contract)
        except PolicyError as exc:
            contract.delete()
            return policy_error(exc)
        return Response(
            ContractSerializer(contract).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        """按相对独立售价分摊交易价格并生成订阅确认计划。"""
        contract = self.get_object()
        try:
            allocate_contract(contract)
        except PolicyError as exc:
            return policy_error(exc)
        return Response(ContractSerializer(contract).data)

    @action(detail=True, methods=["post"])
    def payments(self, request, pk=None):
        """登记收款。收款只影响递延余额，不确认收入。"""
        contract = self.get_object()
        try:
            amount = Decimal(str(request.data.get("amount")))
        except (InvalidOperation, TypeError):
            return Response({"detail": "收款金额格式不正确。"}, status=400)
        if amount <= 0:
            return Response({"detail": "收款金额必须大于零。"}, status=400)
        payment = PaymentReceipt.objects.create(
            contract=contract,
            received_on=request.data.get("received_on"),
            amount=amount,
            reference=request.data.get("reference", ""),
        )
        return Response({"id": payment.id}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def recognize_period(self, request, pk=None):
        """确认指定期间的订阅类计划（月度服务已提供）。"""
        contract = self.get_object()
        period = request.data.get("period")
        if not period:
            return Response({"detail": "缺少 period 参数（YYYY-MM）。"}, status=400)
        count = recognize_period(contract, period)
        return Response({"period": period, "recognized_entries": count})


class LineActionView(APIView):
    """履约义务行级业务动作：验收证据、用量录入。"""

    def post(self, request, line_id, action_name):
        line = get_object_or_404(ContractLine, pk=line_id)
        try:
            if action_name == "acceptance":
                evidence, entry = record_acceptance(
                    line,
                    accepted_on=request.data.get("accepted_on"),
                    reference=request.data.get("reference", ""),
                    note=request.data.get("note", ""),
                )
                return Response(
                    {"entry_id": entry.id, "period": entry.period, "amount": entry.amount},
                    status=status.HTTP_201_CREATED,
                )
            if action_name == "usage":
                record, entry = record_usage(
                    line,
                    period=request.data.get("period"),
                    quantity=request.data.get("quantity"),
                )
                return Response(
                    {"entry_id": entry.id, "period": entry.period, "amount": entry.amount},
                    status=status.HTTP_201_CREATED,
                )
        except PolicyError as exc:
            return policy_error(exc)
        return Response({"detail": "未知动作。"}, status=404)


class SummaryView(APIView):
    """全局汇总：期间 × 合同 的确认矩阵与各合同递延余额。
    ?as_of=YYYY-MM 时，汇总列给出该期间末的时点快照。"""

    def get(self, request):
        as_of = request.query_params.get("as_of") or None
        return Response(period_matrix(as_of))

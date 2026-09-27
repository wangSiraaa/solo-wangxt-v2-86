from datetime import date
from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AcceptanceEvidence,
    Contract,
    Invoice,
    Payment,
    RevenueRecognitionLine,
    UsageRecord,
)
from .serializers import (
    ContractSerializer,
    EvidenceSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    RecognitionLineSerializer,
    UsageRecordSerializer,
    line_is_recognized,
)
from .services import rebuild_contract, rebuild_recognition_plan


def parse_as_of(request):
    raw = request.query_params.get("as_of")
    if raw:
        return date.fromisoformat(raw)
    return date.today()


class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.prefetch_related(
        "obligations",
        "invoices",
        "payments",
        "obligations__recognition_lines",
        "obligations__acceptance_evidences",
        "obligations__usage_records",
    ).order_by("number")
    serializer_class = ContractSerializer

    @action(detail=True, methods=["get"])
    def check_plan(self, request, pk=None):
        """合同组成 + 开票/收款 + 确认计划 + 余额对照（支持 as_of 截止日）。"""
        contract = self.get_object()
        as_of = parse_as_of(request)

        obligations_out = []
        for o in contract.obligations.order_by("code"):
            lines = list(o.recognition_lines.order_by("period_end", "id"))
            recognized = sum(
                (ln.amount for ln in lines if line_is_recognized(ln, as_of)),
                Decimal("0"),
            )
            obligations_out.append({
                "id": o.id,
                "code": o.code,
                "name": o.name,
                "obligation_type": o.obligation_type,
                "standalone_selling_price": str(o.standalone_selling_price),
                "allocated_price": str(o.allocated_price),
                "service_start": o.service_start,
                "service_end": o.service_end,
                "usage_unit": o.usage_unit,
                "recognized_amount": str(recognized),
                "deferred_amount": str(o.allocated_price - recognized),
                "lines": [
                    {
                        "id": ln.id,
                        "period_start": ln.period_start if ln.period_start.year < 9999 else None,
                        "period_end": ln.period_end if ln.period_end.year < 9999 else None,
                        "amount": str(ln.amount),
                        "status": (
                            "recognized"
                            if line_is_recognized(ln, as_of)
                            else "pending"
                        ),
                        "stored_status": ln.status,
                        "basis": ln.basis,
                    }
                    for ln in lines
                ],
            })

        invoices = [
            {"id": i.id, "issued_on": i.issued_on, "amount": str(i.amount), "note": i.note}
            for i in contract.invoices.order_by("issued_on")
        ]
        payments = [
            {
                "id": p.id, "received_on": p.received_on,
                "amount": str(p.amount), "is_prepayment": p.is_prepayment, "note": p.note,
            }
            for p in contract.payments.order_by("received_on")
        ]

        billed = sum(
            (i.amount for i in contract.invoices.all() if i.issued_on <= as_of),
            Decimal("0"),
        )
        received = sum(
            (p.amount for p in contract.payments.all() if p.received_on <= as_of),
            Decimal("0"),
        )
        recognized = sum(
            (Decimal(o["recognized_amount"]) for o in obligations_out), Decimal("0")
        )

        return Response({
            "as_of": as_of,
            "id": contract.id,
            "number": contract.number,
            "customer": contract.customer,
            "signed_on": contract.signed_on,
            "fixed_price": str(contract.fixed_price),
            "allocated_total": str(
                sum((o.allocated_price for o in contract.obligations.all()), Decimal("0"))
            ),
            "obligations": obligations_out,
            "invoices": invoices,
            "payments": payments,
            "totals": {
                "signed_amount": str(contract.fixed_price),  # 签了多少合同
                "billed_amount": str(billed),                # 开了多少票
                "received_amount": str(received),            # 收了多少钱
                "recognized_revenue": str(recognized),       # 真正确认了多少收入
                "deferred_balance": str(received - recognized),  # 现金口径递延
                "contract_liability": str(contract.fixed_price - recognized),
                "billed_not_recognized": str(billed - recognized),
            },
        })


class EvidenceViewSet(viewsets.ModelViewSet):
    """验收证据：默认限定在 URL 指定合同的实施义务下。"""

    serializer_class = EvidenceSerializer

    def get_queryset(self):
        return AcceptanceEvidence.objects.filter(
            obligation__contract_id=self.kwargs["contract_pk"]
        ).order_by("accepted_on")

    def perform_create(self, serializer):
        evidence = serializer.save()
        rebuild_recognition_plan(evidence.obligation)

    def perform_update(self, serializer):
        evidence = serializer.save()
        rebuild_recognition_plan(evidence.obligation)

    def perform_destroy(self, instance):
        obligation = instance.obligation
        instance.delete()
        rebuild_recognition_plan(obligation)


class UsageRecordViewSet(viewsets.ModelViewSet):
    serializer_class = UsageRecordSerializer

    def get_queryset(self):
        return UsageRecord.objects.filter(
            obligation__contract_id=self.kwargs["contract_pk"]
        ).order_by("usage_month")

    def perform_create(self, serializer):
        record = serializer.save()
        rebuild_recognition_plan(record.obligation)

    def perform_update(self, serializer):
        record = serializer.save()
        rebuild_recognition_plan(record.obligation)

    def perform_destroy(self, instance):
        obligation = instance.obligation
        instance.delete()
        rebuild_recognition_plan(obligation)


class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(
            contract_id=self.kwargs["contract_pk"]
        ).order_by("issued_on")


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(
            contract_id=self.kwargs["contract_pk"]
        ).order_by("received_on")


class RecognitionView(APIView):
    """全量确认计划，可按 ?as_of=YYYY-MM-DD 重算每行的确认状态。"""

    def get(self, request):
        as_of = parse_as_of(request)
        lines = RevenueRecognitionLine.objects.select_related(
            "obligation__contract"
        ).order_by("obligation__contract__number", "period_end", "id")
        data = []
        for ln in lines:
            row = RecognitionLineSerializer(ln).data
            row["period_start"] = ln.period_start if ln.period_start.year < 9999 else None
            row["period_end"] = ln.period_end if ln.period_end.year < 9999 else None
            row["status"] = "recognized" if line_is_recognized(ln, as_of) else "pending"
            data.append(row)
        return Response({"as_of": as_of, "results": data})


class SummaryView(APIView):
    """三问对照：签了多少合同 / 收了多少钱 / 当期确认多少收入。"""

    def get(self, request):
        as_of = parse_as_of(request)
        rows = []
        totals = {
            "signed_amount": Decimal("0"),
            "billed_amount": Decimal("0"),
            "received_amount": Decimal("0"),
            "recognized_revenue": Decimal("0"),
            "deferred_balance": Decimal("0"),
            "contract_liability": Decimal("0"),
        }
        for contract in Contract.objects.prefetch_related(
            "obligations__recognition_lines", "invoices", "payments"
        ).order_by("number"):
            recognized = Decimal("0")
            for o in contract.obligations.all():
                for ln in o.recognition_lines.all():
                    if line_is_recognized(ln, as_of):
                        recognized += ln.amount
            billed = sum(
                (i.amount for i in contract.invoices.all() if i.issued_on <= as_of),
                Decimal("0"),
            )
            received = sum(
                (p.amount for p in contract.payments.all() if p.received_on <= as_of),
                Decimal("0"),
            )
            row = {
                "contract_id": contract.id,
                "number": contract.number,
                "customer": contract.customer,
                "signed_amount": str(contract.fixed_price),
                "billed_amount": str(billed),
                "received_amount": str(received),
                "recognized_revenue": str(recognized),
                "deferred_balance": str(received - recognized),
                "contract_liability": str(contract.fixed_price - recognized),
            }
            rows.append(row)
            totals["signed_amount"] += contract.fixed_price
            totals["billed_amount"] += billed
            totals["received_amount"] += received
            totals["recognized_revenue"] += recognized
            totals["deferred_balance"] += received - recognized
            totals["contract_liability"] += contract.fixed_price - recognized

        totals = {k: str(v) for k, v in totals.items()}
        return Response({"as_of": as_of, "contracts": rows, "totals": totals})


class RebuildView(APIView):
    def post(self, request, contract_pk=None):
        if contract_pk:
            rebuild_contract(Contract.objects.get(pk=contract_pk))
            return Response(status=status.HTTP_204_NO_CONTENT)
        for contract in Contract.objects.all():
            rebuild_contract(contract)
        return Response(status=status.HTTP_204_NO_CONTENT)

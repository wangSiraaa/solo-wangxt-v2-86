from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContractViewSet,
    EvidenceViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    RecognitionView,
    RebuildView,
    SummaryView,
    UsageRecordViewSet,
)

router = DefaultRouter()
router.register(r"contracts", ContractViewSet, basename="contract")

nested = [
    path(
        "contracts/<int:contract_pk>/evidences",
        EvidenceViewSet.as_view({"get": "list", "post": "create"}),
    ),
    path(
        "contracts/<int:contract_pk>/evidences/<int:pk>",
        EvidenceViewSet.as_view({"put": "update", "patch": "partial_update", "delete": "destroy"}),
    ),
    path(
        "contracts/<int:contract_pk>/usage",
        UsageRecordViewSet.as_view({"get": "list", "post": "create"}),
    ),
    path(
        "contracts/<int:contract_pk>/usage/<int:pk>",
        UsageRecordViewSet.as_view({"put": "update", "patch": "partial_update", "delete": "destroy"}),
    ),
    path(
        "contracts/<int:contract_pk>/invoices",
        InvoiceViewSet.as_view({"get": "list", "post": "create"}),
    ),
    path(
        "contracts/<int:contract_pk>/invoices/<int:pk>",
        InvoiceViewSet.as_view({"put": "update", "patch": "partial_update", "delete": "destroy"}),
    ),
    path(
        "contracts/<int:contract_pk>/payments",
        PaymentViewSet.as_view({"get": "list", "post": "create"}),
    ),
    path(
        "contracts/<int:contract_pk>/payments/<int:pk>",
        PaymentViewSet.as_view({"put": "update", "patch": "partial_update", "delete": "destroy"}),
    ),
    path("contracts/<int:contract_pk>/rebuild", RebuildView.as_view()),
]

urlpatterns = [
    path("recognition/", RecognitionView.as_view()),
    path("summary/", SummaryView.as_view()),
    path("rebuild/", RebuildView.as_view()),
] + nested

# router 提供 contracts/ 列表与 contracts/{id}/ 详情
urlpatterns += router.urls

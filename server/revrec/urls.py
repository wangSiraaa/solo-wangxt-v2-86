from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ContractViewSet, LineActionView, SummaryView

router = DefaultRouter()
router.register("contracts", ContractViewSet, basename="contract")

urlpatterns = [
    path("", include(router.urls)),
    path("lines/<int:line_id>/<str:action_name>/", LineActionView.as_view()),
    path("summary/", SummaryView.as_view()),
]

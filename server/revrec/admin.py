from django.contrib import admin

from .models import (
    AcceptanceEvidence,
    Contract,
    ContractLine,
    PaymentReceipt,
    ScheduleEntry,
    UsageRecord,
)

admin.site.register(
    [Contract, ContractLine, PaymentReceipt, AcceptanceEvidence, UsageRecord, ScheduleEntry]
)

from decimal import Decimal

from django.conf import settings
from django.db import models


class Commission(models.Model):
    class Status(models.TextChoices):
        EARNED = "EARNED", "Earned (Pending Weekly Payout)"
        PAID = "PAID", "Paid Out"
        CANCELLED = "CANCELLED", "Cancelled"

    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="commission")
    dropshipper = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="commissions")
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"))
    sales_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EARNED)
    payout = models.ForeignKey("Payout", null=True, blank=True, on_delete=models.SET_NULL, related_name="commissions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.dropshipper.username}: RM{self.commission_amount} (15% on {self.order.order_no})"


class PayoutBatch(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        PARTIAL_FAILED = "PARTIAL_FAILED", "Partially Failed"

    batch_no = models.CharField(max_length=40, unique=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payouts_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.batch_no} ({self.payouts_count} recipients, RM{self.total_amount})"


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing (CHIP Send)"
        PAID = "PAID", "Paid to Bank"
        FAILED = "FAILED", "Transfer Failed"

    batch = models.ForeignKey(PayoutBatch, on_delete=models.CASCADE, related_name="payouts")
    dropshipper = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payouts")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    bank_name = models.CharField(max_length=50)
    bank_account_number = models.CharField(max_length=50)
    bank_account_holder = models.CharField(max_length=150)
    bank_id_number = models.CharField(max_length=30, blank=True)

    chip_send_instruction_id = models.CharField(max_length=100, blank=True)
    chip_send_account_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payout #{self.pk}: {self.dropshipper.username} - RM{self.amount} ({self.status})"

    @property
    def status_badge(self):
        return {
            "PENDING": "warning",
            "PROCESSING": "info",
            "PAID": "success",
            "FAILED": "danger",
        }.get(self.status, "secondary")

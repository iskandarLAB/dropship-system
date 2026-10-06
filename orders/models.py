from decimal import Decimal

from django.conf import settings
from django.db import models

from catalog.models import MALAYSIAN_STATES, Variant


class Order(models.Model):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "AWAITING_PAYMENT", "Awaiting payment"
        PAID = "PAID", "Paid - to ship"
        SHIPPED = "SHIPPED", "Shipped"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NEEDS_REFUND = "NEEDS_REFUND", "Paid after expiry - needs refund"

    # Statuses that count as real sales.
    SALE_STATUSES = (Status.PAID, Status.SHIPPED, Status.COMPLETED)

    order_no = models.CharField(max_length=30, unique=True, blank=True)
    dropshipper = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT)

    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=20)
    address = models.TextField()
    postcode = models.CharField(max_length=10)
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=40, choices=MALAYSIAN_STATES)
    notes = models.CharField(max_length=255, blank=True)

    subtotal_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    shipping_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    total_payable = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))

    stock_reserved = models.BooleanField(default=False)
    courier = models.CharField(max_length=50, blank=True)
    tracking_no = models.CharField(max_length=80, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    shipped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_no or f"Order #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.order_no:
            self.order_no = f"DS-{self.created_at:%Y%m%d}-{self.pk:05d}"
            super().save(update_fields=["order_no"])

    @property
    def total_cents(self):
        return int((self.total_payable * 100).quantize(Decimal("1")))

    @property
    def commission_amount(self):
        if hasattr(self, "commission"):
            return self.commission.commission_amount
        return (self.total_sales * Decimal("0.15")).quantize(Decimal("0.01"))

    @property
    def profit(self):
        return self.commission_amount

    @property
    def is_payable(self):
        return self.status == self.Status.AWAITING_PAYMENT

    @property
    def status_badge(self):
        return {
            "AWAITING_PAYMENT": "warning",
            "PAID": "primary",
            "SHIPPED": "info",
            "COMPLETED": "success",
            "CANCELLED": "secondary",
            "NEEDS_REFUND": "danger",
        }.get(self.status, "secondary")


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Snapshot of dropship price")
    unit_sell_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Dropshipper's selling price")

    def __str__(self):
        return f"{self.variant} x{self.quantity}"

    @property
    def line_cost(self):
        return self.unit_cost * self.quantity

    @property
    def line_sales(self):
        return self.unit_sell_price * self.quantity

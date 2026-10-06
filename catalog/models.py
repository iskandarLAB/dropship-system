from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

MALAYSIAN_STATES = [
    ("Johor", "Johor"),
    ("Kedah", "Kedah"),
    ("Kelantan", "Kelantan"),
    ("Melaka", "Melaka"),
    ("Negeri Sembilan", "Negeri Sembilan"),
    ("Pahang", "Pahang"),
    ("Perak", "Perak"),
    ("Perlis", "Perlis"),
    ("Pulau Pinang", "Pulau Pinang"),
    ("Selangor", "Selangor"),
    ("Terengganu", "Terengganu"),
    ("W.P. Kuala Lumpur", "W.P. Kuala Lumpur"),
    ("W.P. Putrajaya", "W.P. Putrajaya"),
    ("Sabah", "Sabah"),
    ("Sarawak", "Sarawak"),
    ("W.P. Labuan", "W.P. Labuan"),
]


class Product(models.Model):
    name = models.CharField(max_length=150)
    sku_prefix = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/", blank=True)
    dropship_price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Price the dropshipper pays HQ (RM)"
    )
    suggested_retail_price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Recommended selling price to end customer (RM)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        return sum(v.stock for v in self.variants.all())


class Variant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.CharField(max_length=20)
    colour = models.CharField(max_length=40)
    sku = models.CharField(max_length=50, unique=True)
    stock = models.PositiveIntegerField(default=0)
    stock_updated_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["product__name", "colour", "sort_order", "size"]
        unique_together = [("product", "size", "colour")]

    def __str__(self):
        return f"{self.product.name} - {self.colour} / {self.size}"

    @property
    def is_stale(self):
        if not self.stock_updated_at:
            return True
        return timezone.now() - self.stock_updated_at > timedelta(hours=settings.STOCK_STALE_HOURS)

    @property
    def stock_level(self):
        if self.stock == 0:
            return "out"
        if self.stock <= 10:
            return "low"
        return "ok"


class StockLog(models.Model):
    class Reason(models.TextChoices):
        HQ_UPDATE = "HQ_UPDATE", "HQ stock update"
        ORDER = "ORDER", "Reserved by order"
        RESTORE = "RESTORE", "Restored (order cancelled)"
        ADMIN = "ADMIN", "Admin adjustment"

    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name="logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    old_qty = models.IntegerField()
    new_qty = models.IntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def delta(self):
        return self.new_qty - self.old_qty


class ShippingRate(models.Model):
    class Region(models.TextChoices):
        WM = "WM", "West Malaysia"
        SABAH = "SABAH", "Sabah"
        SARAWAK = "SARAWAK", "Sarawak"
        LABUAN = "LABUAN", "Labuan"

    region = models.CharField(max_length=10, choices=Region.choices, unique=True)
    fee = models.DecimalField(max_digits=8, decimal_places=2)

    DEFAULTS = {"WM": Decimal("8.00"), "SABAH": Decimal("12.00"),
                "SARAWAK": Decimal("12.00"), "LABUAN": Decimal("12.00")}

    def __str__(self):
        return f"{self.get_region_display()}: RM{self.fee}"

    @staticmethod
    def region_for_state(state):
        return {"Sabah": "SABAH", "Sarawak": "SARAWAK", "W.P. Labuan": "LABUAN"}.get(state, "WM")

    @classmethod
    def fee_for_state(cls, state):
        region = cls.region_for_state(state)
        rate = cls.objects.filter(region=region).first()
        return rate.fee if rate else cls.DEFAULTS[region]

    @classmethod
    def as_state_map(cls):
        """{state: fee} map for the order form JS."""
        return {s: str(cls.fee_for_state(s)) for s, _ in MALAYSIAN_STATES}

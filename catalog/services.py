from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Min
from django.utils import timezone

from .models import StockLog, Variant


@transaction.atomic
def hq_bulk_update(user, qty_by_variant_id):
    """Overwrite stock for many variants at once.

    Every submitted variant gets `stock_updated_at` refreshed (even if the
    quantity didn't change) because HQ has confirmed the count.
    Returns the number of variants whose quantity changed.
    """
    now = timezone.now()
    variants = list(Variant.objects.select_for_update().filter(id__in=qty_by_variant_id.keys()))
    logs, changed = [], 0
    for v in variants:
        new_qty = int(qty_by_variant_id[v.id])
        if new_qty < 0:
            raise ValueError(f"Stock for {v.sku} cannot be negative.")
        if new_qty != v.stock:
            logs.append(StockLog(variant=v, user=user, old_qty=v.stock, new_qty=new_qty,
                                 reason=StockLog.Reason.HQ_UPDATE))
            changed += 1
        v.stock = new_qty
        v.stock_updated_at = now
    Variant.objects.bulk_update(variants, ["stock", "stock_updated_at"])
    StockLog.objects.bulk_create(logs)
    return changed


def freshness_summary():
    """Info about how fresh HQ's stock data is (active products only)."""
    qs = Variant.objects.filter(product__is_active=True)
    agg = qs.aggregate(oldest=Min("stock_updated_at"), latest=Max("stock_updated_at"))
    cutoff = timezone.now() - timedelta(hours=settings.STOCK_STALE_HOURS)
    stale_count = qs.filter(stock_updated_at__lt=cutoff).count() + qs.filter(
        stock_updated_at__isnull=True
    ).count()
    oldest = agg["oldest"]
    due_at = oldest + timedelta(hours=settings.STOCK_STALE_HOURS) if oldest else None
    return {
        "latest": agg["latest"],
        "oldest": oldest,
        "stale_count": stale_count,
        "is_stale": stale_count > 0,
        "due_at": due_at,
        "total": qs.count(),
    }

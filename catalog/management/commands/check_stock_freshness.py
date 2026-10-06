from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from catalog.models import Variant


class Command(BaseCommand):
    help = "List variants whose stock has not been updated by HQ within STOCK_STALE_HOURS."

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(hours=settings.STOCK_STALE_HOURS)
        stale = Variant.objects.filter(product__is_active=True).filter(
            Q(stock_updated_at__lt=cutoff) | Q(stock_updated_at__isnull=True)
        )
        if not stale.exists():
            self.stdout.write(self.style.SUCCESS("All stock updated within the last %sh." % settings.STOCK_STALE_HOURS))
            return
        self.stdout.write(self.style.WARNING(f"{stale.count()} stale variant(s):"))
        for v in stale.select_related("product"):
            self.stdout.write(f"  {v.sku:20} {v}  last update: {v.stock_updated_at or 'never'}")

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from catalog.models import Product, Variant, StockLog, ShippingRate
from catalog.services import hq_bulk_update, freshness_summary


class CatalogTests(TestCase):
    def setUp(self):
        self.hq_user = User.objects.create_user(
            username="hq_tester", password="password", role=User.Role.HQ, status=User.Status.APPROVED
        )
        self.product = Product.objects.create(
            name="Classic Tee", sku_prefix="TEE-CLS", dropship_price=Decimal("20.00"),
            suggested_retail_price=Decimal("40.00"), is_active=True
        )
        self.v1 = Variant.objects.create(
            product=self.product, size="M", colour="Black", sku="TEE-CLS-BLK-M", stock=15
        )
        self.v2 = Variant.objects.create(
            product=self.product, size="L", colour="Black", sku="TEE-CLS-BLK-L", stock=10
        )

    def test_hq_bulk_update_records_stock_log_and_timestamp(self):
        updates = {self.v1.id: 25, self.v2.id: 10}  # v1 changed (+10), v2 unchanged
        changed = hq_bulk_update(self.hq_user, updates)
        
        self.assertEqual(changed, 1)
        self.v1.refresh_from_db()
        self.v2.refresh_from_db()

        self.assertEqual(self.v1.stock, 25)
        self.assertIsNotNone(self.v1.stock_updated_at)
        self.assertIsNotNone(self.v2.stock_updated_at)

        logs = StockLog.objects.filter(variant=self.v1)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().old_qty, 15)
        self.assertEqual(logs.first().new_qty, 25)
        self.assertEqual(logs.first().reason, StockLog.Reason.HQ_UPDATE)

    def test_freshness_summary_detects_stale_stock(self):
        # Set stock_updated_at to 25 hours ago
        stale_time = timezone.now() - timedelta(hours=25)
        Variant.objects.all().update(stock_updated_at=stale_time)

        freshness = freshness_summary()
        self.assertTrue(freshness["is_stale"])
        self.assertEqual(freshness["stale_count"], 2)

        # Update stock -> should become fresh
        hq_bulk_update(self.hq_user, {self.v1.id: 20})
        freshness_now = freshness_summary()
        # v2 is still stale
        self.assertEqual(freshness_now["stale_count"], 1)

    def test_shipping_rate_determination(self):
        ShippingRate.objects.create(region="WM", fee=Decimal("8.00"))
        ShippingRate.objects.create(region="SABAH", fee=Decimal("12.00"))

        self.assertEqual(ShippingRate.fee_for_state("Selangor"), Decimal("8.00"))
        self.assertEqual(ShippingRate.fee_for_state("Sabah"), Decimal("12.00"))
        self.assertEqual(ShippingRate.fee_for_state("Sarawak"), Decimal("12.00"))

    def test_affiliate_store_and_public_customer_order(self):
        from orders.models import Order
        from django.urls import reverse

        ShippingRate.objects.get_or_create(region="WM", defaults={"fee": Decimal("8.00")})
        dropshipper = User.objects.create_user(
            username="affiliate_seller",
            password="password",
            role=User.Role.DROPSHIPPER,
            status=User.Status.APPROVED,
            shop_name="Eksklusif Ali Boutique"
        )

        # 1. Customer visits storefront (no login required)
        resp = self.client.get(reverse("catalog:affiliate_store", args=[dropshipper.username]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Eksklusif Ali Boutique")

        # 2. Customer places order via affiliate checkout (no login required)
        checkout_url = reverse("catalog:affiliate_order", args=[dropshipper.username])
        order_data = {
            "customer_name": "Pak Mat",
            "customer_phone": "0129988776",
            "address": "No 5 Kampung Melayu",
            "postcode": "50000",
            "city": "Kuala Lumpur",
            "state": "W.P. Kuala Lumpur",
            "notes": "Tinggalkan di pintu",
            "item_variant": [self.v1.id],
            "item_qty": [2],
            "item_price": ["999.00"],  # Customer tries to tamper price; view locks to official SRP (RM40.00)
        }
        resp_post = self.client.post(checkout_url, data=order_data)
        self.assertEqual(resp_post.status_code, 302)  # Redirects to payment

        order = Order.objects.get(customer_name="Pak Mat")
        self.assertEqual(order.dropshipper, dropshipper)
        self.assertEqual(order.total_sales, Decimal("80.00"))  # 2 * RM40 SRP
        self.assertEqual(order.shipping_fee, Decimal("8.00"))
        self.assertEqual(order.total_payable, Decimal("88.00"))
        self.assertEqual(order.commission_amount, Decimal("12.00"))  # 15% of RM80

        self.v1.refresh_from_db()
        self.assertEqual(self.v1.stock, 13)  # 15 - 2 = 13 (stock reserved)


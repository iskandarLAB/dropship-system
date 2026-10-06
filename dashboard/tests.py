from decimal import Decimal
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Product, Variant, ShippingRate
from orders.services import place_order, mark_paid


class DashboardTests(TestCase):
    def setUp(self):
        ShippingRate.objects.create(region="WM", fee=Decimal("8.00"))
        self.dropshipper = User.objects.create_user(
            username="dash_ds", password="password", role=User.Role.DROPSHIPPER, status=User.Status.APPROVED
        )
        self.hq_user = User.objects.create_user(
            username="dash_hq", password="password", role=User.Role.HQ, status=User.Status.APPROVED
        )
        self.admin = User.objects.create_superuser(
            username="dash_admin", email="admin@test.com", password="password",
            role=User.Role.ADMIN, status=User.Status.APPROVED
        )

        self.product = Product.objects.create(
            name="Hoodie", sku_prefix="HD", dropship_price=Decimal("40.00"),
            suggested_retail_price=Decimal("80.00"), is_active=True
        )
        self.variant = Variant.objects.create(
            product=self.product, size="L", colour="Black", sku="HD-BLK-L", stock=20
        )

    def test_dropshipper_dashboard_sales_and_profit(self):
        self.client.force_login(self.dropshipper)
        order = place_order(
            self.dropshipper,
            {
                "customer_name": "Buyer 1", "customer_phone": "0123456789",
                "address": "Street", "postcode": "50000", "city": "KL", "state": "Selangor"
            },
            [{"variant_id": self.variant.id, "qty": 2, "sell_price": Decimal("80.00")}]
        )
        # Unpaid order should NOT be counted in sales
        resp = self.client.get(reverse("dashboard:dropshipper"))
        self.assertEqual(resp.context["total_sales"], Decimal("0.00"))

        # Once paid -> counted!
        mark_paid(order, order.total_cents)
        resp = self.client.get(reverse("dashboard:dropshipper"))
        self.assertEqual(resp.context["total_profit"], Decimal("24.00"))  # 15% commission on 160 sales

    def test_role_permissions(self):
        # Dropshipper cannot access HQ home or admin panel
        self.client.force_login(self.dropshipper)
        resp1 = self.client.get(reverse("dashboard:hq_home"))
        self.assertEqual(resp1.status_code, 403)
        resp2 = self.client.get(reverse("dashboard:admin_panel"))
        self.assertEqual(resp2.status_code, 403)

        # HQ can access HQ home
        self.client.force_login(self.hq_user)
        resp3 = self.client.get(reverse("dashboard:hq_home"))
        self.assertEqual(resp3.status_code, 200)

        # Admin can access admin panel
        self.client.force_login(self.admin)
        resp4 = self.client.get(reverse("dashboard:admin_panel"))
        self.assertEqual(resp4.status_code, 200)

    def test_dropshipper_leaderboard(self):
        # Create second dropshipper with higher sales
        ds2 = User.objects.create_user(
            username="ds_champ", password="password", role=User.Role.DROPSHIPPER, status=User.Status.APPROVED, shop_name="Champ Store"
        )
        # Order for ds2 (3x RM80 = RM240)
        order2 = place_order(
            ds2,
            {"customer_name": "VIP", "customer_phone": "011222333", "address": "Jln", "postcode": "50000", "city": "KL", "state": "Selangor"},
            [{"variant_id": self.variant.id, "qty": 3, "sell_price": Decimal("80.00")}]
        )
        mark_paid(order2, order2.total_cents)

        # Order for self.dropshipper (1x RM80 = RM80)
        order1 = place_order(
            self.dropshipper,
            {"customer_name": "Regular", "customer_phone": "011444555", "address": "Jln", "postcode": "50000", "city": "KL", "state": "Selangor"},
            [{"variant_id": self.variant.id, "qty": 1, "sell_price": Decimal("80.00")}]
        )
        mark_paid(order1, order1.total_cents)

        self.client.force_login(self.dropshipper)
        resp = self.client.get(reverse("dashboard:dropshipper"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("leaderboard", resp.context)

        leaderboard = resp.context["leaderboard"]
        self.assertGreaterEqual(len(leaderboard), 2)
        # Rank 1 should be ds_champ with RM240 sales
        self.assertEqual(leaderboard[0]["name"], "Champ Store")
        self.assertEqual(leaderboard[0]["total_sales"], Decimal("240.00"))
        # self.dropshipper is rank 2 with RM80 sales
        self.assertEqual(resp.context["user_rank"], 2)
        self.assertEqual(resp.context["gap_to_next_rank"], Decimal("160.00"))  # 240 - 80 = 160


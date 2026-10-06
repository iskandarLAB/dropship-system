from decimal import Decimal
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import Product, Variant, ShippingRate
from orders.services import place_order, mark_paid, cancel_order
from payouts.models import Commission, PayoutBatch, Payout
from payouts.services import (
    credit_commission_for_order,
    cancel_commission_for_order,
    get_dropshipper_commission_stats,
    create_weekly_payout_batch,
    execute_payout_batch,
)


class PayoutsTests(TestCase):
    def setUp(self):
        ShippingRate.objects.create(region="WM", fee=Decimal("8.00"))

        # Dropshipper with bank details
        self.ds_with_bank = User.objects.create_user(
            username="ds_bank",
            password="password",
            role=User.Role.DROPSHIPPER,
            status=User.Status.APPROVED,
            bank_name="MAYBANK",
            bank_account_number="1234567890",
            bank_account_holder="Ali bin Abu",
            bank_id_number="900101015555",
        )

        # Dropshipper without bank details
        self.ds_no_bank = User.objects.create_user(
            username="ds_nobank",
            password="password",
            role=User.Role.DROPSHIPPER,
            status=User.Status.APPROVED,
        )

        # Admin user
        self.admin = User.objects.create_superuser(
            username="admin_payout",
            email="admin@test.com",
            password="password",
            role=User.Role.ADMIN,
            status=User.Status.APPROVED,
        )

        self.product = Product.objects.create(
            name="Classic Jersey",
            sku_prefix="CJ",
            dropship_price=Decimal("20.00"),
            suggested_retail_price=Decimal("50.00"),
            is_active=True,
        )
        self.variant = Variant.objects.create(
            product=self.product, size="M", colour="Black", sku="CJ-BLK-M", stock=50
        )

    def _create_and_pay_order(self, dropshipper, qty=2, sell_price=Decimal("50.00")):
        customer = {
            "customer_name": "Test Customer",
            "customer_phone": "0123456789",
            "address": "Jalan Bangsar",
            "postcode": "59000",
            "city": "KL",
            "state": "W.P. Kuala Lumpur",
        }
        order = place_order(
            dropshipper,
            customer,
            [{"variant_id": self.variant.id, "qty": qty, "sell_price": sell_price}],
        )
        mark_paid(order, order.total_cents)
        return order

    def test_commission_earned_on_order_paid(self):
        # 2 units * RM50 = RM100 total sales. 15% commission = RM15.00
        order = self._create_and_pay_order(self.ds_with_bank, qty=2, sell_price=Decimal("50.00"))
        
        comm = Commission.objects.filter(order=order).first()
        self.assertIsNotNone(comm)
        self.assertEqual(comm.dropshipper, self.ds_with_bank)
        self.assertEqual(comm.rate_percent, Decimal("15.00"))
        self.assertEqual(comm.sales_amount, Decimal("100.00"))
        self.assertEqual(comm.commission_amount, Decimal("15.00"))
        self.assertEqual(comm.status, Commission.Status.EARNED)

        stats = get_dropshipper_commission_stats(self.ds_with_bank)
        self.assertEqual(stats["total_earned"], Decimal("15.00"))
        self.assertEqual(stats["pending_payout"], Decimal("15.00"))
        self.assertEqual(stats["paid_out"], Decimal("0.00"))

    def test_commission_cancelled_when_order_cancelled(self):
        order = self._create_and_pay_order(self.ds_with_bank, qty=1, sell_price=Decimal("50.00"))
        comm = Commission.objects.get(order=order)
        self.assertEqual(comm.status, Commission.Status.EARNED)

        cancel_order(order, self.admin, "Order refunded by HQ")
        comm.refresh_from_db()
        self.assertEqual(comm.status, Commission.Status.CANCELLED)

    def test_create_and_execute_weekly_payout_batch(self):
        # Order for dropshipper with bank details (RM100 sales -> RM15 commission)
        self._create_and_pay_order(self.ds_with_bank, qty=2, sell_price=Decimal("50.00"))
        # Order for dropshipper without bank details (RM50 sales -> RM7.50 commission)
        self._create_and_pay_order(self.ds_no_bank, qty=1, sell_price=Decimal("50.00"))

        batch = create_weekly_payout_batch(admin_user=self.admin)
        self.assertIsNotNone(batch)
        self.assertEqual(batch.payouts.count(), 1)

        # Dropshipper with bank is batched
        payout_bank = batch.payouts.get(dropshipper=self.ds_with_bank)
        self.assertEqual(payout_bank.amount, Decimal("15.00"))
        self.assertEqual(payout_bank.status, Payout.Status.PENDING)

        # Dropshipper without bank has commission safely retained as EARNED without being lost
        nobank_comm = Commission.objects.get(dropshipper=self.ds_no_bank)
        self.assertEqual(nobank_comm.status, Commission.Status.EARNED)
        self.assertIsNone(nobank_comm.payout)

        # Execute payout batch via simulator
        with override_settings(CHIP_SEND_SIMULATOR=True):
            execute_payout_batch(batch)

        batch.refresh_from_db()
        payout_bank.refresh_from_db()
        self.assertEqual(payout_bank.status, Payout.Status.PAID)
        self.assertTrue(payout_bank.chip_send_instruction_id.startswith("CHIP-SEND-"))

        # Commission should now be PAID
        comm = Commission.objects.get(order__dropshipper=self.ds_with_bank)
        self.assertEqual(comm.status, Commission.Status.PAID)

        # Verify stats reflect paid out
        stats = get_dropshipper_commission_stats(self.ds_with_bank)
        self.assertEqual(stats["total_earned"], Decimal("15.00"))
        self.assertEqual(stats["pending_payout"], Decimal("0.00"))
        self.assertEqual(stats["paid_out"], Decimal("15.00"))

    def test_payout_views_and_permissions(self):
        # Dropshipper views their payout ledger
        self.client.force_login(self.ds_with_bank)
        resp = self.client.get(reverse("payouts:dropshipper_payouts"))
        self.assertEqual(resp.status_code, 200)

        # Dropshipper cannot access admin payout batch
        resp_admin = self.client.get(reverse("payouts:admin_payouts"))
        self.assertEqual(resp_admin.status_code, 403)

        # Admin can access payout management panel
        self.client.force_login(self.admin)
        resp_admin_ok = self.client.get(reverse("payouts:admin_payouts"))
        self.assertEqual(resp_admin_ok.status_code, 200)

    def test_process_weekly_payouts_management_command(self):
        # Place order to create pending commission
        self._create_and_pay_order(self.ds_with_bank, qty=2, sell_price=Decimal("50.00"))
        
        with override_settings(CHIP_SEND_SIMULATOR=True):
            call_command("process_weekly_payouts")

        self.assertTrue(PayoutBatch.objects.exists())
        batch = PayoutBatch.objects.first()
        self.assertEqual(batch.status, PayoutBatch.Status.COMPLETED)

from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from catalog.models import Product, Variant, ShippingRate, StockLog
from orders.models import Order
from orders.services import place_order, mark_paid, cancel_order, ship_order, complete_order, InsufficientStock, InvalidTransition


class OrdersTests(TestCase):
    def setUp(self):
        ShippingRate.objects.create(region="WM", fee=Decimal("8.00"))
        ShippingRate.objects.create(region="SABAH", fee=Decimal("12.00"))

        self.dropshipper = User.objects.create_user(
            username="ds_seller", password="password", role=User.Role.DROPSHIPPER, status=User.Status.APPROVED
        )
        self.hq_user = User.objects.create_user(
            username="hq_worker", password="password", role=User.Role.HQ, status=User.Status.APPROVED
        )

        self.product = Product.objects.create(
            name="Polo Tee", sku_prefix="PLO", dropship_price=Decimal("30.00"),
            suggested_retail_price=Decimal("60.00"), is_active=True
        )
        self.variant = Variant.objects.create(
            product=self.product, size="L", colour="Navy", sku="PLO-NVY-L", stock=5
        )

    def test_place_order_reserves_stock_and_calculates_totals(self):
        customer = {
            "customer_name": "John Doe", "customer_phone": "0123456789",
            "address": "Street 1", "postcode": "50000", "city": "KL", "state": "W.P. Kuala Lumpur"
        }
        items = [{"variant_id": self.variant.id, "qty": 2, "sell_price": Decimal("60.00")}]

        order = place_order(self.dropshipper, customer, items)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)  # 5 - 2 = 3
        self.assertEqual(order.subtotal_cost, Decimal("60.00"))  # 30 * 2
        self.assertEqual(order.shipping_fee, Decimal("8.00"))
        self.assertEqual(order.total_payable, Decimal("128.00"))  # Customer pays RM120 apparel + RM8 shipping
        self.assertEqual(order.total_sales, Decimal("120.00"))
        self.assertEqual(order.profit, Decimal("18.00"))  # 15% commission of RM120
        self.assertEqual(order.commission_amount, Decimal("18.00"))
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)

    def test_place_order_fails_when_stock_insufficient(self):
        customer = {
            "customer_name": "Overbuyer", "customer_phone": "0123456789",
            "address": "Street 1", "postcode": "50000", "city": "KL", "state": "Selangor"
        }
        items = [{"variant_id": self.variant.id, "qty": 10, "sell_price": Decimal("60.00")}]  # stock is only 5

        with self.assertRaises(InsufficientStock):
            place_order(self.dropshipper, customer, items)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)  # Stock untouched

    def test_order_cancellation_restores_stock(self):
        customer = {
            "customer_name": "Jane", "customer_phone": "0123456789",
            "address": "Street 2", "postcode": "50000", "city": "KL", "state": "Selangor"
        }
        items = [{"variant_id": self.variant.id, "qty": 3, "sell_price": Decimal("60.00")}]
        order = place_order(self.dropshipper, customer, items)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 2)

        cancel_order(order, self.dropshipper, "Customer changed mind")
        order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.variant.stock, 5)  # Restored back to 5
        self.assertFalse(order.stock_reserved)

    def test_order_fulfillment_flow(self):
        customer = {
            "customer_name": "Jane", "customer_phone": "0123456789",
            "address": "Street 2", "postcode": "50000", "city": "KL", "state": "Selangor"
        }
        order = place_order(self.dropshipper, customer, [{"variant_id": self.variant.id, "qty": 1, "sell_price": Decimal("60.00")}])

        # Pay
        mark_paid(order, order.total_cents)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        # Ship
        ship_order(order, self.hq_user, "J&T Express", "JNT123456MY")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)
        self.assertEqual(order.tracking_no, "JNT123456MY")

        # Complete
        complete_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

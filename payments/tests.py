import base64
import json
from decimal import Decimal
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Product, Variant, ShippingRate
from orders.models import Order
from orders.services import place_order
from payments.gateways.chip import ChipGateway
from payments.gateways import InvalidSignature
from payments.models import Payment
from payments.services import start_payment


class PaymentsTests(TestCase):
    def setUp(self):
        ShippingRate.objects.create(region="WM", fee=Decimal("8.00"))
        self.dropshipper = User.objects.create_user(
            username="buyer_ds", password="password", role=User.Role.DROPSHIPPER, status=User.Status.APPROVED
        )
        self.product = Product.objects.create(
            name="Shirt", sku_prefix="SHRT", dropship_price=Decimal("40.00"),
            suggested_retail_price=Decimal("70.00"), is_active=True
        )
        self.variant = Variant.objects.create(
            product=self.product, size="M", colour="Black", sku="SHRT-BLK-M", stock=10
        )
        self.order = place_order(
            self.dropshipper,
            {
                "customer_name": "Test Cust", "customer_phone": "0123456789",
                "address": "Street", "postcode": "50000", "city": "KL", "state": "Selangor"
            },
            [{"variant_id": self.variant.id, "qty": 1, "sell_price": Decimal("70.00")}]
        )

    def test_start_dummy_payment_and_simulate_success(self):
        self.client.force_login(self.dropshipper)
        payment = start_payment(self.order)
        self.assertEqual(payment.gateway, "dummy")
        self.assertEqual(payment.status, Payment.Status.PENDING)

        # Post success on simulator
        resp = self.client.post(
            reverse("payments:dummy_checkout", kwargs={"purchase_id": payment.purchase_id}),
            {"action": "success"}
        )
        self.assertEqual(resp.status_code, 302)  # Redirects to return

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_simulate_fpx_cancel_restores_inventory(self):
        self.client.force_login(self.dropshipper)
        payment = start_payment(self.order)
        
        # Stock should be 9
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 9)

        # Post cancel
        self.client.post(
            reverse("payments:dummy_checkout", kwargs={"purchase_id": payment.purchase_id}),
            {"action": "cancel"}
        )

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.CANCELLED)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.variant.stock, 10)  # Restored!

    def test_chip_rsa_signature_verification(self):
        # Generate temporary RSA key pair
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        pub_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()

        payload = {
            "id": "chip-purchase-123",
            "brand_id": "test-brand-id",
            "status": "paid",
            "purchase": {"total": 4800}
        }
        body_bytes = json.dumps(payload).encode()
        
        # Sign payload using private key
        signature = private_key.sign(body_bytes, padding.PKCS1v15(), hashes.SHA256())
        sig_b64 = base64.b64encode(signature).decode()

        with patch.object(ChipGateway, "public_key_pem", return_value=pub_pem):
            with self.settings(CHIP_SECRET_KEY="test_sec", CHIP_BRAND_ID="test-brand-id"):
                gw = ChipGateway()
                verified_data = gw.verify_callback(body_bytes, sig_b64)
                self.assertEqual(verified_data["id"], "chip-purchase-123")
                self.assertEqual(verified_data["status"], "paid")

                # Corrupt signature should raise InvalidSignature
                with self.assertRaises(InvalidSignature):
                    gw.verify_callback(body_bytes, "invalid_signature_base64")

"""Fake FPX gateway for local development and tests.

It mimics CHIP's purchase JSON shape ({"id", "status", "purchase": {"total"}})
so the rest of the system runs exactly the same code path.
"""
import uuid

from django.urls import reverse

from . import GatewayError, InvalidSignature


class DummyGateway:
    name = "dummy"

    def create_purchase(self, order):
        pid = f"dummy-{uuid.uuid4().hex[:16]}"
        raw = {"id": pid, "status": "created", "reference": order.order_no,
               "purchase": {"total": order.total_cents, "currency": "MYR"}}
        url = "http://localhost" + reverse("payments:dummy_checkout", args=[pid])
        return {"purchase_id": pid, "checkout_url": url, "raw": raw}

    def get_purchase(self, purchase_id):
        from payments.models import Payment

        p = Payment.objects.filter(purchase_id=purchase_id).first()
        if not p:
            raise GatewayError("Unknown dummy purchase")
        return p.raw_payload or {"id": purchase_id, "status": "created",
                                 "purchase": {"total": p.amount_cents}}

    def verify_callback(self, raw_body, signature_b64):
        raise InvalidSignature("Dummy gateway does not accept callbacks")

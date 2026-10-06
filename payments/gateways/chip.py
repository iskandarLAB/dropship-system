"""CHIP Collect gateway (https://docs.chip-in.asia).

- Create purchase:  POST {base}/purchases/        (Authorization: Bearer <secret>)
- Get purchase:     GET  {base}/purchases/{id}/
- Public key:       GET  {base}/public_key/        -> JSON-encoded PEM string
- success_callback: POST with Purchase JSON; header X-Signature = base64 RSA PKCS#1 v1.5
                    signature of SHA256(raw body), verified with the company public key.
"""
import base64
import json
import logging

import requests
from cryptography.exceptions import InvalidSignature as CryptoInvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from . import GatewayError, InvalidSignature

log = logging.getLogger("payments")

PUBLIC_KEY_CACHE = "chip-public-key"


def _cents(amount):
    return int(round(amount * 100))


class ChipGateway:
    name = "chip"

    def __init__(self):
        if not settings.CHIP_SECRET_KEY or not settings.CHIP_BRAND_ID:
            raise GatewayError("CHIP_SECRET_KEY and CHIP_BRAND_ID must be set in .env")
        self.base = settings.CHIP_API_BASE.rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings.CHIP_SECRET_KEY}"}

    # --- API calls -------------------------------------------------------
    def _request(self, method, path, **kwargs):
        try:
            r = requests.request(method, f"{self.base}{path}", headers=self.headers, timeout=20, **kwargs)
        except requests.RequestException as e:
            raise GatewayError(f"Could not reach CHIP: {e}") from e
        if r.status_code >= 400:
            log.error("CHIP %s %s -> %s %s", method, path, r.status_code, r.text[:500])
            raise GatewayError(f"CHIP error {r.status_code}: {r.text[:300]}")
        return r.json()

    def create_purchase(self, order):
        user = order.dropshipper
        return_url = settings.SITE_URL + reverse("payments:return") + f"?order={order.pk}"
        products = [
            {
                "name": f"{i.variant.sku} {i.variant}"[:256],
                "price": _cents(i.unit_cost),
                "quantity": str(i.quantity),
            }
            for i in order.items.select_related("variant__product")
        ]
        if order.shipping_fee:
            products.append({"name": f"Shipping ({order.state})", "price": _cents(order.shipping_fee), "quantity": "1"})

        client = {"email": user.email, "full_name": (user.get_full_name() or user.username)[:128]}
        if user.phone:
            client["phone"] = user.phone

        body = {
            "brand_id": settings.CHIP_BRAND_ID,
            "reference": order.order_no,
            "client": client,
            "purchase": {
                "currency": "MYR",
                "products": products,
                "due_strict": True,  # CHIP refuses payment after `due`
                "notes": f"Dropship order {order.order_no}",
            },
            "due": int(order.expires_at.timestamp()),
            "payment_method_whitelist": ["fpx"],
            "success_redirect": return_url,
            "failure_redirect": return_url,
            "cancel_redirect": return_url,
            "send_receipt": False,
        }
        # CHIP rejects explicit ports in success_callback; skip it for localhost dev.
        callback = settings.SITE_URL + reverse("payments:chip_callback")
        if callback.startswith("https://") or ":" not in callback.split("//", 1)[1].split("/", 1)[0]:
            body["success_callback"] = callback

        data = self._request("POST", "/purchases/", json=body)
        total = data.get("purchase", {}).get("total")
        if total is not None and int(total) != order.total_cents:
            raise GatewayError(f"CHIP total {total} != order total {order.total_cents}")
        return {"purchase_id": data["id"], "checkout_url": data["checkout_url"], "raw": data}

    def get_purchase(self, purchase_id):
        return self._request("GET", f"/purchases/{purchase_id}/")

    # --- Callback verification ------------------------------------------
    def public_key_pem(self):
        if settings.CHIP_PUBLIC_KEY:
            return settings.CHIP_PUBLIC_KEY
        pem = cache.get(PUBLIC_KEY_CACHE)
        if not pem:
            pem = self._request("GET", "/public_key/")  # JSON-decoded -> PEM string
            if not isinstance(pem, str):
                raise GatewayError("Unexpected /public_key/ response")
            cache.set(PUBLIC_KEY_CACHE, pem, 60 * 60 * 24)
        return pem

    def verify_callback(self, raw_body, signature_b64):
        if not signature_b64:
            raise InvalidSignature("Missing X-Signature header")
        try:
            pub = load_pem_public_key(self.public_key_pem().encode())
            pub.verify(base64.b64decode(signature_b64), raw_body, padding.PKCS1v15(), hashes.SHA256())
        except (CryptoInvalidSignature, ValueError, TypeError) as e:
            raise InvalidSignature(str(e) or "Signature mismatch") from e
        data = json.loads(raw_body)
        if data.get("brand_id") and data["brand_id"] != settings.CHIP_BRAND_ID:
            raise InvalidSignature("Brand ID mismatch")
        return data

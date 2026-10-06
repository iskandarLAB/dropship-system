"""Glue between the gateway and order services."""
import logging

from django.db import transaction

from orders import services as order_services
from orders.models import Order

from .gateways import get_gateway
from .models import Payment

log = logging.getLogger("payments")

PAID_STATUSES = {"paid"}
# Terminal "no money coming" statuses -> cancel the order (restore stock).
DEAD_STATUSES = {"cancelled", "expired", "blocked", "released"}
# A failed attempt; the payer may retry on the same checkout page before expiry.
FAILED_STATUSES = {"error"}


def start_payment(order):
    """Return a PENDING Payment with a checkout URL (reusing the open one if any)."""
    if not order.is_payable:
        raise order_services.InvalidTransition("This order is not awaiting payment.")
    existing = order.payments.filter(status=Payment.Status.PENDING, amount_cents=order.total_cents).first()
    if existing and existing.gateway == get_gateway().name:
        return existing
    gw = get_gateway()
    res = gw.create_purchase(order)
    return Payment.objects.create(
        order=order, gateway=gw.name, purchase_id=res["purchase_id"], checkout_url=res["checkout_url"],
        amount_cents=order.total_cents, gateway_status=res["raw"].get("status", ""), raw_payload=res["raw"],
    )


def _extract_total(data):
    total = (data.get("purchase") or {}).get("total")
    if total is None:
        total = (data.get("payment") or {}).get("amount")
    return int(total) if total is not None else None


def apply_purchase_data(payment, data):
    """Apply a verified purchase object (from callback or API) to Payment + Order."""
    status = (data.get("status") or "").lower()
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        payment.gateway_status = status
        payment.raw_payload = data
        if status in PAID_STATUSES:
            total = _extract_total(data)
            if total is None:
                total = payment.amount_cents
            try:
                order_services.mark_paid(payment.order, total)
            except order_services.AmountMismatch:
                payment.status = Payment.Status.FAILED
                payment.save()
                raise
            payment.status = Payment.Status.PAID
        elif status in DEAD_STATUSES:
            payment.status = Payment.Status.CANCELLED
        elif status in FAILED_STATUSES:
            payment.status = Payment.Status.FAILED
        payment.save()

    if status in DEAD_STATUSES:
        order = Order.objects.get(pk=payment.order_id)
        if order.status == Order.Status.AWAITING_PAYMENT:
            order_services.cancel_order(order, None, f"Payment {status}")
    return Order.objects.get(pk=payment.order_id)


def refresh_order_payment(order):
    """Ask the gateway for the latest status of the order's open payment."""
    payment = order.payments.exclude(status=Payment.Status.PAID).first()
    if not payment:
        return Order.objects.get(pk=order.pk)
    data = get_gateway(payment.gateway).get_purchase(payment.purchase_id)
    if str(data.get("id", payment.purchase_id)) != payment.purchase_id:
        log.error("Purchase id mismatch for %s", payment)
        return order
    return apply_purchase_data(payment, data)

"""Order business logic. All stock movements go through here."""
import logging
from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from catalog.models import ShippingRate, StockLog, Variant

from .models import Order, OrderItem

log = logging.getLogger("payments")


class OrderError(Exception):
    pass


class InsufficientStock(OrderError):
    def __init__(self, variant, available, requested):
        self.variant, self.available, self.requested = variant, available, requested
        super().__init__(f"Not enough stock for {variant}: requested {requested}, available {available}.")


class AmountMismatch(OrderError):
    pass


class InvalidTransition(OrderError):
    pass


def _normalise_items(items):
    """Merge duplicate variants and validate quantities/prices."""
    merged = OrderedDict()
    for it in items:
        vid, qty = int(it["variant_id"]), int(it["qty"])
        price = Decimal(str(it["sell_price"]))
        if qty <= 0:
            raise OrderError("Quantity must be at least 1.")
        if price < 0:
            raise OrderError("Selling price cannot be negative.")
        if vid in merged:
            merged[vid]["qty"] += qty
        else:
            merged[vid] = {"qty": qty, "sell_price": price}
    if not merged:
        raise OrderError("Add at least one item.")
    return merged


@transaction.atomic
def place_order(dropshipper, customer, items):
    """Create an order and reserve stock. Raises InsufficientStock / OrderError."""
    merged = _normalise_items(items)
    variants = {
        v.id: v
        for v in Variant.objects.select_for_update()
        .select_related("product")
        .filter(id__in=merged.keys(), product__is_active=True)
    }
    for vid, it in merged.items():
        v = variants.get(vid)
        if v is None:
            raise OrderError("One of the selected products is no longer available.")
        if it["qty"] > v.stock:
            raise InsufficientStock(v, v.stock, it["qty"])

    order = Order.objects.create(
        dropshipper=dropshipper,
        status=Order.Status.AWAITING_PAYMENT,
        expires_at=timezone.now() + timedelta(minutes=settings.ORDER_PAYMENT_TIMEOUT_MINUTES),
        shipping_fee=ShippingRate.fee_for_state(customer["state"]),
        stock_reserved=True,
        **customer,
    )
    subtotal = sales = Decimal("0")
    for vid, it in merged.items():
        v = variants[vid]
        item = OrderItem.objects.create(
            order=order, variant=v, quantity=it["qty"],
            unit_cost=v.product.dropship_price, unit_sell_price=it["sell_price"],
        )
        subtotal += item.line_cost
        sales += item.line_sales
        StockLog.objects.create(variant=v, user=dropshipper, old_qty=v.stock, new_qty=v.stock - it["qty"],
                                reason=StockLog.Reason.ORDER, note=order.order_no)
        v.stock -= it["qty"]
        v.save(update_fields=["stock"])

    order.subtotal_cost = subtotal
    order.total_sales = sales
    # In affiliate marketing dropship, customer pays Retail Sales + Shipping Fee to HQ
    order.total_payable = sales + order.shipping_fee
    order.save(update_fields=["subtotal_cost", "total_sales", "total_payable"])
    return order


def _restore_stock(order, user, note):
    if not order.stock_reserved:
        return
    for item in order.items.select_related("variant"):
        v = Variant.objects.select_for_update().get(pk=item.variant_id)
        StockLog.objects.create(variant=v, user=user, old_qty=v.stock, new_qty=v.stock + item.quantity,
                                reason=StockLog.Reason.RESTORE, note=f"{order.order_no}: {note}"[:200])
        v.stock += item.quantity
        v.save(update_fields=["stock"])
    order.stock_reserved = False


def _try_reserve_stock(order, user):
    """Re-reserve stock for an order that was cancelled. Returns True on success."""
    items = list(order.items.all())
    variants = {v.id: v for v in Variant.objects.select_for_update().filter(id__in=[i.variant_id for i in items])}
    if any(variants[i.variant_id].stock < i.quantity for i in items):
        return False
    for i in items:
        v = variants[i.variant_id]
        StockLog.objects.create(variant=v, user=user, old_qty=v.stock, new_qty=v.stock - i.quantity,
                                reason=StockLog.Reason.ORDER, note=f"{order.order_no} (late payment)")
        v.stock -= i.quantity
        v.save(update_fields=["stock"])
    order.stock_reserved = True
    return True


@transaction.atomic
def mark_paid(order, amount_cents):
    """Auto-approve an order after a verified payment. Idempotent."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status in (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.COMPLETED, Order.Status.NEEDS_REFUND):
        return order
    if int(amount_cents) != order.total_cents:
        log.error("Amount mismatch for %s: paid %s, expected %s", order, amount_cents, order.total_cents)
        raise AmountMismatch(f"Paid {amount_cents} cents, expected {order.total_cents}.")

    now = timezone.now()
    if order.status == Order.Status.CANCELLED:
        # Payment arrived after the order expired/was cancelled.
        if _try_reserve_stock(order, order.dropshipper):
            order.status = Order.Status.PAID
            order.cancel_reason = ""
        else:
            order.status = Order.Status.NEEDS_REFUND
    else:
        order.status = Order.Status.PAID
    order.paid_at = now
    order.save()
    if order.status == Order.Status.PAID:
        try:
            from payouts.services import credit_commission_for_order
            credit_commission_for_order(order)
        except Exception:
            log.exception("Could not credit commission for order %s", order)
    log.info("Order %s marked %s", order, order.status)
    return order


@transaction.atomic
def cancel_order(order, user=None, reason=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in (Order.Status.AWAITING_PAYMENT, Order.Status.PAID, Order.Status.NEEDS_REFUND):
        raise InvalidTransition(f"Cannot cancel an order that is {order.get_status_display()}.")
    _restore_stock(order, user, reason or "cancelled")
    order.status = Order.Status.CANCELLED
    order.cancel_reason = reason
    order.save()
    try:
        from payouts.services import cancel_commission_for_order
        cancel_commission_for_order(order)
    except Exception:
        log.exception("Could not cancel commission for order %s", order)
    return order


@transaction.atomic
def ship_order(order, user, courier, tracking_no):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in (Order.Status.PAID, Order.Status.SHIPPED):
        raise InvalidTransition("Only paid orders can be shipped.")
    if not courier.strip() or not tracking_no.strip():
        raise OrderError("Courier and tracking number are required.")
    order.courier = courier.strip()
    order.tracking_no = tracking_no.strip()
    if order.status == Order.Status.PAID:
        order.status = Order.Status.SHIPPED
        order.shipped_at = timezone.now()
        order.shipped_by = user
    order.save()
    return order


@transaction.atomic
def complete_order(order):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.SHIPPED:
        raise InvalidTransition("Only shipped orders can be completed.")
    order.status = Order.Status.COMPLETED
    order.completed_at = timezone.now()
    order.save()
    return order


def expire_unpaid_orders(check_gateway=True):
    """Cancel AWAITING_PAYMENT orders past their expiry (restoring stock).

    Before cancelling, ask the gateway whether the order was actually paid
    so we never cancel a paid order because a callback was missed.
    """
    from payments.services import refresh_order_payment

    expired = Order.objects.filter(status=Order.Status.AWAITING_PAYMENT, expires_at__lt=timezone.now())
    count = 0
    for order in expired:
        if check_gateway:
            try:
                order = refresh_order_payment(order)
            except Exception:  # network issues shouldn't block expiry forever
                log.exception("Could not refresh payment for %s", order)
            if order.status != Order.Status.AWAITING_PAYMENT:
                continue
        try:
            cancel_order(order, None, "Payment not completed in time")
            count += 1
        except InvalidTransition:
            pass
    return count


def auto_complete_shipped():
    cutoff = timezone.now() - timedelta(days=settings.ORDER_AUTO_COMPLETE_DAYS)
    return Order.objects.filter(status=Order.Status.SHIPPED, shipped_at__lt=cutoff).update(
        status=Order.Status.COMPLETED, completed_at=timezone.now()
    )


def run_housekeeping(throttle_seconds=60):
    """Lazy housekeeping called from page views (so cron is optional)."""
    if cache.add("orders-housekeeping-lock", 1, throttle_seconds):
        expire_unpaid_orders()
        auto_complete_shipped()

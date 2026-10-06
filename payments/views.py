import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from orders import services as order_services
from orders.models import Order

from . import services
from .gateways import GatewayError, InvalidSignature, get_gateway
from .models import Payment

log = logging.getLogger("payments")


def _own_order(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.dropshipper_id != request.user.id:
        raise PermissionDenied
    return order


@role_required("DROPSHIPPER")
def start(request, order_id):
    order = _own_order(request, order_id)
    if not order.is_payable:
        messages.info(request, "This order is no longer awaiting payment.")
        return redirect("orders:detail", pk=order.pk)
    try:
        payment = services.start_payment(order)
    except (GatewayError, order_services.OrderError) as e:
        log.exception("start_payment failed for %s", order)
        messages.error(request, f"Could not start FPX payment: {e}")
        return redirect("orders:detail", pk=order.pk)
    if payment.gateway == "dummy":
        return redirect("payments:dummy_checkout", purchase_id=payment.purchase_id)
    return redirect(payment.checkout_url)


@role_required("DROPSHIPPER")
def payment_return(request):
    """User lands here after the FPX page. Never trust URL params: ask the gateway."""
    try:
        order = _own_order(request, int(request.GET.get("order", 0)))
    except ValueError:
        raise Http404
    if order.is_payable:
        try:
            order = services.refresh_order_payment(order)
        except GatewayError as e:
            messages.warning(request, f"Could not confirm payment status yet ({e}). Refresh in a moment.")
        except order_services.AmountMismatch:
            messages.error(request, "Payment amount mismatch. Please contact admin.")
    return render(request, "payments/result.html", {"order": order})


@csrf_exempt
@require_POST
def chip_callback(request):
    """CHIP success_callback. Verified with RSA signature over the raw body."""
    try:
        gw = get_gateway("chip")
        data = gw.verify_callback(request.body, request.headers.get("X-Signature", ""))
    except InvalidSignature as e:
        log.warning("Rejected CHIP callback: %s", e)
        return HttpResponse("invalid signature", status=401)
    except GatewayError as e:
        log.error("CHIP callback config error: %s", e)
        return HttpResponse("gateway not configured", status=503)

    payment = Payment.objects.filter(purchase_id=str(data.get("id", ""))).first()
    if not payment:
        log.warning("CHIP callback for unknown purchase %s", data.get("id"))
        return HttpResponse("ok")  # ack so CHIP doesn't retry forever
    try:
        services.apply_purchase_data(payment, data)
    except order_services.AmountMismatch:
        return HttpResponse("amount mismatch", status=400)
    return HttpResponse("ok")


# ---------------- Dummy gateway (development only) ----------------

def _dummy_payment(request, purchase_id):
    if settings.PAYMENT_GATEWAY != "dummy" and not settings.DEBUG:
        raise Http404
    payment = get_object_or_404(Payment, purchase_id=purchase_id, gateway="dummy")
    if payment.order.dropshipper_id != request.user.id:
        raise PermissionDenied
    return payment


@role_required("DROPSHIPPER")
def dummy_checkout(request, purchase_id):
    payment = _dummy_payment(request, purchase_id)
    if request.method == "POST":
        action = request.POST.get("action")
        status = {"success": "paid", "fail": "error", "cancel": "cancelled"}.get(action)
        if not status:
            raise Http404
        data = dict(payment.raw_payload or {})
        data.update({"id": payment.purchase_id, "status": status,
                     "purchase": {"total": payment.amount_cents, "currency": "MYR"}})
        # Simulate CHIP: callback updates state, then the browser is redirected back.
        payment.raw_payload = data
        payment.save(update_fields=["raw_payload"])
        services.apply_purchase_data(payment, data)
        return redirect(reverse("payments:return") + f"?order={payment.order_id}")
    return render(request, "payments/dummy_checkout.html", {"payment": payment, "order": payment.order})

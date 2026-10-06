import csv

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from catalog.models import Product, ShippingRate

from . import services
from .forms import CustomerForm, parse_items
from .models import Order


def _product_catalog_json():
    """Data for the order form JS: products -> variants with live stock."""
    data = []
    for p in Product.objects.filter(is_active=True).prefetch_related("variants"):
        data.append({
            "id": p.id,
            "name": p.name,
            "cost": str(p.dropship_price),
            "srp": str(p.suggested_retail_price),
            "variants": [
                {"id": v.id, "label": f"{v.colour} / {v.size}", "stock": v.stock, "sku": v.sku}
                for v in p.variants.all()
            ],
        })
    return data


@role_required("DROPSHIPPER", "ADMIN", "HQ")
def order_new(request):
    services.run_housekeeping()
    form = CustomerForm(request.POST or None)
    item_errors = []
    if request.method == "POST":
        items, item_errors = parse_items(request.POST)
        if form.is_valid() and not item_errors:
            try:
                order = services.place_order(request.user, form.cleaned_data, items)
            except services.OrderError as e:
                item_errors.append(str(e))
            else:
                return redirect("payments:start", order_id=order.pk)
    return render(request, "orders/order_new.html", {
        "form": form,
        "item_errors": item_errors,
        "catalog": _product_catalog_json(),
        "shipping_map": ShippingRate.as_state_map(),
    })


@role_required("DROPSHIPPER", "ADMIN", "HQ")
def order_list(request):
    services.run_housekeeping()
    if request.user.is_management:
        orders = Order.objects.all().prefetch_related("items__variant__product")
    else:
        orders = request.user.orders.prefetch_related("items__variant__product")
    status = request.GET.get("status")
    if status:
        orders = orders.filter(status=status)
    return render(request, "orders/order_list.html",
                  {"orders": orders, "status": status, "statuses": Order.Status.choices})


@role_required("DROPSHIPPER", "HQ", "ADMIN")
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("dropshipper"), pk=pk)
    if request.user.is_dropshipper and order.dropshipper_id != request.user.id:
        raise PermissionDenied
    return render(request, "orders/order_detail.html",
                  {"order": order, "items": order.items.select_related("variant__product"),
                   "payments": order.payments.all()})


@require_POST
@role_required("DROPSHIPPER", "ADMIN")
def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.user.is_dropshipper:
        if order.dropshipper_id != request.user.id or order.status != Order.Status.AWAITING_PAYMENT:
            raise PermissionDenied
    try:
        services.cancel_order(order, request.user, request.POST.get("reason", "Cancelled by user"))
        messages.success(request, f"Order {order.order_no} cancelled and stock restored.")
    except services.OrderError as e:
        messages.error(request, str(e))
    return redirect("orders:detail", pk=pk)


# ---------------- HQ ----------------

@role_required("HQ", "ADMIN")
def hq_orders(request):
    services.run_housekeeping()
    status = request.GET.get("status", Order.Status.PAID)
    orders = Order.objects.select_related("dropshipper").prefetch_related("items__variant__product")
    if status != "ALL":
        orders = orders.filter(status=status)
    if status == Order.Status.PAID:
        orders = orders.order_by("paid_at")  # oldest first = ship first
    q = request.GET.get("q", "").strip()
    if q:
        orders = orders.filter(order_no__icontains=q) | orders.filter(customer_name__icontains=q)
    return render(request, "orders/hq_orders.html",
                  {"orders": orders, "status": status, "statuses": Order.Status.choices, "q": q})


@require_POST
@role_required("HQ", "ADMIN")
def hq_ship(request, pk):
    order = get_object_or_404(Order, pk=pk)
    try:
        services.ship_order(order, request.user, request.POST.get("courier", ""), request.POST.get("tracking_no", ""))
        messages.success(request, f"{order.order_no} marked as shipped.")
    except services.OrderError as e:
        messages.error(request, f"{order.order_no}: {e}")
    return redirect(request.POST.get("next") or "orders:hq_orders")


@require_POST
@role_required("HQ", "ADMIN")
def hq_complete(request, pk):
    order = get_object_or_404(Order, pk=pk)
    try:
        services.complete_order(order)
        messages.success(request, f"{order.order_no} marked as completed.")
    except services.OrderError as e:
        messages.error(request, str(e))
    if request.POST.get("next"):
        return redirect(request.POST["next"])
    return redirect("orders:detail", pk=pk)


@role_required("HQ", "ADMIN")
def packing_slip(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, "orders/packing_slip.html",
                  {"order": order, "items": order.items.select_related("variant__product")})


@role_required("ADMIN")
def export_csv(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="orders.csv"'
    w = csv.writer(resp)
    w.writerow(["Order No", "Date", "Dropshipper", "Status", "Customer", "Phone", "State",
                "Items", "Cost (RM)", "Shipping (RM)", "Paid (RM)", "Sales (RM)", "Courier", "Tracking"])
    for o in Order.objects.select_related("dropshipper").prefetch_related("items__variant__product"):
        w.writerow([o.order_no, o.created_at.strftime("%Y-%m-%d %H:%M"), o.dropshipper, o.get_status_display(),
                    o.customer_name, o.customer_phone, o.state,
                    "; ".join(f"{i.variant.sku} x{i.quantity}" for i in o.items.all()),
                    o.subtotal_cost, o.shipping_fee, o.total_payable, o.total_sales, o.courier, o.tracking_no])
    return resp

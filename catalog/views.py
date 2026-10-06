from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.decorators import role_required

from .models import Product, Variant
from .services import hq_bulk_update


@role_required("HQ", "ADMIN")
def hq_stock(request):
    variants = Variant.objects.select_related("product").filter(product__is_active=True)
    product_id = request.GET.get("product")
    if product_id:
        variants = variants.filter(product_id=product_id)

    if request.method == "POST":
        updates, errors = {}, []
        for key, value in request.POST.items():
            if not key.startswith("qty_"):
                continue
            try:
                vid = int(key[4:])
                qty = int(value)
                if qty < 0:
                    raise ValueError
            except ValueError:
                errors.append(key)
                continue
            updates[vid] = qty
        if errors:
            messages.error(request, "Some quantities were invalid (must be whole numbers ≥ 0). Nothing saved.")
        else:
            changed = hq_bulk_update(request.user, updates)
            messages.success(
                request, f"Stock confirmed for {len(updates)} variant(s); {changed} quantity change(s) saved."
            )
            return redirect(request.get_full_path())

    return render(
        request,
        "catalog/hq_stock.html",
        {"variants": variants, "products": Product.objects.filter(is_active=True), "product_id": product_id},
    )


@role_required("DROPSHIPPER", "HQ", "ADMIN")
def stock_list(request):
    products = Product.objects.filter(is_active=True).prefetch_related("variants")
    return render(request, "catalog/stock_list.html", {"products": products})


def affiliate_store(request, username):
    """Public storefront for an approved dropshipper marketer."""
    from accounts.models import User
    from django.shortcuts import get_object_or_404
    dropshipper = get_object_or_404(User, username=username, role=User.Role.DROPSHIPPER, status=User.Status.APPROVED)
    products = Product.objects.filter(is_active=True).prefetch_related("variants")
    return render(request, "catalog/affiliate_store.html", {
        "dropshipper": dropshipper,
        "products": products,
    })


def affiliate_order(request, username):
    """Customer checkout page for an affiliate's referral store."""
    from accounts.models import User
    from django.shortcuts import get_object_or_404, redirect
    from orders.forms import CustomerForm, parse_items
    from orders.services import place_order, run_housekeeping, OrderError
    from catalog.models import ShippingRate

    run_housekeeping()
    dropshipper = get_object_or_404(User, username=username, role=User.Role.DROPSHIPPER, status=User.Status.APPROVED)
    
    preselect_variant_id = request.GET.get("variant")

    form = CustomerForm(request.POST or None)
    item_errors = []
    
    if request.method == "POST":
        items, item_errors = parse_items(request.POST)
        
        variant_ids = [it["variant_id"] for it in items]
        variant_map = {v.id: v for v in Variant.objects.filter(id__in=variant_ids).select_related("product")}
        
        for it in items:
            v = variant_map.get(it["variant_id"])
            if v:
                it["sell_price"] = v.product.suggested_retail_price
            else:
                item_errors.append("Invalid product variant selected.")

        if form.is_valid() and not item_errors:
            try:
                order = place_order(dropshipper, form.cleaned_data, items)
            except OrderError as e:
                item_errors.append(str(e))
            else:
                return redirect("payments:start", order_id=order.pk)

    catalog_data = []
    for p in Product.objects.filter(is_active=True).prefetch_related("variants"):
        avail_variants = [
            {"id": v.id, "label": f"{v.colour} - Saiz {v.size} (Baki Stok: {v.stock})", "stock": v.stock, "sku": v.sku}
            for v in p.variants.all() if v.stock > 0
        ]
        if avail_variants:
            catalog_data.append({
                "id": p.id,
                "name": p.name,
                "cost": str(p.dropship_price),
                "srp": str(p.suggested_retail_price),
                "variants": avail_variants,
            })

    return render(request, "catalog/affiliate_checkout.html", {
        "dropshipper": dropshipper,
        "form": form,
        "item_errors": item_errors,
        "catalog": catalog_data,
        "shipping_map": ShippingRate.as_state_map(),
        "preselect_variant_id": preselect_variant_id,
    })

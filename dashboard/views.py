from datetime import timedelta
import json
from decimal import Decimal

from django.db.models import Count, Sum, F, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render, redirect
from django.utils import timezone

from accounts.decorators import role_required
from accounts.models import User
from catalog.models import Product, Variant
from catalog.services import freshness_summary
from orders.models import Order
from orders.services import run_housekeeping


def dropshipper_dashboard(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.is_admin_role:
        return redirect("dashboard:admin_panel")
    if request.user.is_hq:
        return redirect("dashboard:hq_home")
    if not request.user.is_dropshipper or not request.user.is_approved:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    run_housekeeping()
    user = request.user
    orders = user.orders.filter(status__in=Order.SALE_STATUSES)

    period = request.GET.get("period", "30d")
    now = timezone.now()

    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "all":
        start_date = None
    else:  # default 30d
        period = "30d"
        start_date = now - timedelta(days=30)

    period_orders = orders
    if start_date:
        period_orders = period_orders.filter(paid_at__gte=start_date)

    agg = period_orders.aggregate(
        total_sales=Sum("total_sales"),
        total_cost=Sum("subtotal_cost"),
        total_orders=Count("id")
    )
    total_sales = agg["total_sales"] or Decimal("0.00")
    total_cost = agg["total_cost"] or Decimal("0.00")
    total_profit = total_sales - total_cost
    total_orders = agg["total_orders"] or 0

    pending_payment_count = user.orders.filter(status=Order.Status.AWAITING_PAYMENT).count()
    awaiting_shipment_count = user.orders.filter(status=Order.Status.PAID).count()

    # Chart: Daily sales for the last 30 days
    thirty_days_ago = now - timedelta(days=30)
    daily_sales = (
        orders.filter(paid_at__gte=thirty_days_ago)
        .annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(sales=Sum("total_sales"))
        .order_by("day")
    )
    sales_map = {entry["day"].strftime("%d %b"): float(entry["sales"]) for entry in daily_sales if entry["day"]}
    
    chart_labels = []
    chart_data = []
    for i in range(29, -1, -1):
        day_date = (now - timedelta(days=i)).date()
        label = day_date.strftime("%d %b")
        chart_labels.append(label)
        chart_data.append(sales_map.get(label, 0.0))

    from payouts.services import get_dropshipper_commission_stats
    from django.urls import reverse
    commission_stats = get_dropshipper_commission_stats(user)
    store_url = request.build_absolute_uri(reverse("catalog:affiliate_store", args=[user.username]))
    products = Product.objects.filter(is_active=True).prefetch_related("variants")
    stock_freshness = freshness_summary()

    # --- Dropshipper Sales Leaderboard (Papan Pendahulu) ---
    ranking_time = request.GET.get("ranking_time", "month")
    order_filter = Q(orders__status__in=Order.SALE_STATUSES)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if ranking_time == "month":
        order_filter &= Q(orders__paid_at__gte=month_start)

    ranked_users = (
        User.objects.filter(role=User.Role.DROPSHIPPER, status=User.Status.APPROVED)
        .annotate(
            total_revenue=Sum("orders__total_sales", filter=order_filter),
            orders_count=Count("orders", filter=order_filter),
        )
        .order_by(F("total_revenue").desc(nulls_last=True), "-orders_count")
    )

    leaderboard = []
    user_rank = None
    user_rank_sales = Decimal("0.00")
    gap_to_next_rank = None
    rank_ahead_name = None

    for idx, ds in enumerate(ranked_users, start=1):
        rev = ds.total_revenue or Decimal("0.00")
        cnt = ds.orders_count or 0
        is_me = (ds.id == user.id)
        if is_me:
            user_rank = idx
            user_rank_sales = rev

        comm_est = (rev * Decimal("0.15")).quantize(Decimal("0.01"))
        entry = {
            "rank": idx,
            "dropshipper": ds,
            "name": ds.shop_name or ds.get_full_name() or ds.username,
            "total_sales": rev,
            "orders_count": cnt,
            "commission_est": comm_est,
            "is_current_user": is_me,
        }
        if idx <= 10:
            leaderboard.append(entry)

    if user_rank and user_rank > 1:
        for item in leaderboard:
            if item["rank"] == user_rank - 1:
                gap_to_next_rank = item["total_sales"] - user_rank_sales
                rank_ahead_name = item["name"]
                break

    return render(request, "dashboard/dropshipper.html", {
        "period": period,
        "total_sales": total_sales,
        "total_orders": total_orders,
        "total_profit": commission_stats["total_earned"],
        "commission_stats": commission_stats,
        "store_url": store_url,
        "pending_payment_count": pending_payment_count,
        "awaiting_shipment_count": awaiting_shipment_count,
        "chart_labels_json": json.dumps(chart_labels),
        "chart_data_json": json.dumps(chart_data),
        "products": products,
        "stock_freshness": stock_freshness,
        "leaderboard": leaderboard,
        "user_rank": user_rank,
        "user_rank_sales": user_rank_sales,
        "gap_to_next_rank": gap_to_next_rank,
        "rank_ahead_name": rank_ahead_name,
        "ranking_time": ranking_time,
    })


@role_required("HQ", "ADMIN")
def hq_home(request):
    run_housekeeping()
    freshness = freshness_summary()
    to_ship_count = Order.objects.filter(status=Order.Status.PAID).count()
    shipped_recent = Order.objects.filter(status=Order.Status.SHIPPED).order_by("-shipped_at")[:10]
    out_of_stock = Variant.objects.filter(product__is_active=True, stock=0).select_related("product")
    low_stock = Variant.objects.filter(product__is_active=True, stock__gt=0, stock__lte=10).select_related("product")

    return render(request, "dashboard/hq_home.html", {
        "freshness": freshness,
        "to_ship_count": to_ship_count,
        "shipped_recent": shipped_recent,
        "out_of_stock": out_of_stock,
        "low_stock": low_stock,
    })


@role_required("ADMIN", "HQ")
def admin_panel(request):
    run_housekeeping()
    freshness = freshness_summary()
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    all_paid_orders = Order.objects.filter(status__in=Order.SALE_STATUSES)
    month_orders = all_paid_orders.filter(paid_at__gte=month_start)

    month_sales = month_orders.aggregate(s=Sum("total_sales"))["s"] or Decimal("0.00")
    total_sales = all_paid_orders.aggregate(s=Sum("total_sales"))["s"] or Decimal("0.00")

    pending_dropshippers = User.objects.filter(role=User.Role.DROPSHIPPER, status=User.Status.PENDING)
    needs_refund_orders = Order.objects.filter(status=Order.Status.NEEDS_REFUND)

    # Top Dropshippers ranking
    top_dropshippers = (
        User.objects.filter(role=User.Role.DROPSHIPPER, orders__status__in=Order.SALE_STATUSES)
        .annotate(total_revenue=Sum("orders__total_sales"), orders_count=Count("orders"))
        .order_by("-total_revenue")[:10]
    )

    from payouts.models import Commission, Payout
    total_commission_paid = Payout.objects.filter(status=Payout.Status.PAID).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    pending_commissions = Commission.objects.filter(status=Commission.Status.EARNED).aggregate(s=Sum("commission_amount"))["s"] or Decimal("0.00")

    return render(request, "dashboard/admin_panel.html", {
        "month_sales": month_sales,
        "total_sales": total_sales,
        "total_commission_paid": total_commission_paid,
        "pending_commissions": pending_commissions,
        "pending_dropshippers": pending_dropshippers,
        "needs_refund_orders": needs_refund_orders,
        "top_dropshippers": top_dropshippers,
        "freshness": freshness,
    })

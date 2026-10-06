from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from .models import Commission, PayoutBatch, Payout
from .services import (
    create_weekly_payout_batch,
    execute_payout_batch,
    get_dropshipper_commission_stats,
)


@role_required("ADMIN", "HQ")
def admin_payouts(request):
    batches = PayoutBatch.objects.prefetch_related("payouts__dropshipper").all()
    pending_commissions = Commission.objects.filter(status=Commission.Status.EARNED).select_related("dropshipper", "order")

    # Dropshippers with unpaid commission
    unpaid_dropshippers = (
        User.objects.filter(role=User.Role.DROPSHIPPER, commissions__status=Commission.Status.EARNED)
        .distinct()
    )
    eligible_list = []
    for ds in unpaid_dropshippers:
        stats = get_dropshipper_commission_stats(ds)
        eligible_list.append({
            "dropshipper": ds,
            "pending_amount": stats["pending_payout"],
            "has_bank": ds.has_payout_bank_setup,
        })

    return render(request, "payouts/admin_payouts.html", {
        "batches": batches,
        "pending_commissions": pending_commissions,
        "eligible_list": eligible_list,
    })


@require_POST
@role_required("ADMIN", "HQ")
def admin_trigger_payout(request):
    batch = create_weekly_payout_batch(request.user)
    if not batch:
        messages.warning(request, "No eligible dropshippers with pending commissions or completed bank setups found.")
        return redirect("payouts:admin_payouts")

    batch = execute_payout_batch(batch)
    if batch.status == PayoutBatch.Status.COMPLETED:
        messages.success(
            request,
            f"Successfully processed {batch.batch_no}! Transferred RM{batch.total_amount} to {batch.payouts_count} dropshipper(s) via CHIP Send."
        )
    else:
        messages.warning(
            request,
            f"Batch {batch.batch_no} partially processed. Please inspect any failed bank transfers."
        )
    return redirect("payouts:admin_payouts")


def dropshipper_payouts(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.is_management:
        return redirect("payouts:admin_payouts")
    if not request.user.is_dropshipper or not request.user.is_approved:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    stats = get_dropshipper_commission_stats(request.user)
    commissions = Commission.objects.filter(dropshipper=request.user).select_related("order")
    payouts = Payout.objects.filter(dropshipper=request.user).select_related("batch")

    return render(request, "payouts/dropshipper_payouts.html", {
        "stats": stats,
        "commissions": commissions,
        "payouts": payouts,
    })

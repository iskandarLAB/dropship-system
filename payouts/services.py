from decimal import Decimal
import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import User
from .chip_send import ChipSendClient, ChipSendError
from .models import Commission, PayoutBatch, Payout

log = logging.getLogger("payouts")


@transaction.atomic
def credit_commission_for_order(order):
    """Credit 15% commission on clothing retail sales when an order is paid."""
    if hasattr(order, "commission"):
        return order.commission

    if not order.dropshipper.is_dropshipper:
        return None

    rate = settings.DROPSHIP_COMMISSION_PERCENT
    commission_amount = (order.total_sales * (rate / Decimal("100.00"))).quantize(Decimal("0.01"))

    comm = Commission.objects.create(
        order=order,
        dropshipper=order.dropshipper,
        rate_percent=rate,
        sales_amount=order.total_sales,
        commission_amount=commission_amount,
        status=Commission.Status.EARNED,
    )
    log.info("Credited RM%s commission (15%%) to %s for order %s", commission_amount, order.dropshipper, order.order_no)
    return comm


@transaction.atomic
def cancel_commission_for_order(order):
    """Cancel commission if order is cancelled or refunded."""
    comm = Commission.objects.filter(order=order, status=Commission.Status.EARNED).first()
    if comm:
        comm.status = Commission.Status.CANCELLED
        comm.save(update_fields=["status"])
        log.info("Cancelled commission for order %s", order.order_no)


def get_dropshipper_commission_stats(dropshipper):
    """Return dictionary of commission statistics for a dropshipper."""
    all_comms = Commission.objects.filter(dropshipper=dropshipper)
    total_earned = all_comms.filter(status__in=[Commission.Status.EARNED, Commission.Status.PAID]).aggregate(
        s=Sum("commission_amount")
    )["s"] or Decimal("0.00")
    
    paid_out = all_comms.filter(status=Commission.Status.PAID).aggregate(
        s=Sum("commission_amount")
    )["s"] or Decimal("0.00")

    pending_payout = all_comms.filter(status=Commission.Status.EARNED).aggregate(
        s=Sum("commission_amount")
    )["s"] or Decimal("0.00")

    return {
        "total_earned": total_earned,
        "paid_out": paid_out,
        "pending_payout": pending_payout,
    }


@transaction.atomic
def create_weekly_payout_batch(admin_user=None):
    """Generate a weekly payout batch for all dropshippers with pending commissions."""
    now = timezone.now()
    batch_no = f"PAY-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    pending_comms = Commission.objects.select_for_update().filter(status=Commission.Status.EARNED)
    if not pending_comms.exists():
        return None

    # Group pending commissions by dropshipper
    dropshippers_with_balance = (
        pending_comms.values("dropshipper")
        .annotate(total=Sum("commission_amount"))
        .filter(total__gte=settings.MINIMUM_PAYOUT_AMOUNT)
    )

    if not dropshippers_with_balance.exists():
        return None

    batch = PayoutBatch.objects.create(
        batch_no=batch_no,
        created_by=admin_user,
        status=PayoutBatch.Status.PENDING,
    )

    batch_total = Decimal("0.00")
    payout_count = 0

    for item in dropshippers_with_balance:
        user = User.objects.get(pk=item["dropshipper"])
        amount = item["total"]

        # Only create payout if dropshipper has filled in their bank details
        if not user.has_payout_bank_setup:
            log.warning("Skipping payout for %s: bank details missing", user)
            continue

        payout = Payout.objects.create(
            batch=batch,
            dropshipper=user,
            amount=amount,
            bank_name=user.bank_name,
            bank_account_number=user.bank_account_number,
            bank_account_holder=user.bank_account_holder,
            bank_id_number=user.bank_id_number,
            status=Payout.Status.PENDING,
        )

        # Attach pending commissions to this payout
        user_comms = Commission.objects.filter(dropshipper=user, status=Commission.Status.EARNED)
        user_comms.update(payout=payout)

        batch_total += amount
        payout_count += 1

    if payout_count == 0:
        batch.delete()
        return None

    batch.total_amount = batch_total
    batch.payouts_count = payout_count
    batch.save(update_fields=["total_amount", "payouts_count"])
    return batch


@transaction.atomic
def execute_payout_batch(batch):
    """Execute bank disbursements for a batch using CHIP Send."""
    client = ChipSendClient()
    success_count = 0
    now = timezone.now()

    for payout in batch.payouts.select_for_update().filter(status__in=[Payout.Status.PENDING, Payout.Status.FAILED]):
        user = payout.dropshipper
        try:
            # 1. Register or reuse bank account with CHIP Send
            if not user.chip_send_recipient_id:
                account_id = client.register_bank_account(user)
                user.chip_send_recipient_id = str(account_id)
                user.save(update_fields=["chip_send_recipient_id"])
            else:
                account_id = user.chip_send_recipient_id

            # 2. Initiate payout instruction via CHIP Send
            reference = f"{batch.batch_no}-{payout.pk}"
            res = client.create_send_instruction(account_id, float(payout.amount), reference)

            instruction_id = str(res.get("id") or res.get("instruction_id") or "CHIP-OK")
            payout.chip_send_account_id = str(account_id)
            payout.chip_send_instruction_id = instruction_id
            payout.status = Payout.Status.PAID
            payout.paid_at = now
            payout.error_message = ""
            payout.save()

            # Mark linked commissions as PAID
            payout.commissions.update(status=Commission.Status.PAID)
            success_count += 1

        except ChipSendError as e:
            log.error("Payout failed for %s: %s", payout, e)
            payout.status = Payout.Status.FAILED
            payout.error_message = str(e)
            payout.save()

    if success_count == batch.payouts.count():
        batch.status = PayoutBatch.Status.COMPLETED
    else:
        batch.status = PayoutBatch.Status.PARTIAL_FAILED
    batch.processed_at = now
    batch.save(update_fields=["status", "processed_at"])
    return batch

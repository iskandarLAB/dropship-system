from django.core.management.base import BaseCommand
from payouts.services import create_weekly_payout_batch, execute_payout_batch


class Command(BaseCommand):
    help = "Generate and execute weekly commission payout batch to dropshippers via CHIP Send."

    def handle(self, *args, **options):
        self.stdout.write("Running weekly commission payout batch processor...")
        batch = create_weekly_payout_batch(admin_user=None)
        if not batch:
            self.stdout.write(self.style.NOTICE("No eligible dropshippers with pending commissions found."))
            return

        batch = execute_payout_batch(batch)
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed {batch.batch_no}: Disbursed RM{batch.total_amount} to {batch.payouts_count} dropshipper(s) via CHIP Send ({batch.status})."
            )
        )

from django.core.management.base import BaseCommand

from orders.services import auto_complete_shipped, expire_unpaid_orders


class Command(BaseCommand):
    help = "Cancel unpaid orders past their payment window and auto-complete old shipped orders."

    def handle(self, *args, **opts):
        expired = expire_unpaid_orders()
        completed = auto_complete_shipped()
        self.stdout.write(self.style.SUCCESS(f"Expired {expired} order(s); auto-completed {completed}."))

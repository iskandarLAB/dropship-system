from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("created_at", "order", "gateway", "purchase_id", "amount", "status", "gateway_status")
    list_filter = ("gateway", "status")
    search_fields = ("purchase_id", "order__order_no")
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

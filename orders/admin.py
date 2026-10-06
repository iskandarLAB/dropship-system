from django.contrib import admin, messages

from payments.models import Payment

from . import services
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("variant", "quantity", "unit_cost", "unit_sell_price")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("gateway", "purchase_id", "amount_cents", "status", "created_at", "updated_at")
    exclude = ("raw_payload", "checkout_url")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_no", "created_at", "dropshipper", "status", "customer_name", "state",
                    "total_payable", "total_sales", "tracking_no")
    list_filter = ("status", "state", "created_at")
    search_fields = ("order_no", "customer_name", "customer_phone", "tracking_no", "dropshipper__username")
    inlines = [OrderItemInline, PaymentInline]
    readonly_fields = ("order_no", "dropshipper", "status", "subtotal_cost", "shipping_fee", "total_payable",
                       "total_sales", "stock_reserved", "created_at", "expires_at", "paid_at", "shipped_at",
                       "completed_at", "shipped_by", "cancel_reason")
    actions = ["cancel_orders", "complete_orders"]

    def has_add_permission(self, request):
        return False  # orders must go through the dropshipper flow (stock + payment)

    @admin.action(description="Cancel selected orders (restore stock)")
    def cancel_orders(self, request, queryset):
        for o in queryset:
            try:
                services.cancel_order(o, request.user, "Cancelled by admin")
            except services.OrderError as e:
                self.message_user(request, f"{o}: {e}", messages.WARNING)

    @admin.action(description="Mark selected shipped orders as completed")
    def complete_orders(self, request, queryset):
        for o in queryset:
            try:
                services.complete_order(o)
            except services.OrderError as e:
                self.message_user(request, f"{o}: {e}", messages.WARNING)

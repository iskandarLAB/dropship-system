from django.contrib import admin
from .models import Commission, PayoutBatch, Payout


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ("order", "dropshipper", "rate_percent", "sales_amount", "commission_amount", "status", "created_at")
    list_filter = ("status", "rate_percent")
    search_fields = ("order__order_no", "dropshipper__username")
    readonly_fields = [f.name for f in Commission._meta.fields]

    def has_add_permission(self, request):
        return False


class PayoutInline(admin.TabularInline):
    model = Payout
    extra = 0
    readonly_fields = ("dropshipper", "amount", "bank_name", "bank_account_number", "chip_send_instruction_id", "status", "paid_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PayoutBatch)
class PayoutBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_no", "total_amount", "payouts_count", "status", "created_at", "processed_at")
    list_filter = ("status",)
    search_fields = ("batch_no",)
    inlines = [PayoutInline]
    readonly_fields = [f.name for f in PayoutBatch._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("batch", "dropshipper", "amount", "bank_name", "chip_send_instruction_id", "status", "paid_at")
    list_filter = ("status", "bank_name")
    search_fields = ("dropshipper__username", "chip_send_instruction_id")
    readonly_fields = [f.name for f in Payout._meta.fields]

    def has_add_permission(self, request):
        return False

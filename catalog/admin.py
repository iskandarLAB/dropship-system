from django.contrib import admin

from .models import Product, ShippingRate, StockLog, Variant


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 1
    fields = ("size", "colour", "sku", "stock", "sort_order", "stock_updated_at")
    readonly_fields = ("stock_updated_at",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku_prefix", "dropship_price", "suggested_retail_price", "total_stock", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "sku_prefix")
    inlines = [VariantInline]


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "colour", "size", "stock", "stock_updated_at")
    list_filter = ("product", "colour", "size")
    search_fields = ("sku", "product__name")


@admin.register(StockLog)
class StockLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "variant", "old_qty", "new_qty", "reason", "user", "note")
    list_filter = ("reason", "created_at")
    search_fields = ("variant__sku", "note")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = ("region", "fee")
    list_editable = ("fee",)

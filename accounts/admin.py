from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "shop_name", "email", "phone", "role", "status", "date_joined")
    list_filter = ("role", "status", "is_active")
    search_fields = ("username", "email", "shop_name", "phone", "first_name")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Dropship", {"fields": ("role", "status", "phone", "shop_name", "approved_at", "approved_by")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Dropship", {"fields": ("role", "status", "email", "phone", "shop_name")}),
    )
    readonly_fields = ("approved_at", "approved_by")
    actions = ["approve", "reject", "suspend"]

    @admin.action(description="Approve selected users")
    def approve(self, request, queryset):
        for u in queryset:
            u.approve(request.user)
        self.message_user(request, f"{queryset.count()} user(s) approved.")

    @admin.action(description="Reject selected users")
    def reject(self, request, queryset):
        queryset.update(status=User.Status.REJECTED)

    @admin.action(description="Suspend selected users")
    def suspend(self, request, queryset):
        queryset.update(status=User.Status.SUSPENDED)

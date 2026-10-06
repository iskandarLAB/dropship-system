from django.urls import path

from . import views

app_name = "payouts"

urlpatterns = [
    path("admin-panel/payouts/", views.admin_payouts, name="admin_payouts"),
    path("admin-panel/payouts/trigger/", views.admin_trigger_payout, name="admin_trigger_payout"),
    path("payouts/", views.dropshipper_payouts, name="dropshipper_payouts"),
]

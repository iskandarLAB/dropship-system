from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("dashboard/", views.dropshipper_dashboard, name="dropshipper"),
    path("hq/", views.hq_home, name="hq_home"),
    path("admin-panel/", views.admin_panel, name="admin_panel"),
]

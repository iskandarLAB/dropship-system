from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.order_list, name="list"),
    path("new/", views.order_new, name="new"),
    path("<int:pk>/", views.order_detail, name="detail"),
    path("<int:pk>/cancel/", views.order_cancel, name="cancel"),
    path("hq/", views.hq_orders, name="hq_orders"),
    path("hq/<int:pk>/ship/", views.hq_ship, name="hq_ship"),
    path("hq/<int:pk>/complete/", views.hq_complete, name="hq_complete"),
    path("hq/<int:pk>/slip/", views.packing_slip, name="packing_slip"),
    path("export.csv", views.export_csv, name="export_csv"),
]

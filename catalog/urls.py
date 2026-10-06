from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("hq/stock/", views.hq_stock, name="hq_stock"),
    path("stock/", views.stock_list, name="stock_list"),
    path("shop/<str:username>/", views.affiliate_store, name="affiliate_store"),
    path("shop/<str:username>/order/", views.affiliate_order, name="affiliate_order"),
]

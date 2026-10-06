from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("start/<int:order_id>/", views.start, name="start"),
    path("return/", views.payment_return, name="return"),
    path("chip/callback/", views.chip_callback, name="chip_callback"),
    path("dummy/<str:purchase_id>/", views.dummy_checkout, name="dummy_checkout"),
]

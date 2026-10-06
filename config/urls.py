from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Dropship Admin"
admin.site.site_title = "Dropship Admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("catalog.urls")),
    path("orders/", include("orders.urls")),
    path("payments/", include("payments.urls")),
    path("", include("payouts.urls")),
    path("", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

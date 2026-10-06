from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/bank/", views.profile_bank, name="profile_bank"),
    path("admin-panel/dropshippers/", views.dropshipper_list, name="dropshippers"),
    path(
        "admin-panel/dropshippers/<int:pk>/<str:action>/",
        views.dropshipper_action,
        name="dropshipper_action",
    ),
]

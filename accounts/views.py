from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import ApprovedAuthenticationForm, DropshipperRegistrationForm, BankDetailsForm
from .models import User


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = ApprovedAuthenticationForm
    redirect_authenticated_user = True


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:home")
    if request.method == "POST":
        form = DropshipperRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "accounts/register_done.html")
    else:
        form = DropshipperRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def home(request):
    """Redirect to the right landing page for the user's role."""
    user = request.user
    if user.is_admin_role:
        return redirect("dashboard:admin_panel")
    if user.is_hq:
        return redirect("dashboard:hq_home")
    return redirect("dashboard:dropshipper")


@role_required("ADMIN", "HQ")
def dropshipper_list(request):
    status = request.GET.get("status", User.Status.PENDING)
    users = User.objects.filter(role=User.Role.DROPSHIPPER)
    if status != "ALL":
        users = users.filter(status=status)
    return render(
        request,
        "accounts/dropshipper_list.html",
        {"users": users.order_by("-date_joined"), "status": status, "statuses": User.Status.choices},
    )


@require_POST
@role_required("ADMIN", "HQ")
def dropshipper_action(request, pk, action):
    user = get_object_or_404(User, pk=pk, role=User.Role.DROPSHIPPER)
    if action == "approve":
        user.approve(request.user)
    elif action == "reject":
        user.set_status(User.Status.REJECTED)
    elif action == "suspend":
        user.set_status(User.Status.SUSPENDED)
    else:
        messages.error(request, "Unknown action.")
        return redirect("accounts:dropshippers")
    messages.success(request, f"{user} is now {user.get_status_display().lower()}.")
    return redirect(request.POST.get("next") or "accounts:dropshippers")


@role_required("DROPSHIPPER")
def profile_bank(request):
    user = request.user
    if request.method == "POST":
        form = BankDetailsForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your payout bank details have been updated successfully.")
            return redirect("accounts:profile_bank")
    else:
        form = BankDetailsForm(instance=user)
    return render(request, "accounts/profile_bank.html", {"form": form})

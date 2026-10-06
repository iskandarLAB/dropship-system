from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User

STATUS_MESSAGES = {
    User.Status.PENDING: "Your account is awaiting admin approval. Please check back later.",
    User.Status.REJECTED: "Your registration was not approved. Please contact the admin.",
    User.Status.SUSPENDED: "Your account has been suspended. Please contact the admin.",
}


class ApprovedAuthenticationForm(AuthenticationForm):
    """Login form that blocks users who are not approved."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_approved:
            raise forms.ValidationError(
                STATUS_MESSAGES.get(user.status, "Account not active."), code="not_approved"
            )


class DropshipperRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(label="Full name", max_length=150)
    shop_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, help_text="e.g. 0123456789")
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("first_name", "shop_name", "email", "phone", "username")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error("password_confirm", "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        # Never trust client input for role/status.
        user.role = User.Role.DROPSHIPPER
        user.status = User.Status.PENDING
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class BankDetailsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("bank_name", "bank_account_number", "bank_account_holder", "bank_id_number")
        widgets = {
            "bank_name": forms.Select(attrs={"class": "form-select"}),
            "bank_account_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 164012345678"}),
            "bank_account_holder": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full name as in bank account"}),
            "bank_id_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 950101-14-1234 (for bank verification)"}),
        }

    def clean_bank_account_number(self):
        acc = self.cleaned_data.get("bank_account_number", "").strip().replace(" ", "").replace("-", "")
        if not acc.isdigit():
            raise forms.ValidationError("Account number must contain only numbers.")
        return acc

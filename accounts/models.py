from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


MALAYSIAN_BANKS = [
    ("Maybank", "Maybank (Malayan Banking Berhad)"),
    ("CIMB Bank", "CIMB Bank"),
    ("Public Bank", "Public Bank"),
    ("RHB Bank", "RHB Bank"),
    ("Hong Leong Bank", "Hong Leong Bank"),
    ("AmBank", "AmBank"),
    ("Bank Islam", "Bank Islam Malaysia"),
    ("BSN", "Bank Simpanan Nasional"),
    ("Affin Bank", "Affin Bank"),
    ("Alliance Bank", "Alliance Bank"),
    ("Bank Rakyat", "Bank Kerjasama Rakyat Malaysia"),
    ("OCBC Bank", "OCBC Bank (Malaysia)"),
    ("UOB Bank", "United Overseas Bank (Malaysia)"),
    ("HSBC Bank", "HSBC Bank Malaysia"),
    ("Standard Chartered", "Standard Chartered Bank"),
]


class User(AbstractUser):
    class Role(models.TextChoices):
        HQ = "HQ", "HQ"
        ADMIN = "ADMIN", "Admin"
        DROPSHIPPER = "DROPSHIPPER", "Dropshipper"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUSPENDED = "SUSPENDED", "Suspended"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.DROPSHIPPER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    phone = models.CharField(max_length=20, blank=True)
    shop_name = models.CharField(max_length=100, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # Bank payout details (for weekly CHIP Send disbursements)
    bank_name = models.CharField(max_length=50, choices=MALAYSIAN_BANKS, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_account_holder = models.CharField(max_length=150, blank=True)
    bank_id_number = models.CharField(max_length=30, blank=True, help_text="MyKad / NRIC / Passport for CHIP Send KYC")
    chip_send_recipient_id = models.CharField(max_length=100, blank=True)

    @property
    def is_hq(self):
        return self.role == self.Role.HQ

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_management(self):
        return self.is_hq or self.is_admin_role

    @property
    def is_dropshipper(self):
        return self.role == self.Role.DROPSHIPPER

    @property
    def has_payout_bank_setup(self):
        return bool(self.bank_name and self.bank_account_number and self.bank_account_holder)

    @property
    def is_approved(self):
        # Superusers are always allowed in (bootstrap / emergency access).
        return self.is_superuser or self.status == self.Status.APPROVED

    def approve(self, by_user):
        self.status = self.Status.APPROVED
        self.approved_at = timezone.now()
        self.approved_by = by_user
        self.save(update_fields=["status", "approved_at", "approved_by"])

    def set_status(self, status):
        self.status = status
        self.save(update_fields=["status"])

    def __str__(self):
        return self.shop_name or self.get_full_name() or self.username

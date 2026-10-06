from django.test import TestCase
from django.urls import reverse
from accounts.models import User


class AccountsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adminuser", email="admin@test.com", password="password123",
            role=User.Role.ADMIN, status=User.Status.APPROVED
        )

    def test_registration_creates_pending_dropshipper(self):
        url = reverse("accounts:register")
        data = {
            "first_name": "Test Seller",
            "shop_name": "My Shop",
            "email": "seller@test.com",
            "phone": "0123456789",
            "username": "seller1",
            "password": "Password123!",
            "password_confirm": "Password123!",
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 200)  # Renders register_done
        user = User.objects.get(username="seller1")
        self.assertEqual(user.role, User.Role.DROPSHIPPER)
        self.assertEqual(user.status, User.Status.PENDING)
        self.assertFalse(user.is_approved)

    def test_pending_user_cannot_login(self):
        user = User.objects.create_user(
            username="pendinguser", password="password123",
            role=User.Role.DROPSHIPPER, status=User.Status.PENDING
        )
        login_url = reverse("accounts:login")
        resp = self.client.post(login_url, {"username": "pendinguser", "password": "password123"})
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_approved_user_can_login(self):
        user = User.objects.create_user(
            username="approveduser", password="password123",
            role=User.Role.DROPSHIPPER, status=User.Status.APPROVED
        )
        login_url = reverse("accounts:login")
        resp = self.client.post(login_url, {"username": "approveduser", "password": "password123"})
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

    def test_admin_approve_and_suspend_actions(self):
        self.client.force_login(self.admin)
        user = User.objects.create_user(
            username="candidate", password="password123",
            role=User.Role.DROPSHIPPER, status=User.Status.PENDING
        )
        
        # Approve
        resp = self.client.post(reverse("accounts:dropshipper_action", kwargs={"pk": user.pk, "action": "approve"}))
        user.refresh_from_db()
        self.assertEqual(user.status, User.Status.APPROVED)
        self.assertEqual(user.approved_by, self.admin)

        # Suspend
        resp = self.client.post(reverse("accounts:dropshipper_action", kwargs={"pk": user.pk, "action": "suspend"}))
        user.refresh_from_db()
        self.assertEqual(user.status, User.Status.SUSPENDED)

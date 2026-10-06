import hashlib
import hmac
import logging
import time
import uuid

import requests
from django.conf import settings

log = logging.getLogger("payouts")


class ChipSendError(Exception):
    pass


class ChipSendClient:
    """Client for CHIP Send API (Automated Bank Payouts)."""

    def __init__(self):
        self.base_url = settings.CHIP_SEND_API_BASE.rstrip("/")
        self.api_key = settings.CHIP_SEND_API_KEY
        self.api_secret = settings.CHIP_SEND_API_SECRET
        self.is_simulator = settings.CHIP_SEND_SIMULATOR

    def _get_auth_headers(self):
        epoch = str(int(time.time()))
        signing_string = f"{epoch}{self.api_key}"
        checksum = hmac.new(
            self.api_secret.encode("utf-8"),
            signing_string.encode("utf-8"),
            hashlib.sha512
        ).hexdigest()
        return {
            "Authorization": f"Bearer {self.api_key}",
            "epoch": epoch,
            "checksum": checksum,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def register_bank_account(self, dropshipper):
        """Register recipient bank account with CHIP Send."""
        if self.is_simulator:
            mock_id = f"mock-bank-acc-{uuid.uuid4().hex[:12]}"
            log.info("[SIMULATOR] Registered CHIP Send bank account: %s for %s", mock_id, dropshipper)
            return mock_id

        if not self.api_key or not self.api_secret:
            raise ChipSendError("CHIP_SEND_API_KEY and CHIP_SEND_API_SECRET must be configured in .env")

        headers = self._get_auth_headers()
        payload = {
            "name": dropshipper.bank_account_holder,
            "bank_name": dropshipper.bank_name,
            "account_number": dropshipper.bank_account_number,
            "id_number": dropshipper.bank_id_number or "000000000000",
            "email": dropshipper.email,
        }
        try:
            r = requests.post(f"{self.base_url}/send/bank_accounts", json=payload, headers=headers, timeout=20)
            r.raise_for_status()
            data = r.json()
            return data.get("id") or data.get("results", {}).get("id")
        except Exception as e:
            log.exception("CHIP Send register_bank_account failed for %s", dropshipper)
            raise ChipSendError(f"Could not register bank account with CHIP Send: {e}") from e

    def create_send_instruction(self, bank_account_id, amount_rm, reference):
        """Initiate bank transfer (disbursement) to registered bank account."""
        amount_cents = int(round(amount_rm * 100))
        if self.is_simulator:
            mock_instruction_id = f"CHIP-SEND-{uuid.uuid4().hex[:12].upper()}"
            log.info("[SIMULATOR] Created CHIP Send disbursement %s for RM%.2f (ref: %s)", mock_instruction_id, amount_rm, reference)
            return {"id": mock_instruction_id, "status": "paid", "amount": amount_cents}

        if not self.api_key or not self.api_secret:
            raise ChipSendError("CHIP_SEND_API_KEY and CHIP_SEND_API_SECRET must be configured in .env")

        headers = self._get_auth_headers()
        payload = {
            "bank_account_id": bank_account_id,
            "amount": amount_cents,
            "currency": "MYR",
            "reference": reference[:40],
        }
        try:
            r = requests.post(f"{self.base_url}/send/send_instructions", json=payload, headers=headers, timeout=25)
            r.raise_for_status()
            data = r.json()
            return data
        except Exception as e:
            log.exception("CHIP Send create_send_instruction failed for %s", reference)
            raise ChipSendError(f"CHIP Send payout failed: {e}") from e

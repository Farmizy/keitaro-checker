from typing import Any, Optional
from uuid import UUID

from supabase import Client

from app.core.encryption import encrypt, decrypt
from app.db.client import get_supabase

ENCRYPTED_FIELDS = {"access_token", "cookie", "proxy_password"}


def _encrypt_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Encrypt sensitive fields before writing to DB."""
    result = dict(data)
    for field in ENCRYPTED_FIELDS:
        if field in result and result[field] is not None:
            result[field] = encrypt(result[field])
    return result


def _decrypt_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Decrypt sensitive fields after reading from DB."""
    result = dict(data)
    for field in ENCRYPTED_FIELDS:
        if field in result and result[field] is not None:
            result[field] = decrypt(result[field])
    return result


class DatabaseService:
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase()

    # --- fb_accounts ---

    def get_accounts(self) -> list[dict]:
        response = self.client.table("fb_accounts").select("*").execute()
        return [_decrypt_fields(row) for row in response.data]

    def get_account(self, account_id: UUID) -> Optional[dict]:
        response = (
            self.client.table("fb_accounts")
            .select("*")
            .eq("id", str(account_id))
            .execute()
        )
        if not response.data:
            return None
        return _decrypt_fields(response.data[0])

    def create_account(self, data: dict[str, Any]) -> dict:
        encrypted = _encrypt_fields(data)
        response = self.client.table("fb_accounts").insert(encrypted).execute()
        return _decrypt_fields(response.data[0])

    def update_account(self, account_id: UUID, data: dict[str, Any]) -> Optional[dict]:
        encrypted = _encrypt_fields(data)
        response = (
            self.client.table("fb_accounts")
            .update(encrypted)
            .eq("id", str(account_id))
            .execute()
        )
        if not response.data:
            return None
        return _decrypt_fields(response.data[0])

    def delete_account(self, account_id: UUID) -> bool:
        response = (
            self.client.table("fb_accounts")
            .delete()
            .eq("id", str(account_id))
            .execute()
        )
        return len(response.data) > 0

    def get_active_accounts(self) -> list[dict]:
        response = (
            self.client.table("fb_accounts")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        return [_decrypt_fields(row) for row in response.data]

    def upsert_account_by_panel_id(self, panel_id: int, data: dict[str, Any]) -> dict:
        """Upsert account by panel_account_id."""
        existing = (
            self.client.table("fb_accounts")
            .select("*")
            .eq("panel_account_id", panel_id)
            .execute()
        )
        if existing.data:
            response = (
                self.client.table("fb_accounts")
                .update(data)
                .eq("panel_account_id", panel_id)
                .execute()
            )
            return response.data[0]
        response = self.client.table("fb_accounts").insert(data).execute()
        return response.data[0]

    # --- campaigns ---

    def get_campaigns(
        self,
        account_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        query = self.client.table("campaigns").select("*")
        if account_id:
            query = query.eq("fb_account_id", str(account_id))
        if status:
            query = query.eq("status", status)
        response = query.execute()
        return response.data

    def get_campaign_by_fb_ids(
        self, fb_account_id: str, fb_campaign_id: str,
    ) -> Optional[dict]:
        response = (
            self.client.table("campaigns")
            .select("*")
            .eq("fb_account_id", fb_account_id)
            .eq("fb_campaign_id", fb_campaign_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def get_campaign(self, campaign_id: UUID) -> Optional[dict]:
        response = (
            self.client.table("campaigns")
            .select("*")
            .eq("id", str(campaign_id))
            .execute()
        )
        return response.data[0] if response.data else None

    def upsert_campaign(self, data: dict[str, Any]) -> dict:
        response = (
            self.client.table("campaigns")
            .upsert(data, on_conflict="fb_account_id,fb_campaign_id")
            .execute()
        )
        return response.data[0]

    def update_campaign(self, campaign_id: UUID, data: dict[str, Any]) -> Optional[dict]:
        response = (
            self.client.table("campaigns")
            .update(data)
            .eq("id", str(campaign_id))
            .execute()
        )
        return response.data[0] if response.data else None

    # --- action_logs ---

    def create_action_log(self, data: dict[str, Any]) -> dict:
        response = self.client.table("action_logs").insert(data).execute()
        return response.data[0]

    def get_action_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        campaign_id: Optional[UUID] = None,
    ) -> list[dict]:
        query = (
            self.client.table("action_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if campaign_id:
            query = query.eq("campaign_id", str(campaign_id))
        response = query.execute()
        return response.data

    # --- check_runs ---

    def create_check_run(self, data: dict[str, Any]) -> dict:
        response = self.client.table("check_runs").insert(data).execute()
        return response.data[0]

    def update_check_run(self, run_id: UUID, data: dict[str, Any]) -> Optional[dict]:
        response = (
            self.client.table("check_runs")
            .update(data)
            .eq("id", str(run_id))
            .execute()
        )
        return response.data[0] if response.data else None

    def get_latest_check_runs(self, limit: int = 10) -> list[dict]:
        response = (
            self.client.table("check_runs")
            .select("*")
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data

    # --- rule_sets / rule_steps ---

    def get_default_rule_set(self) -> Optional[dict]:
        response = (
            self.client.table("rule_sets")
            .select("*, rule_steps(*)")
            .eq("is_default", True)
            .execute()
        )
        return response.data[0] if response.data else None

    def get_rule_sets(self) -> list[dict]:
        response = (
            self.client.table("rule_sets")
            .select("*, rule_steps(*)")
            .execute()
        )
        return response.data

    def update_rule_step(self, step_id: UUID, data: dict[str, Any]) -> Optional[dict]:
        response = (
            self.client.table("rule_steps")
            .update(data)
            .eq("id", str(step_id))
            .execute()
        )
        return response.data[0] if response.data else None

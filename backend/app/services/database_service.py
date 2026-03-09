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
        if field in result and result[field]:
            result[field] = encrypt(result[field])
    return result


def _decrypt_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Decrypt sensitive fields after reading from DB."""
    result = dict(data)
    for field in ENCRYPTED_FIELDS:
        if field in result and result[field]:
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

    def get_account_by_panel_id(self, panel_id: int) -> Optional[dict]:
        """Get account by panel_account_id."""
        response = (
            self.client.table("fb_accounts")
            .select("*")
            .eq("panel_account_id", panel_id)
            .execute()
        )
        return _decrypt_fields(response.data[0]) if response.data else None

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

    # --- fb_account_profiles ---

    def get_account_profiles(self) -> list[dict]:
        response = self.client.table("fb_account_profiles").select("*").execute()
        return response.data

    def get_account_profile_by_account(self, fb_account_id: UUID) -> Optional[dict]:
        response = (
            self.client.table("fb_account_profiles")
            .select("*")
            .eq("fb_account_id", str(fb_account_id))
            .execute()
        )
        return response.data[0] if response.data else None

    def create_account_profile(self, data: dict[str, Any]) -> dict:
        response = self.client.table("fb_account_profiles").insert(data).execute()
        return response.data[0]

    def update_account_profile(self, profile_id: UUID, data: dict[str, Any]) -> Optional[dict]:
        response = (
            self.client.table("fb_account_profiles")
            .update(data)
            .eq("id", str(profile_id))
            .execute()
        )
        return response.data[0] if response.data else None

    # --- Auto-Launch Settings ---

    def get_auto_launch_settings(self) -> Optional[dict]:
        response = self.client.table("auto_launch_settings").select("*").limit(1).execute()
        return response.data[0] if response.data else None

    def update_auto_launch_settings(self, data: dict[str, Any]) -> Optional[dict]:
        current = self.get_auto_launch_settings()
        if not current:
            response = self.client.table("auto_launch_settings").insert(data).execute()
            return response.data[0] if response.data else None
        data["updated_at"] = "now()"
        response = (
            self.client.table("auto_launch_settings")
            .update(data)
            .eq("id", current["id"])
            .execute()
        )
        return response.data[0] if response.data else None

    # --- Auto-Launch Queue ---

    def add_to_launch_queue(self, data: dict[str, Any]) -> dict:
        response = self.client.table("auto_launch_queue").upsert(
            data, on_conflict="campaign_id,launch_date"
        ).execute()
        return response.data[0]

    def get_launch_queue(
        self,
        launch_date: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        query = self.client.table("auto_launch_queue").select("*")
        if launch_date:
            query = query.eq("launch_date", launch_date)
        if status:
            query = query.eq("status", status)
        query = query.order("created_at")
        return query.execute().data

    def update_launch_queue_item(self, item_id: str, data: dict[str, Any]) -> Optional[dict]:
        response = (
            self.client.table("auto_launch_queue")
            .update(data)
            .eq("id", item_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def clear_old_launch_queue(self, before_date: str) -> None:
        self.client.table("auto_launch_queue") \
            .delete() \
            .lt("launch_date", before_date) \
            .in_("status", ["launched", "skipped", "failed", "removed"]) \
            .execute()

    # --- Auto-Launch Blacklist ---

    def get_blacklist(self) -> list[dict]:
        return (
            self.client.table("auto_launch_blacklist")
            .select("*")
            .order("blacklisted_at", desc=True)
            .execute()
            .data
        )

    def get_blacklisted_campaign_ids(self) -> set[str]:
        response = self.client.table("auto_launch_blacklist").select("campaign_id").execute()
        return {row["campaign_id"] for row in response.data}

    def add_to_blacklist(self, data: dict[str, Any]) -> dict:
        response = self.client.table("auto_launch_blacklist").upsert(
            data, on_conflict="campaign_id"
        ).execute()
        return response.data[0]

    def remove_from_blacklist(self, campaign_id: str) -> bool:
        response = (
            self.client.table("auto_launch_blacklist")
            .delete()
            .eq("campaign_id", campaign_id)
            .execute()
        )
        return len(response.data) > 0

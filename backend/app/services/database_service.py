from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from supabase import Client

from app.core.encryption import encrypt, decrypt
from app.db.client import get_supabase, get_supabase_admin

ENCRYPTED_FIELDS = {"access_token", "cookie", "proxy_password"}

USER_SETTINGS_ENCRYPTED_FIELDS = {
    "keitaro_login", "keitaro_password", "fbtool_cookies", "telegram_bot_token",
}


def _encrypt_fields(
    data: dict[str, Any],
    fields: set[str] = ENCRYPTED_FIELDS,
) -> dict[str, Any]:
    """Encrypt sensitive fields before writing to DB."""
    result = dict(data)
    for field in fields:
        if field in result and result[field]:
            result[field] = encrypt(result[field])
    return result


def _decrypt_fields(
    data: dict[str, Any],
    fields: set[str] = ENCRYPTED_FIELDS,
) -> dict[str, Any]:
    """Decrypt sensitive fields after reading from DB."""
    result = dict(data)
    for field in fields:
        if field in result and result[field]:
            result[field] = decrypt(result[field])
    return result


class DatabaseService:
    def __init__(self, client: Optional[Client] = None, user_id: Optional[str] = None):
        self.client = client or get_supabase()
        self.user_id = user_id
        self._cached_account_ids: Optional[list[str]] = None

    @classmethod
    def for_user(cls, user_id: str) -> "DatabaseService":
        """Create service scoped to a user (admin client + app-level filtering)."""
        return cls(client=get_supabase_admin(), user_id=user_id)

    @classmethod
    def admin(cls, user_id: Optional[str] = None) -> "DatabaseService":
        """Create service with admin client (bypasses RLS). For background tasks."""
        return cls(client=get_supabase_admin(), user_id=user_id)

    # --- helpers ---

    def _get_user_account_ids(self) -> list[str]:
        """Get list of fb_accounts.id UUIDs for current user. Cached per instance."""
        if not self.user_id:
            return []
        if self._cached_account_ids is not None:
            return self._cached_account_ids
        response = (
            self.client.table("fb_accounts")
            .select("id")
            .eq("user_id", self.user_id)
            .execute()
        )
        self._cached_account_ids = [row["id"] for row in response.data]
        return self._cached_account_ids

    # --- fb_accounts ---

    def get_accounts(self) -> list[dict]:
        query = self.client.table("fb_accounts").select("*")
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.execute()
        return [_decrypt_fields(row) for row in response.data]

    def get_account(self, account_id: UUID) -> Optional[dict]:
        query = (
            self.client.table("fb_accounts")
            .select("*")
            .eq("id", str(account_id))
        )
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.execute()
        if not response.data:
            return None
        return _decrypt_fields(response.data[0])

    def create_account(self, data: dict[str, Any]) -> dict:
        encrypted = _encrypt_fields(data)
        if self.user_id and "user_id" not in encrypted:
            encrypted["user_id"] = self.user_id
        response = self.client.table("fb_accounts").insert(encrypted).execute()
        self._cached_account_ids = None  # invalidate cache
        return _decrypt_fields(response.data[0])

    def update_account(self, account_id: UUID, data: dict[str, Any]) -> Optional[dict]:
        encrypted = _encrypt_fields(data)
        query = (
            self.client.table("fb_accounts")
            .update(encrypted)
            .eq("id", str(account_id))
        )
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.execute()
        if not response.data:
            return None
        return _decrypt_fields(response.data[0])

    def delete_account(self, account_id: UUID) -> bool:
        query = (
            self.client.table("fb_accounts")
            .delete()
            .eq("id", str(account_id))
        )
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.execute()
        self._cached_account_ids = None  # invalidate cache
        return len(response.data) > 0

    def get_active_accounts(self) -> list[dict]:
        query = (
            self.client.table("fb_accounts")
            .select("*")
            .eq("is_active", True)
        )
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.execute()
        return [_decrypt_fields(row) for row in response.data]

    def get_account_by_fbtool_id(self, fbtool_id: int) -> Optional[dict]:
        """Get account by fbtool_account_id."""
        query = (
            self.client.table("fb_accounts")
            .select("*")
            .eq("fbtool_account_id", fbtool_id)
        )
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.execute()
        return _decrypt_fields(response.data[0]) if response.data else None

    def upsert_account_by_fbtool_id(self, fbtool_id: int, data: dict[str, Any]) -> dict:
        """Upsert account by fbtool_account_id."""
        query = (
            self.client.table("fb_accounts")
            .select("*")
            .eq("fbtool_account_id", fbtool_id)
        )
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        existing = query.execute()

        if existing.data:
            update_query = (
                self.client.table("fb_accounts")
                .update(data)
                .eq("fbtool_account_id", fbtool_id)
            )
            if self.user_id:
                update_query = update_query.eq("user_id", self.user_id)
            response = update_query.execute()
            return response.data[0]

        if self.user_id and "user_id" not in data:
            data["user_id"] = self.user_id
        response = self.client.table("fb_accounts").insert(data).execute()
        self._cached_account_ids = None  # invalidate cache
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
        elif self.user_id:
            account_ids = self._get_user_account_ids()
            if not account_ids:
                return []
            query = query.in_("fb_account_id", account_ids)
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
        query = (
            self.client.table("campaigns")
            .select("*")
            .eq("id", str(campaign_id))
        )
        if self.user_id:
            account_ids = self._get_user_account_ids()
            if not account_ids:
                return None
            query = query.in_("fb_account_id", account_ids)
        response = query.execute()
        return response.data[0] if response.data else None

    def upsert_campaign(self, data: dict[str, Any]) -> dict:
        response = (
            self.client.table("campaigns")
            .upsert(data, on_conflict="fb_account_id,fb_campaign_id")
            .execute()
        )
        return response.data[0]

    def update_campaign(self, campaign_id: UUID, data: dict[str, Any]) -> Optional[dict]:
        query = (
            self.client.table("campaigns")
            .update(data)
            .eq("id", str(campaign_id))
        )
        if self.user_id:
            account_ids = self._get_user_account_ids()
            if not account_ids:
                return None
            query = query.in_("fb_account_id", account_ids)
        response = query.execute()
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
        if self.user_id:
            account_ids = self._get_user_account_ids()
            if not account_ids:
                return []
            query = query.in_("fb_account_id", account_ids)
        response = query.execute()
        return response.data

    # --- check_runs ---

    def create_check_run(self, data: dict[str, Any]) -> dict:
        if self.user_id and "user_id" not in data:
            data["user_id"] = self.user_id
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
        query = (
            self.client.table("check_runs")
            .select("*")
            .order("started_at", desc=True)
            .limit(limit)
        )
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.execute()
        return response.data

    # --- rule_sets / rule_steps ---

    def get_default_rule_set(self) -> Optional[dict]:
        query = (
            self.client.table("rule_sets")
            .select("*, rule_steps(*)")
            .eq("is_default", True)
        )
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.execute()
        return response.data[0] if response.data else None

    def get_rule_sets(self) -> list[dict]:
        query = (
            self.client.table("rule_sets")
            .select("*, rule_steps(*)")
        )
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.execute()
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
        query = self.client.table("fb_account_profiles").select("*")
        if self.user_id:
            account_ids = self._get_user_account_ids()
            if not account_ids:
                return []
            query = query.in_("fb_account_id", account_ids)
        response = query.execute()
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
        query = self.client.table("auto_launch_settings").select("*")
        if self.user_id:
            query = query.eq("user_id", self.user_id)
        response = query.limit(1).execute()
        return response.data[0] if response.data else None

    def get_all_auto_launch_settings(self) -> list[dict]:
        """Get auto-launch settings for ALL users. Admin only."""
        response = self.client.table("auto_launch_settings").select("*").execute()
        return response.data

    def update_auto_launch_settings(self, data: dict[str, Any]) -> Optional[dict]:
        current = self.get_auto_launch_settings()
        if not current:
            if self.user_id and "user_id" not in data:
                data["user_id"] = self.user_id
            response = self.client.table("auto_launch_settings").insert(data).execute()
            return response.data[0] if response.data else None
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
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
        if self.user_id:
            account_ids = self._get_user_account_ids()
            if not account_ids:
                return []
            query = query.in_("fb_account_id", account_ids)
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

    def count_campaign_launches(self, campaign_id: str) -> int:
        """Count how many times a campaign was launched (status='launched')."""
        response = (
            self.client.table("auto_launch_queue")
            .select("id", count="exact")
            .eq("campaign_id", campaign_id)
            .eq("status", "launched")
            .execute()
        )
        return response.count or 0

    def clear_old_launch_queue(self, before_date: str) -> None:
        """Delete all queue entries with launch_date before the given date
        (including stale pending items that were never launched)."""
        self.client.table("auto_launch_queue") \
            .delete() \
            .lt("launch_date", before_date) \
            .execute()

    def clear_pending_queue(self) -> None:
        """Delete all pending queue entries (before re-analysis)."""
        query = self.client.table("auto_launch_queue") \
            .delete() \
            .eq("status", "pending")
        if self.user_id:
            account_ids = self._get_user_account_ids()
            if account_ids:
                query = query.in_("fb_account_id", account_ids)
        query.execute()

    # --- Auto-Launch Blacklist ---

    def get_blacklist(self) -> list[dict]:
        query = (
            self.client.table("auto_launch_blacklist")
            .select("*")
            .order("blacklisted_at", desc=True)
        )
        if self.user_id:
            account_ids = self._get_user_account_ids()
            if not account_ids:
                return []
            # Filter via campaign_id → campaigns → fb_account_id
            campaign_ids = self._get_user_campaign_ids(account_ids)
            if not campaign_ids:
                return []
            query = query.in_("campaign_id", campaign_ids)
        return query.execute().data

    def get_blacklisted_campaign_ids(self) -> set[str]:
        query = self.client.table("auto_launch_blacklist").select("campaign_id")
        if self.user_id:
            account_ids = self._get_user_account_ids()
            if not account_ids:
                return set()
            campaign_ids = self._get_user_campaign_ids(account_ids)
            if not campaign_ids:
                return set()
            query = query.in_("campaign_id", campaign_ids)
        response = query.execute()
        return {row["campaign_id"] for row in response.data}

    def _get_user_campaign_ids(self, account_ids: list[str]) -> list[str]:
        """Get campaign IDs belonging to given accounts."""
        response = (
            self.client.table("campaigns")
            .select("id")
            .in_("fb_account_id", account_ids)
            .execute()
        )
        return [row["id"] for row in response.data]

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

    # --- User Settings ---

    def get_user_settings(self, user_id: Optional[str] = None) -> Optional[dict]:
        """Get settings for a specific user."""
        uid = user_id or self.user_id
        if not uid:
            return None
        response = (
            self.client.table("user_settings")
            .select("*")
            .eq("user_id", uid)
            .execute()
        )
        if not response.data:
            return None
        return _decrypt_fields(response.data[0], USER_SETTINGS_ENCRYPTED_FIELDS)

    def update_user_settings(self, data: dict[str, Any], user_id: Optional[str] = None) -> Optional[dict]:
        """Update user settings. Creates if not exists."""
        uid = user_id or self.user_id
        if not uid:
            return None

        encrypted = _encrypt_fields(data, USER_SETTINGS_ENCRYPTED_FIELDS)
        encrypted["updated_at"] = datetime.now(timezone.utc).isoformat()

        existing = (
            self.client.table("user_settings")
            .select("id")
            .eq("user_id", uid)
            .execute()
        )

        if existing.data:
            response = (
                self.client.table("user_settings")
                .update(encrypted)
                .eq("user_id", uid)
                .execute()
            )
        else:
            encrypted["user_id"] = uid
            response = (
                self.client.table("user_settings")
                .insert(encrypted)
                .execute()
            )

        if not response.data:
            return None
        return _decrypt_fields(response.data[0], USER_SETTINGS_ENCRYPTED_FIELDS)

    def get_all_user_settings(self) -> list[dict]:
        """Get settings for ALL users. Admin only, for background tasks."""
        response = self.client.table("user_settings").select("*").execute()
        return [
            _decrypt_fields(row, USER_SETTINGS_ENCRYPTED_FIELDS)
            for row in response.data
        ]

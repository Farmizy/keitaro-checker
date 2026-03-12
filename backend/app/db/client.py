from functools import lru_cache

from supabase import create_client, Client

from app.config import settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Anon client — respects RLS. For user-facing API requests."""
    return create_client(settings.supabase_url, settings.supabase_key)


@lru_cache(maxsize=1)
def get_supabase_admin() -> Client:
    """Service-role client — bypasses RLS. For background tasks only."""
    if not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not set. "
            "Required for background tasks (campaign_checker, auto_launcher)."
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_key: str  # anon key (public, respects RLS)
    supabase_service_role_key: str = ""  # service_role key (bypasses RLS, for background tasks)
    supabase_jwt_secret: str = ""

    # Keitaro (Internal Panel API) — optional, now per-user via user_settings
    keitaro_url: str = ""
    keitaro_login: str = ""
    keitaro_password: str = ""

    # 2KK Panel API — optional, now per-user via user_settings
    panel_api_url: str = "https://fbm.adway.team/api"
    panel_jwt: str = ""

    # Encryption
    encryption_key: str  # Fernet key

    # Telegram (optional) — now per-user via user_settings
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Scheduler
    check_interval_minutes: int = 10

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

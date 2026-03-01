from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_jwt_secret: str

    # Keitaro (Internal Panel API)
    keitaro_url: str  # e.g. https://pro1.trk.dev
    keitaro_login: str
    keitaro_password: str

    # 2KK Panel API
    panel_api_url: str = "https://fbm.adway.team/api"
    panel_jwt: str

    # Encryption
    encryption_key: str  # Fernet key

    # Telegram (optional)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Scheduler
    check_interval_minutes: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

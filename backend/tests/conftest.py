import os

from cryptography.fernet import Fernet

# Must be set before any app module import
_test_fernet_key = Fernet.generate_key().decode()

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-32chars-minimum!!")
os.environ.setdefault("KEITARO_URL", "https://test.trk.dev")
os.environ.setdefault("KEITARO_LOGIN", "test")
os.environ.setdefault("KEITARO_PASSWORD", "test")
os.environ.setdefault("PANEL_JWT", "test-jwt")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)

from app.services.database_service import _encrypt_fields, _decrypt_fields


class TestEncryptDecryptFields:
    def test_encrypt_fields_encrypts_sensitive(self):
        data = {
            "name": "Test Account",
            "access_token": "my-token",
            "cookie": "my-cookie",
            "proxy_password": "my-pass",
        }
        result = _encrypt_fields(data)
        assert result["name"] == "Test Account"
        assert result["access_token"] != "my-token"
        assert result["cookie"] != "my-cookie"
        assert result["proxy_password"] != "my-pass"

    def test_encrypt_decrypt_roundtrip(self):
        data = {
            "name": "Test",
            "access_token": "token123",
            "cookie": "cookie456",
            "proxy_password": "pass789",
        }
        encrypted = _encrypt_fields(data)
        decrypted = _decrypt_fields(encrypted)
        assert decrypted == data

    def test_none_values_not_encrypted(self):
        data = {"access_token": None, "name": "Test"}
        result = _encrypt_fields(data)
        assert result["access_token"] is None

    def test_missing_fields_ignored(self):
        data = {"name": "Test"}
        result = _encrypt_fields(data)
        assert result == {"name": "Test"}

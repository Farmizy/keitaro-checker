import pytest

from app.core.encryption import encrypt, decrypt


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        original = "my-secret-token-12345"
        encrypted = encrypt(original)
        assert encrypted != original
        decrypted = decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_ciphertexts(self):
        value = "same-value"
        enc1 = encrypt(value)
        enc2 = encrypt(value)
        # Fernet uses random IV, so ciphertexts differ
        assert enc1 != enc2
        assert decrypt(enc1) == value
        assert decrypt(enc2) == value

    def test_encrypt_empty_string(self):
        encrypted = encrypt("")
        assert decrypt(encrypted) == ""

    def test_encrypt_unicode(self):
        value = "токен-с-юникодом-🔑"
        encrypted = encrypt(value)
        assert decrypt(encrypted) == value

    def test_decrypt_invalid_raises(self):
        with pytest.raises(Exception):
            decrypt("not-valid-ciphertext")

class BudgetManagerError(Exception):
    """Base exception for Budget Manager."""
    pass


class ExternalAPIError(BudgetManagerError):
    """Error communicating with external API (Keitaro, 2KK Panel)."""
    pass


class EncryptionError(BudgetManagerError):
    """Error encrypting/decrypting data."""
    pass

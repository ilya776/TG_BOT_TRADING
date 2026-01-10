"""Encryption Manager for API Keys.

Uses Fernet symmetric encryption for storing sensitive data like API keys.
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import get_settings

settings = get_settings()


class EncryptionManager:
    """Handles encryption and decryption of sensitive data."""

    def __init__(self, secret_key: str | None = None):
        """Initialize encryption manager.

        Args:
            secret_key: Base secret for key derivation.
                       Uses settings.secret_key if not provided.
        """
        key = secret_key or settings.secret_key
        # Derive a valid Fernet key from the secret
        derived_key = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)
        self._fernet = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string.

        Args:
            plaintext: The string to encrypt.

        Returns:
            Base64-encoded encrypted string.
        """
        encrypted = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt an encrypted string.

        Args:
            ciphertext: The encrypted string.

        Returns:
            Decrypted plaintext string.
        """
        decrypted = self._fernet.decrypt(ciphertext.encode())
        return decrypted.decode()


# Singleton instance
_encryption_manager: EncryptionManager | None = None


def get_encryption_manager() -> EncryptionManager:
    """Get or create the encryption manager singleton."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager

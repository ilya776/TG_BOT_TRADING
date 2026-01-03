"""
Encryption utilities for sensitive data like API keys
"""

import base64
import hashlib
import secrets
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import get_settings


class EncryptionManager:
    """Handles encryption/decryption of sensitive data."""

    def __init__(self, encryption_key: str | None = None):
        """
        Initialize encryption manager.

        Args:
            encryption_key: Fernet key for encryption. If not provided,
                          uses the key from settings.
        """
        settings = get_settings()
        key = encryption_key or settings.encryption_key

        # Ensure key is valid Fernet key format
        if len(key) == 32:
            # If it's a raw 32-byte string, encode it properly
            key = base64.urlsafe_b64encode(key.encode()[:32]).decode()
        elif len(key) != 44:
            # Not a valid Fernet key, derive one from the provided key
            key = self._derive_key(key)

        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def _derive_key(self, password: str, salt: bytes | None = None) -> str:
        """Derive a Fernet key from a password."""
        if salt is None:
            salt = b"whale_copy_trading_salt"  # Static salt for consistency

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key.decode()

    def encrypt(self, data: str) -> str:
        """
        Encrypt a string.

        Args:
            data: Plain text to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not data:
            return ""
        encrypted = self._fernet.encrypt(data.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted_data: Base64-encoded encrypted string

        Returns:
            Decrypted plain text

        Raises:
            ValueError: If decryption fails
        """
        if not encrypted_data:
            return ""
        try:
            decrypted = self._fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except InvalidToken as e:
            raise ValueError("Failed to decrypt data - invalid token") from e

    def encrypt_dict(self, data: dict[str, Any]) -> dict[str, str]:
        """
        Encrypt all string values in a dictionary.

        Args:
            data: Dictionary with string values

        Returns:
            Dictionary with encrypted values
        """
        return {
            key: self.encrypt(str(value)) if value else ""
            for key, value in data.items()
        }

    def decrypt_dict(self, data: dict[str, str]) -> dict[str, str]:
        """
        Decrypt all values in a dictionary.

        Args:
            data: Dictionary with encrypted values

        Returns:
            Dictionary with decrypted values
        """
        return {
            key: self.decrypt(value) if value else ""
            for key, value in data.items()
        }

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key."""
        return Fernet.generate_key().decode()

    @staticmethod
    def hash_data(data: str) -> str:
        """
        Create a SHA256 hash of data (one-way).

        Args:
            data: String to hash

        Returns:
            Hex-encoded hash
        """
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        Generate a cryptographically secure random token.

        Args:
            length: Length of the token in bytes

        Returns:
            URL-safe base64-encoded token
        """
        return secrets.token_urlsafe(length)


# Singleton instance
_encryption_manager: EncryptionManager | None = None


def get_encryption_manager() -> EncryptionManager:
    """Get or create the encryption manager singleton."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager

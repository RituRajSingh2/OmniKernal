"""
Encryption Engine — Symmetric Fernet Encryption

Handles encryption and decryption of sensitive strings like API keys.
Requires OMNIKERNAL_SECRET_KEY in the environment.

BUG 37 fix: When OMNIKERNAL_SECRET_KEY is not set, the engine now persists
a generated dev key to `.dev.key` in the current working directory. This
means that restarting the process will reload the same key rather than
generating a new one each time, preventing silent data loss across restarts.

In strict mode (OMNIKERNAL_STRICT_KEY=1), missing key raises RuntimeError
immediately — use this in production to prevent key-loss incidents.
"""

import os
from pathlib import Path
from cryptography.fernet import Fernet
from loguru import logger

# Dev key is stored here so restarts reuse it instead of generating a new one (BUG 37)
_DEV_KEY_FILE = Path(".dev.key")


def _load_or_create_dev_key() -> str:
    """
    BUG 37 fix: Loads an existing dev key file or creates and persists a new one.
    This ensures a consistent key across process restarts in development.
    """
    if _DEV_KEY_FILE.exists():
        return _DEV_KEY_FILE.read_text().strip()

    new_key = Fernet.generate_key().decode()
    _DEV_KEY_FILE.write_text(new_key)
    return new_key


class EncryptionEngine:
    """Provides secure encryption and decryption."""

    _fernet: "Fernet | None" = None

    @classmethod
    def _get_fernet(cls) -> "Fernet":
        if cls._fernet is None:
            key = os.getenv("OMNIKERNAL_SECRET_KEY")

            if not key:
                # Strict mode: raise immediately (use in production)
                if os.getenv("OMNIKERNAL_STRICT_KEY", "").lower() in ("1", "true", "yes"):
                    raise RuntimeError(
                        "OMNIKERNAL_SECRET_KEY is not set. "
                        "Set the environment variable to a valid Fernet key. "
                        "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                    )

                # BUG 37 fix: persist dev key to .dev.key so restarts reuse the same key
                key = _load_or_create_dev_key()
                os.environ["OMNIKERNAL_SECRET_KEY"] = key
                logger.warning(
                    "OMNIKERNAL_SECRET_KEY not set! Using a persisted development key from '.dev.key'. "
                    "This key is process-stable but NOT suitable for production. "
                    "Set OMNIKERNAL_STRICT_KEY=1 to raise an error instead."
                )

            try:
                cls._fernet = Fernet(key.encode() if isinstance(key, str) else key)
            except Exception as e:
                logger.error(f"Failed to initialize Fernet with provided key: {e}")
                raise

        return cls._fernet

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """Encrypts a string and returns the ciphertext as string."""
        if not plaintext:
            return ""
        fernet = cls._get_fernet()
        return fernet.encrypt(plaintext.encode()).decode()

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """Decrypts a ciphertext string back to plaintext."""
        if not ciphertext:
            return ""
        fernet = cls._get_fernet()
        return fernet.decrypt(ciphertext.encode()).decode()

    @classmethod
    def reset(cls) -> None:
        """
        Reset the cached Fernet instance. Useful in tests when the key
        changes (e.g. setting OMNIKERNAL_SECRET_KEY between test cases).
        """
        cls._fernet = None

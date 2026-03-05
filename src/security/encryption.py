"""
Encryption Engine ΓÇö Symmetric Fernet Encryption

Handles encryption and decryption of sensitive strings like API keys.
Requires OMNIKERNAL_SECRET_KEY in the environment.
"""

import os
from cryptography.fernet import Fernet
from loguru import logger

class EncryptionEngine:
    """Provides secure encryption and decryption."""
    
    _fernet = None
    
    @classmethod
    def _get_fernet(cls) -> Fernet:
        if cls._fernet is None:
            # For development, if key is missing, generate a temporary one
            key = os.getenv("OMNIKERNAL_SECRET_KEY")
            if not key:
                logger.warning("OMNIKERNAL_SECRET_KEY not set! Using a temporary development key.")
                key = Fernet.generate_key().decode()
                os.environ["OMNIKERNAL_SECRET_KEY"] = key
                
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

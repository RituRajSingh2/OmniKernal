"""
ProfileMetadata — Encrypted metadata.json Read/Write

Stores profile configuration and session data. Sensitive fields
are encrypted at rest using the EncryptionEngine from Phase 2.5.
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional
from src.core.logger import core_logger
from src.security.encryption import EncryptionEngine

PROFILES_DIR = "profiles"

# Fields that are encrypted at rest
SENSITIVE_FIELDS = {"session_data"}


class ProfileMetadata:
    """
    Manages encrypted metadata.json files for each profile.

    Schema:
        name: str           — Profile display name
        platform: str       — Target platform (e.g. 'whatsapp')
        created_at: str     — ISO timestamp
        headless: bool      — Whether this profile runs headless
        session_data: str   — Encrypted session/auth data (encrypted at rest)
    """

    def __init__(self, profiles_dir: str = PROFILES_DIR):
        self.profiles_dir = profiles_dir
        self.logger = core_logger.bind(subsystem="profile_metadata")
        
        if not os.getenv("OMNIKERNAL_SECRET_KEY"):
            self.logger.warning(
                "OMNIKERNAL_SECRET_KEY not set. Profiles will use a temporary DEVELOPMENT key. "
                "Data encrypted today will be lost on the next server restart if context is lost."
            )

    def _metadata_path(self, profile_name: str) -> str:
        return os.path.join(self.profiles_dir, profile_name, "metadata.json")

    def save(self, profile_name: str, data: dict) -> None:
        """
        Saves profile metadata, encrypting sensitive fields.

        Args:
            profile_name: Profile directory name.
            data: Metadata dict to persist.
        """
        encrypted_data = dict(data)

        for field in SENSITIVE_FIELDS:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = EncryptionEngine.encrypt(str(encrypted_data[field]))

        meta_path = self._metadata_path(profile_name)
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(encrypted_data, f, indent=2, default=str)

        self.logger.debug(f"Metadata saved for '{profile_name}'.")

    def load(self, profile_name: str) -> Optional[dict]:
        """
        Loads and decrypts profile metadata.

        Returns:
            Decrypted metadata dict, or None if not found.
        """
        meta_path = self._metadata_path(profile_name)
        if not os.path.exists(meta_path):
            return None

        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Decrypt sensitive fields
        for field in SENSITIVE_FIELDS:
            if field in data and data[field]:
                try:
                    data[field] = EncryptionEngine.decrypt(data[field])
                except Exception:
                    self.logger.warning(f"Failed to decrypt '{field}' for profile '{profile_name}'.")
                    data[field] = None

        return data

    def create_default(self, profile_name: str, platform: str) -> dict:
        """Creates and saves a default metadata.json for a new profile."""
        data = {
            "name": profile_name,
            "platform": platform,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "headless": False,
            "session_data": "",
        }
        self.save(profile_name, data)
        return data

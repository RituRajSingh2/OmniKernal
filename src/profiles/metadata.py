"""
ProfileMetadata — Encrypted metadata.json Read/Write

Stores profile configuration and session data. Sensitive fields
are encrypted at rest using the EncryptionEngine from Phase 2.5.

BUG 11 note: save() always expects PLAINTEXT values for SENSITIVE_FIELDS.
Never pass a dict obtained from load() back into save() without going through
the full decrypt → modify → save cycle, or session_data will be double-encrypted.
The safe pattern is:
    data = metadata.load(name)      # returns decrypted values
    data["session_data"] = new_val  # update with plaintext
    metadata.save(name, data)       # re-encrypts cleanly
"""

import json
import os
from datetime import UTC, datetime
from typing import Any

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

    BUG 11: save() encrypts sensitive fields unconditionally if they are non-empty.
    Callers MUST ensure they only pass plaintext values for SENSITIVE_FIELDS.
    Passing an already-encrypted value results in double-encryption (silent corruption).
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

    def save(self, profile_name: str, data: dict[str, Any]) -> None:
        """
        Saves profile metadata, encrypting sensitive fields.

        Args:
            profile_name: Profile directory name.
            data: Metadata dict to persist. Values for SENSITIVE_FIELDS must be
                  plaintext strings — they will be encrypted by this method.

        BUG 11 warning: do NOT pass a dict that was previously returned by load()
        without first decrypting-then-plaintext-setting the sensitive fields.
        load() decrypts automatically, so the round-trip is safe as long as you
        don't re-load without modifying (which would pass plaintext to save() again,
        which is correct). The dangerous case is keeping raw ciphertext in a dict
        and passing it here — that will double-encrypt.
        """
        encrypted_data: dict[str, Any] = dict(data)

        for field in SENSITIVE_FIELDS:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = EncryptionEngine.encrypt(str(encrypted_data[field]))

        meta_path = self._metadata_path(profile_name)
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(encrypted_data, f, indent=2, default=str)

        self.logger.debug(f"Metadata saved for '{profile_name}'.")

    def load(self, profile_name: str, decrypt: bool = True) -> dict[str, Any] | None:
        """
        Loads and potentially decrypts profile metadata.

        Args:
            profile_name: Profile directory name.
            decrypt:      BUG 80 fix: set to False to skip decryption;
                          useful for lists/checks when secret key is unknown.

        BUG 51 fix: previously, a failed decryption silently set the field to
        None. If the caller then did `save(load(name))`, the original ciphertext
        would be overwritten with None, permanently destroying the secret.

        Now we raise on decryption failure. The caller must decide how to handle
        a key-mismatch scenario (e.g. prompt user or deactivate) rather than
        silently losing data.

        Returns:
            Decrypted metadata dict, or None if the file doesn't exist.

        Raises:
            RuntimeError: If a sensitive field cannot be decrypted (key mismatch).
        """
        meta_path = self._metadata_path(profile_name)
        if not os.path.exists(meta_path):
            return None

        with open(meta_path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        # Decrypt sensitive fields
        if decrypt:
            for field in SENSITIVE_FIELDS:
                if field in data and data[field]:
                    try:
                        data[field] = EncryptionEngine.decrypt(data[field])
                    except Exception as e:
                        self.logger.error(
                            f"Cannot decrypt '{field}' for profile '{profile_name}'. "
                            f"Key mismatch or corrupted data. Original ciphertext preserved."
                        )
                        raise RuntimeError(
                            f"Profile '{profile_name}': failed to decrypt '{field}'. "
                            "Ensure OMNIKERNAL_SECRET_KEY matches the key used when this profile was created."
                        ) from e

        return data

    def create_default(self, profile_name: str, platform: str) -> dict[str, Any]:
        """Creates and saves a default metadata.json for a new profile."""
        data = {
            "name": profile_name,
            "platform": platform,
            "created_at": datetime.now(UTC).isoformat(),
            "headless": False,
            "session_data": "",
        }
        self.save(profile_name, data)
        return data

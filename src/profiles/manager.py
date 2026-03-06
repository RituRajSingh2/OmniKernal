"""
ProfileManager — Profile Lifecycle Controller

Orchestrates creation, activation, and deactivation of isolated
WhatsApp profiles. Enforces headless mode when ≥2 profiles are active.
"""

import os
from typing import Optional
from src.core.logger import core_logger
from src.profiles.lock import ProfileLock
from src.profiles.metadata import ProfileMetadata

PROFILES_DIR = "profiles"


class ProfileManager:
    """
    Manages the full profile lifecycle.

    Lifecycle: Create → Activate (lock + headless check) → Use → Deactivate (unlock)

    Rules:
      - Each profile gets its own isolated directory under profiles/<name>/
      - PID-based locks prevent duplicate activations
      - If ≥2 profiles are active, headless mode is automatically enforced
    """

    def __init__(self, profiles_dir: str = PROFILES_DIR):
        self.profiles_dir = profiles_dir
        self.lock = ProfileLock(profiles_dir)
        self.metadata = ProfileMetadata(profiles_dir)
        self.logger = core_logger.bind(subsystem="profile_manager")

    def create(self, name: str, platform: str = "whatsapp") -> dict:
        """
        Creates a new profile directory and initializes metadata.

        Args:
            name: Unique profile name.
            platform: Target platform identifier.

        Returns:
            The initial metadata dict.

        Raises:
            FileExistsError: If the profile already exists.
        """
        profile_dir = os.path.join(self.profiles_dir, name)
        if os.path.exists(profile_dir):
            raise FileExistsError(f"Profile '{name}' already exists.")

        os.makedirs(profile_dir, exist_ok=True)
        data = self.metadata.create_default(name, platform)
        self.logger.info(f"Profile created: {name} (platform={platform})")
        return data

    def activate(self, name: str) -> dict:
        """
        Activates a profile: acquires lock and enforces headless if needed.

        Returns:
            Updated metadata dict with headless flag set appropriately.

        Raises:
            FileNotFoundError: If the profile doesn't exist.
            RuntimeError: If the profile is already locked.
        """
        profile_dir = os.path.join(self.profiles_dir, name)
        if not os.path.isdir(profile_dir):
            raise FileNotFoundError(f"Profile '{name}' does not exist.")

        # Acquire PID lock
        self.lock.acquire(name)

        # Check headless enforcement
        meta = self.metadata.load(name) or {}
        force_headless = self.should_force_headless()

        if force_headless:
            meta["headless"] = True
            self.metadata.save(name, meta)
            self.logger.warning(
                f"Multiple profiles active ({self.lock.get_active_count()}). "
                f"Forcing headless mode for '{name}'."
            )

        self.logger.info(f"Profile activated: {name} (headless={meta.get('headless', False)})")
        return meta

    def deactivate(self, name: str) -> None:
        """
        Deactivates a profile: releases lock and resets headless flag.

        Args:
            name: Profile name to deactivate.
        """
        self.lock.release(name)

        meta = self.metadata.load(name)
        if meta:
            meta["headless"] = False
            self.metadata.save(name, meta)

        self.logger.info(f"Profile deactivated: {name}")

    def list_profiles(self) -> list[str]:
        """Returns a list of all profile directory names."""
        if not os.path.isdir(self.profiles_dir):
            return []
        return [
            d for d in os.listdir(self.profiles_dir)
            if os.path.isdir(os.path.join(self.profiles_dir, d))
            and d != ".gitkeep"
        ]

    def should_force_headless(self) -> bool:
        """Returns True if ≥2 profiles are currently active (locked)."""
        return self.lock.get_active_count() >= 2

    def get_profile(self, name: str) -> Optional[dict]:
        """Returns metadata for a profile, or None if it doesn't exist."""
        return self.metadata.load(name)

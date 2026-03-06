"""
Tests for Phase 5 — Profile Management.
"""

import os
import pytest
from src.profiles.lock import ProfileLock
from src.profiles.metadata import ProfileMetadata
from src.profiles.manager import ProfileManager


class TestProfileLock:
    """Tests for PID-based lock file enforcement."""

    def test_acquire_and_release(self, tmp_path):
        lock = ProfileLock(str(tmp_path))
        profile_dir = tmp_path / "test_profile"
        profile_dir.mkdir()

        lock.acquire("test_profile")
        assert lock.is_locked("test_profile") is True

        lock.release("test_profile")
        assert lock.is_locked("test_profile") is False

    def test_duplicate_lock_raises(self, tmp_path):
        lock = ProfileLock(str(tmp_path))
        profile_dir = tmp_path / "test_profile"
        profile_dir.mkdir()

        lock.acquire("test_profile")

        with pytest.raises(RuntimeError, match="already locked"):
            lock.acquire("test_profile")

        lock.release("test_profile")

    def test_stale_lock_cleared(self, tmp_path):
        lock = ProfileLock(str(tmp_path))
        profile_dir = tmp_path / "test_profile"
        profile_dir.mkdir()

        # Write a fake PID that's definitely dead
        lock_file = profile_dir / "lock.pid"
        lock_file.write_text("999999999")

        # Should detect stale lock and allow re-acquisition
        assert lock.is_locked("test_profile") is False
        lock.acquire("test_profile")
        assert lock.is_locked("test_profile") is True
        lock.release("test_profile")

    def test_active_count(self, tmp_path):
        lock = ProfileLock(str(tmp_path))

        for name in ["profile_a", "profile_b", "profile_c"]:
            (tmp_path / name).mkdir()

        lock.acquire("profile_a")
        assert lock.get_active_count() == 1

        lock.acquire("profile_b")
        assert lock.get_active_count() == 2

        lock.release("profile_a")
        assert lock.get_active_count() == 1

        lock.release("profile_b")
        assert lock.get_active_count() == 0


class TestProfileMetadata:
    """Tests for encrypted metadata read/write."""

    def test_save_and_load(self, tmp_path):
        meta = ProfileMetadata(str(tmp_path))
        profile_dir = tmp_path / "test_profile"
        profile_dir.mkdir()

        data = {
            "name": "test_profile",
            "platform": "whatsapp",
            "headless": False,
            "session_data": "super_secret_token_12345",
        }
        meta.save("test_profile", data)

        # Verify the raw file has encrypted session_data
        import json
        raw = json.loads((profile_dir / "metadata.json").read_text())
        assert raw["session_data"] != "super_secret_token_12345"  # Encrypted!

        # Verify decrypted load
        loaded = meta.load("test_profile")
        assert loaded["name"] == "test_profile"
        assert loaded["session_data"] == "super_secret_token_12345"  # Decrypted!

    def test_empty_session_data(self, tmp_path):
        meta = ProfileMetadata(str(tmp_path))
        (tmp_path / "test_profile").mkdir()

        data = meta.create_default("test_profile", "whatsapp")
        loaded = meta.load("test_profile")
        assert loaded["platform"] == "whatsapp"


class TestProfileManager:
    """Tests for the full profile lifecycle."""

    def test_create_and_list(self, tmp_path):
        mgr = ProfileManager(str(tmp_path))

        mgr.create("alice", "whatsapp")
        mgr.create("bob", "whatsapp")

        profiles = mgr.list_profiles()
        assert "alice" in profiles
        assert "bob" in profiles

    def test_duplicate_create_raises(self, tmp_path):
        mgr = ProfileManager(str(tmp_path))
        mgr.create("alice")

        with pytest.raises(FileExistsError):
            mgr.create("alice")

    def test_activate_deactivate(self, tmp_path):
        mgr = ProfileManager(str(tmp_path))
        mgr.create("alice")

        meta = mgr.activate("alice")
        assert mgr.lock.is_locked("alice") is True

        mgr.deactivate("alice")
        assert mgr.lock.is_locked("alice") is False

    def test_headless_enforced_with_two_profiles(self, tmp_path):
        mgr = ProfileManager(str(tmp_path))
        mgr.create("alice")
        mgr.create("bob")

        # Activate first — no headless needed
        meta_a = mgr.activate("alice")
        assert mgr.should_force_headless() is False

        # Activate second — headless enforced (>= 2 active)
        meta_b = mgr.activate("bob")
        assert mgr.should_force_headless() is True
        assert meta_b["headless"] is True

        # Deactivate one — back to single
        mgr.deactivate("alice")
        assert mgr.should_force_headless() is False

        mgr.deactivate("bob")

    def test_activate_nonexistent_raises(self, tmp_path):
        mgr = ProfileManager(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            mgr.activate("ghost_profile")

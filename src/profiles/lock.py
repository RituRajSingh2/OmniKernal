"""
ProfileLock — PID-Based Lock File Enforcement

Prevents two processes from activating the same profile simultaneously.
Stale locks (from crashed processes) are automatically detected and cleared.
"""

import os
import json
from src.core.logger import core_logger

PROFILES_DIR = "profiles"


class ProfileLock:
    """
    PID-based lock file manager for profile isolation.

    Each active profile writes its PID to profiles/<name>/lock.pid.
    Stale locks from dead processes are automatically cleaned up.
    """

    def __init__(self, profiles_dir: str = PROFILES_DIR):
        self.profiles_dir = profiles_dir
        self.logger = core_logger.bind(subsystem="profile_lock")

    def _lock_path(self, profile_name: str) -> str:
        return os.path.join(self.profiles_dir, profile_name, "lock.pid")

    def _pid_is_alive(self, pid: int) -> bool:
        """Check if a process with the given PID is still running."""
        try:
            # On Windows, os.kill with signal 0 checks existence
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def acquire(self, profile_name: str) -> None:
        """
        Acquires the lock for a profile by writing the current PID.
        Uses atomic file creation (O_CREAT | O_EXCL) to prevent race conditions.

        Raises:
            RuntimeError: If the lock is already held by a live process.
        """
        lock_file = self._lock_path(profile_name)
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)

        # 1. Check for existing lock
        if os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as f:
                    content = f.read().strip()
                    existing_pid = int(content) if content else None
            except (ValueError, OSError):
                existing_pid = None

            if existing_pid and self._pid_is_alive(existing_pid):
                raise RuntimeError(
                    f"Profile '{profile_name}' is already locked by PID {existing_pid}."
                )
            else:
                self.logger.warning(
                    f"Clearing stale lock for '{profile_name}'."
                )
                self.release(profile_name)

        # 2. Atomic creation
        try:
            # os.O_EXCL ensures the call fails if the file already exists
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w') as f:
                f.write(str(os.getpid()))
        except FileExistsError:
            # Rare race condition: someone else created it between our exists check and open
            raise RuntimeError(
                f"Profile '{profile_name}' was locked by another process during acquisition."
            )

        self.logger.info(f"Lock acquired for '{profile_name}' (PID {os.getpid()}).")

    def release(self, profile_name: str) -> None:
        """Releases the lock for a profile."""
        lock_file = self._lock_path(profile_name)
        if os.path.exists(lock_file):
            os.remove(lock_file)
            self.logger.info(f"Lock released for '{profile_name}'.")

    def is_locked(self, profile_name: str) -> bool:
        """Returns True if the profile is locked by a live process."""
        lock_file = self._lock_path(profile_name)
        if not os.path.exists(lock_file):
            return False

        with open(lock_file, "r") as f:
            try:
                pid = int(f.read().strip())
            except ValueError:
                return False

        if self._pid_is_alive(pid):
            return True

        # Stale lock — clean it up
        self.release(profile_name)
        return False

    def get_active_count(self) -> int:
        """Counts how many profiles currently hold valid (live PID) locks."""
        if not os.path.isdir(self.profiles_dir):
            return 0

        count = 0
        for name in os.listdir(self.profiles_dir):
            profile_dir = os.path.join(self.profiles_dir, name)
            if os.path.isdir(profile_dir) and self.is_locked(name):
                count += 1
        return count

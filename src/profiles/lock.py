"""
ProfileLock — PID-Based Lock File Enforcement

Prevents two processes from activating the same profile simultaneously.
Stale locks (from crashed processes) are automatically detected and cleared.

BUG 31 fix: Eliminated the TOCTOU race between the exists-check and atomic
file creation. acquire() now uses a try-first-then-cleanup loop: it attempts
os.O_EXCL creation immediately; only on FileExistsError does it inspect the
existing PID and potentially clean up a stale lock, then retries once.
"""

import os
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
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def acquire(self, profile_name: str) -> None:
        """
        Acquires the lock for a profile by writing the current PID.

        BUG 31 fix: Uses a try-first-then-cleanup strategy to eliminate the
        TOCTOU race between the exists check and atomic creation.

        Strategy:
          1. Attempt O_EXCL atomic create immediately (fastest, no race).
          2. On FileExistsError, read the existing PID.
          3. If PID is alive → raise RuntimeError (lock genuinely held).
          4. If PID is dead → remove stale file and retry once (max 2 attempts).
          5. If second attempt also fails → another live process got there first.

        Raises:
            RuntimeError: If the lock is held by a live process.
        """
        lock_file = self._lock_path(profile_name)
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)

        for attempt in range(2):
            try:
                # Atomic: fails immediately if the file already exists
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w") as f:
                    f.write(str(os.getpid()))
                self.logger.info(f"Lock acquired for '{profile_name}' (PID {os.getpid()}).")
                return

            except FileExistsError:
                if attempt == 1:
                    # Second attempt failed — a live process just acquired the lock
                    raise RuntimeError(
                        f"Profile '{profile_name}' was locked by another process during acquisition."
                    )

                # First attempt: inspect the existing lock file
                try:
                    with open(lock_file, "r") as f:
                        content = f.read().strip()
                    existing_pid = int(content) if content else None
                except (OSError, ValueError):
                    existing_pid = None

                if existing_pid and self._pid_is_alive(existing_pid):
                    raise RuntimeError(
                        f"Profile '{profile_name}' is already locked by PID {existing_pid}."
                    )

                # Stale lock — remove it and loop back to retry O_EXCL
                self.logger.warning(f"Clearing stale lock for '{profile_name}'.")
                try:
                    os.remove(lock_file)
                except FileNotFoundError:
                    pass  # another process already removed it — fine, O_EXCL will decide

    def release(self, profile_name: str) -> None:
        """Releases the lock for a profile, but only if owned by the current process.

        BUG 50 fix: Previously deleted unconditionally. Now checks that the PID
        in the lock file matches os.getpid() before deleting, preventing a
        process from releasing a lock held by a different live process.
        """
        lock_file = self._lock_path(profile_name)
        if not os.path.exists(lock_file):
            return

        try:
            with open(lock_file, "r") as f:
                content = f.read().strip()
            file_pid = int(content) if content else None
        except (OSError, ValueError):
            file_pid = None

        if file_pid is not None and file_pid != os.getpid():
            self.logger.warning(
                f"Skipping lock release for '{profile_name}': "
                f"lock is held by PID {file_pid}, not current PID {os.getpid()}."
            )
            return

        try:
            os.remove(lock_file)
            self.logger.info(f"Lock released for '{profile_name}'.")
        except FileNotFoundError:
            pass  # Already removed — fine

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
        # BUG 61 fix: needs to bypass the ownership check if we're cleaning up
        # after a dead process that wasn't us.
        try:
            os.remove(lock_file)
            self.logger.info(f"Cleared stale lock for '{profile_name}'.")
        except FileNotFoundError:
            pass
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

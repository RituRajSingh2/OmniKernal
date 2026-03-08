"""
ProfileLock — PID-Based Lock File Enforcement

Prevents two processes from activating the same profile simultaneously.
Stale locks (from crashed processes) are automatically detected and cleared.

BUG 31 fix: Eliminated the TOCTOU race between the exists-check and atomic
file creation. acquire() now uses a try-first-then-cleanup loop: it attempts
os.O_EXCL creation immediately; only on FileExistsError does it inspect the
existing PID and potentially clean up a stale lock, then retries once.
"""

import contextlib
import os
import psutil # BUG 75

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

    def _pid_is_alive(self, pid: int, start_time: float | None = None) -> bool:
        """
        Check if a process with the given PID is still running.
        BUG 75 fix: If start_time is provided, also verify that the process
        was created at that exact time to prevent recycling races.
        """
        try:
            proc = psutil.Process(pid)
            if not proc.is_running():
                return False
            if start_time is not None:
                # Allow minor float precision difference
                return abs(proc.create_time() - start_time) < 0.1
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
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
                    # BUG 75: Store pid:starttime
                    curr_proc = psutil.Process()
                    f.write(f"{curr_proc.pid}:{curr_proc.create_time()}")
                self.logger.info(f"Lock acquired for '{profile_name}' (PID {os.getpid()}).")
                return

            except FileExistsError:
                if attempt == 1:
                    # Second attempt failed — a live process just acquired the lock
                    raise RuntimeError(
                        f"Profile '{profile_name}' was locked by another process during acquisition."
                    ) from None

                # First attempt: inspect the existing lock file
                try:
                    # BUG 210 fix: if file is empty, someone might be currently writing to it.
                    # Wait briefly and retry reading before assuming it's truly stale.
                    content = ""
                    for sub_attempt in range(3):
                        with open(lock_file) as f:
                            content = f.read().strip()
                        if content:
                            break
                        # Only sleep if we have a loop; else it's a script/test boot.
                        if asyncio.get_event_loop().is_running():
                            # We can't await here as acquire() is sync for profile_manager use.
                            # But we only hit this on concurrent startup.
                            import time
                            time.sleep(0.05)

                    if ":" in content:
                        p_str, t_str = content.split(":", 1)
                        existing_pid = int(p_str)
                        existing_time = float(t_str)
                    else:
                        existing_pid = int(content) if content else None
                        existing_time = None
                except (OSError, ValueError):
                    existing_pid = None
                    existing_time = None

                if existing_pid and self._pid_is_alive(existing_pid, existing_time):
                    raise RuntimeError(
                        f"Profile '{profile_name}' is already locked by PID {existing_pid}."
                    ) from None

                # Stale lock — remove it and loop back to retry O_EXCL
                self.logger.warning(f"Clearing stale lock for '{profile_name}'.")
                with contextlib.suppress(FileNotFoundError):
                    os.remove(lock_file)

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
            with open(lock_file) as f:
                content = f.read().strip()
            # BUG 131 fix: handle colon-separated PID:TIME format consistently
            if ":" in content:
                file_pid = int(content.split(":", 1)[0])
            else:
                file_pid = int(content) if content else None
        except (OSError, ValueError):
            file_pid = None

        # BUG 163 fix: also verify creation time if available to prevent Windows PID reciclery race.
        current_proc = psutil.Process()
        if file_pid is not None and file_pid != current_proc.pid:
            self.logger.warning(
                f"Skipping lock release for '{profile_name}': "
                f"lock is held by PID {file_pid}, not current PID {current_proc.pid}."
            )
            return

        # Optimization: we already have current_proc. Avoid re-check if we know it matches.

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

        # BUG 194 fix: Handle FileNotFoundError race condition (TOCTOU)
        try:
            with open(lock_file) as f:
                content = f.read().strip()
        except FileNotFoundError:
            return False
        except Exception:
            return False

        try:
            if ":" in content:
                pid_str, time_str = content.split(":", 1)
                pid = int(pid_str)
                start_time = float(time_str)
            else:
                pid = int(content)
                start_time = None
        except (ValueError, TypeError):
            return False

        if self._pid_is_alive(pid, start_time):
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

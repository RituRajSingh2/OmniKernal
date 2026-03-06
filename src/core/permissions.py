"""
PermissionValidator — Access Control Logic

Checks if a user has sufficient roles or permissions to execute a command.

BUG 39 fix: Added check_role() classmethod that operates on a pre-resolved
role string rather than a User object. This lets the dispatcher pass the
effective_role (after OMNIKERNAL_ADMINS elevation) without needing to mutate
the frozen User dataclass.
"""

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.core.contracts.user import User


class PermissionValidator:
    """
    Validates execution rights.
    """

    @classmethod
    def check_permission(cls, user: "User", required_role: str = "user") -> bool:
        """
        Simple role check using the user's original frozen role field.
        'admin' role can do everything. 'user' role can do 'user' level commands.

        Note: This compares user.role (the frozen original field). For admin-
        elevated users resolved via OMNIKERNAL_ADMINS, use check_role() with
        the effective_role string so that elevation is actually enforced.
        """
        if user.role == "admin":
            return True
        return user.role == required_role

    @classmethod
    def check_role(cls, effective_role: str, required_role: str = "user") -> bool:
        """
        BUG 39 fix: Checks a pre-resolved effective role string against the
        required role. Use this when the caller has already resolved the
        effective role (e.g. after OMNIKERNAL_ADMINS elevation).

        Args:
            effective_role: The resolved role string (e.g. 'admin' or 'user').
            required_role:  Minimum role required to execute. Default 'user'.

        Returns:
            True if effective_role grants the required access level.
        """
        if effective_role == "admin":
            return True
        return effective_role == required_role

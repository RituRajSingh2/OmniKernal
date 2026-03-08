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
    Checks if a user has sufficient roles or permissions to execute a command.
    """

    ROLE_LEVELS = {
        "any": 0,
        "user": 10,
        "mod": 50,
        "admin": 100
    }

    @classmethod
    def check_role(cls, effective_role: str, required_role: str = "user") -> bool:
        """
        Hierarchical RBAC check (BUG 74 fix).
        Checks if the user's role level is >= the required role level.

        Args:
            effective_role: The resolved role string (e.g. 'admin', 'mod', 'user').
            required_role:  Minimum role required (default 'user').

        Returns:
            True if user role meets or exceeds required level.
        """
        # BUG 165 fix: Fail-closed on unrecognized roles.
        # If 'required_role' is misspelled, default to level 100 (admin).
        # This prevents typo-ing 'adm1n' and accidentally opening it to 'user'.
        # BUG 165 + BUG 173 fix: Fail-closed on unrecognized roles.
        # Maps common synonyms to internal levels to prevent accidental lockout.
        LEVEL_SYNONYMS = {"owner": "admin", "superuser": "admin", "administrator": "admin"}
        # BUG 281: normalize to lowercase for robust dictionary lookup
        mapped_user = LEVEL_SYNONYMS.get(effective_role.lower(), effective_role.lower())
        mapped_req = LEVEL_SYNONYMS.get(required_role.lower(), required_role.lower())

        user_lvl = cls.ROLE_LEVELS.get(mapped_user, 0)
        req_lvl = cls.ROLE_LEVELS.get(mapped_req, 100) # Default to 100 (admin)

        return user_lvl >= req_lvl

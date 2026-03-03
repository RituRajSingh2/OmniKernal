"""
PermissionValidator ΓÇö Access Control Logic

Checks if a user has sufficient roles or permissions to execute a command.
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
        Simple role check for Phase 1.
        'admin' role can do everything. 'user' role can do 'user' level commands.
        """
        if user.role == "admin":
            return True
        
        return user.role == required_role

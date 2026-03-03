"""Test stubs for User contract — construction and immutability."""
import pytest
from dataclasses import FrozenInstanceError
from src.core.contracts.user import User


def test_user_construction():
    u = User(id="123", display_name="Alice", platform="whatsapp")
    assert u.id == "123"
    assert u.display_name == "Alice"
    assert u.platform == "whatsapp"
    assert u.role == "user"  # default


def test_user_admin_role():
    u = User(id="1", display_name="Admin", platform="whatsapp", role="admin")
    assert u.is_admin() is True


def test_user_default_not_admin():
    u = User(id="2", display_name="Bob", platform="whatsapp")
    assert u.is_admin() is False


def test_user_is_immutable():
    u = User(id="3", display_name="Carol", platform="whatsapp")
    with pytest.raises(FrozenInstanceError):
        u.display_name = "Changed"  # type: ignore[misc]

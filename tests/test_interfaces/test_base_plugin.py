"""Test stubs for BasePlugin ABC — structural correctness only."""
import pytest
from src.core.interfaces.base_plugin import BasePlugin


def test_base_plugin_is_abstract():
    """BasePlugin cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BasePlugin()  # type: ignore[abstract]


def test_base_plugin_missing_properties_raises():
    """A subclass missing abstract properties raises TypeError."""
    class IncompletePlugin(BasePlugin):
        pass

    with pytest.raises(TypeError):
        IncompletePlugin()


def test_base_plugin_full_concrete_instantiates():
    """A fully implemented subclass instantiates correctly."""
    class ConcretePlugin(BasePlugin):
        @property
        def name(self) -> str: return "test_plugin"
        @property
        def version(self) -> str: return "1.0.0"
        @property
        def platform(self) -> list[str]: return ["any"]
        @property
        def description(self) -> str: return "A test plugin"

    p = ConcretePlugin()
    assert p.name == "test_plugin"
    assert p.version == "1.0.0"
    assert p.platform == ["any"]

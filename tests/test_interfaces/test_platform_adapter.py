"""Test stubs for PlatformAdapter ABC — structural correctness only."""
import pytest
from src.core.interfaces.platform_adapter import PlatformAdapter


def test_platform_adapter_is_abstract():
    """PlatformAdapter cannot be instantiated directly — it's an ABC."""
    with pytest.raises(TypeError):
        PlatformAdapter()  # type: ignore[abstract]


def test_platform_adapter_concrete_missing_methods_raises():
    """A subclass missing abstract methods raises TypeError on instantiation."""
    class IncompleteAdapter(PlatformAdapter):
        pass  # missing all abstract methods

    with pytest.raises(TypeError):
        IncompleteAdapter()


def test_platform_adapter_full_concrete_instantiates():
    """A fully implemented subclass instantiates without error."""
    class ConcreteAdapter(PlatformAdapter):
        async def connect(self) -> None: ...
        async def fetch_new_messages(self): return []
        async def send_message(self, to: str, content: str) -> None: ...
        async def disconnect(self) -> None: ...

        @property
        def platform_name(self) -> str:
            return "mock"

    adapter = ConcreteAdapter()
    assert adapter.platform_name == "mock"

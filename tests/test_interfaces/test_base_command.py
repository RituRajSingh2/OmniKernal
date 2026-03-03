"""Test stubs for BaseCommand ABC — structural correctness only."""
import pytest
from src.core.interfaces.base_command import BaseCommand


def test_base_command_is_abstract():
    """BaseCommand cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseCommand()  # type: ignore[abstract]


def test_base_command_missing_methods_raises():
    """A subclass missing abstract methods raises TypeError."""
    class IncompleteCommand(BaseCommand):
        pass

    with pytest.raises(TypeError):
        IncompleteCommand()


def test_base_command_full_concrete_instantiates():
    """A fully implemented subclass instantiates correctly."""
    from src.core.contracts import CommandContext, CommandResult

    class ConcreteCommand(BaseCommand):
        @property
        def command_name(self) -> str: return "echo"
        @property
        def pattern(self) -> str: return "!echo <text>"
        async def run(self, args, ctx) -> CommandResult:
            return CommandResult.success(reply=args.get("text"))

    cmd = ConcreteCommand()
    assert cmd.command_name == "echo"
    assert cmd.pattern == "!echo <text>"

from src.core.contracts.command_result import CommandResult
from src.core.contracts.command_context import CommandContext

async def run(args: dict, ctx: CommandContext) -> CommandResult:
    """The echo handler logic."""
    text = args.get("text", "...")
    return CommandResult.success(reply=f"[OK] Echo: {text}")

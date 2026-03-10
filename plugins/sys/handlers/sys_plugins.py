from src.core.contracts.command_context import CommandContext
from src.core.contracts.command_result import CommandResult
from src.database.session import AsyncDatabase
from src.database.repository import OmniRepository


async def run(args: dict[str, str], ctx: CommandContext) -> CommandResult:
    """
    Handler for "!sys plugins"
    Returns a list of all loaded plugins from the DB registry to test end-to-end connectivity.
    """
    async with AsyncDatabase().session() as session:
        repo = OmniRepository(session)
        plugins = await repo.get_all_plugins()
        
    if not plugins:
        return CommandResult.success("No plugins are currently registered in the system.")
        
    lines = ["⚙️ *OmniKernal Plugin Registry*"]
    for p in plugins:
        status = "✅" if p.is_active else "❌"
        lines.append(f"{status} {p.name} (v{p.version})")
        
    reply = "\n".join(lines)
    return CommandResult.success(reply=reply)

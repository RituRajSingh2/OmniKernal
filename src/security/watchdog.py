"""
ApiWatchdog ΓÇö Reliability & Fail-Fast Mechanism

Tracks external API call success rates. If an API fails repeatedly,
it quarantines the API to prevent cascading blocks and wastes.
"""

from typing import TYPE_CHECKING
from src.core.logger import core_logger

if TYPE_CHECKING:
    from src.database.repository import OmniRepository

class ApiWatchdog:
    """
    Monitor for external API health.
    Methods should be called before and after plugin API interactions.
    """
    
    def __init__(self, repo: "OmniRepository"):
        self.repo = repo
        self.logger = core_logger.bind(subsystem="watchdog")

    async def record_failure(self, api_url: str, tool_id: int, error_msg: str):
        """Records a failure and quarantines if threshold reached."""
        self.logger.warning(f"API Failure recorded for {api_url}: {error_msg}")
        is_dead = await self.repo.increment_error(api_url, tool_id=tool_id, error_msg=error_msg)
        if is_dead:
            self.logger.error(f"API {api_url} is now QUARANTINED due to consecutive failures.")

    async def record_success(self, api_url: str):
        """Records a success, resetting any degraded state."""
        await self.repo.reset_api_health(api_url)
        self.logger.debug(f"API {api_url} success recorded. Health reset.")

    async def is_dead(self, api_url: str) -> bool:
        """Checks if an API is currently quarantined."""
        return not await self.repo.is_api_healthy(api_url)

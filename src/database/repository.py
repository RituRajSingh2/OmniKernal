"""
Database Repository — Encapsulated SQL Logic

Isolates all SQLAlchemy queries. Ensures parameterized inputs and
consistent error handling.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload  # BUG 70

from .models import ApiHealth, DeadApi, ExecutionLog, Plugin, RoutingRule, Tool, ToolRequirement


class OmniRepository:
    """
    Main repository for all OmniKernal data access.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Plugin & Tool Registry ---

    async def register_plugin(self, name: str, version: str, author_name: str | None = None, description: str | None = None) -> None:
        """
        Registers or updates a plugin entry.

        BUG 52 fix: session.merge() with a new Plugin instance always resets
        is_active to True (the model default), silently re-enabling manually
        disabled plugins on every restart. We now load the existing record and
        only update mutable metadata fields, preserving is_active.
        """
        existing = await self.session.get(Plugin, name)
        if existing:
            existing.version = version
            existing.author = author_name
            existing.description = description
            # is_active is intentionally NOT touched — preserve disabled state
        else:
            plugin = Plugin(
                name=name,
                version=version,
                author=author_name,
                description=description,
                is_active=True,
            )
            self.session.add(plugin)
        await self.session.commit()

    async def register_tool(
        self,
        command_name: str,
        pattern: str,
        handler_path: str,
        plugin_name: str,
        description: str | None = None,
        required_role: str = "user"  # BUG 71
    ) -> None:
        """Registers or updates a tool entry."""
        existing = await self.get_tool_by_command(command_name)
        if existing:
            # BUG 3 fix: also update plugin_name to avoid stale association
            existing.pattern = pattern
            existing.handler_path = handler_path
            existing.description = description
            existing.plugin_name = plugin_name   # was missing
            existing.required_role = required_role # BUG 71
            await self.session.flush()           # make intent explicit
        else:
            tool = Tool(
                command_name=command_name,
                pattern=pattern,
                handler_path=handler_path,
                plugin_name=plugin_name,
                description=description,
                required_role=required_role # BUG 71
            )
            self.session.add(tool)

        await self.session.commit()

    async def get_tool_by_command(self, command_name: str) -> Tool | None:
        """Looks up a tool by its !command trigger."""
        result = await self.session.execute(
            select(Tool).where(Tool.command_name == command_name)
        )
        return result.scalar_one_or_none()

    async def get_tool_by_id(self, tool_id: int) -> Tool | None:
        """Looks up a tool by its integer primary key. BUG 30 support."""
        return await self.session.get(Tool, tool_id)

    async def get_all_tools(self) -> Sequence[Tool]:
        """Returns all registered tools."""
        result = await self.session.execute(select(Tool))
        return result.scalars().all()

    async def get_all_routing_rules(self) -> Sequence[RoutingRule]:
        """
        Returns all routing rules ordered by priority (highest first).
        BUG 30 fix: used by CommandRouter for regex-based dispatch.
        BUG 70 fix: uses joinedload to fetch Tool metadata in one query.
        """
        result = await self.session.execute(
            select(RoutingRule)
            .options(joinedload(RoutingRule.tool))
            .order_by(RoutingRule.priority.desc())
        )
        return result.scalars().all()

    async def set_plugin_inactive(self, name: str) -> None:
        """Marks a plugin as inactive. BUG 13."""
        from sqlalchemy import update
        await self.session.execute(
            update(Plugin).where(Plugin.name == name).values(is_active=False)
        )
        await self.session.commit()

    async def deactivate_missing_plugins(self, active_names: list[str]) -> None:
        """Marks plugins NOT in the list as inactive. BUG 240."""
        from sqlalchemy import update
        await self.session.execute(
            update(Plugin)
            .where(Plugin.name.notin_(active_names))
            .values(is_active=False)
        )
        await self.session.commit()

    # --- Execution Logging ---

    async def log_execution(
        self,
        user_id: str,
        platform: str,
        command_name: str,
        raw_input: str,
        success: bool,
        response_time_ms: float | None = None,
        error_reason: str | None = None
    ) -> None:
        """Adds a record to the audit trail. BUG 183 sanitized."""
        # Sanitize error reason specifically for audit logs to prevent injection (B183)
        from src.security.sanitizer import CommandSanitizer
        safe_reason = CommandSanitizer.sanitize(error_reason) if error_reason else None

        log = ExecutionLog(
            user_id=user_id,
            platform=platform,
            command_name=command_name,
            raw_input=raw_input,
            success=success,
            response_time_ms=response_time_ms,
            error_reason=safe_reason
        )
        self.session.add(log)
        await self.session.commit()

    # --- API Health Watchdog ---

    async def increment_error(self, url: str, tool_id: int | None, error_msg: str) -> bool:
        """
        Increments failure count. Quarantines and logs to DeadApi if threshold reached.
        Returns True if the API is now quarantined as a result of this error.
        """
        # BUG 220 + BUG 274 fix: use atomic SQL update and fetch fresh data.
        # execute(update) does not refresh loaded objects; we must SELECT again.
        from sqlalchemy import select
        await self.session.execute(
            update(ApiHealth)
            .where(ApiHealth.url == url)
            .values(consecutive_failures=ApiHealth.consecutive_failures + 1, last_failure=datetime.now(UTC))
        )
        
        # Fresh fetch to avoid identity-map stale counter values
        result = await self.session.execute(select(ApiHealth).where(ApiHealth.url == url))
        health = result.scalar_one_or_none()
        
        if not health:
            health = ApiHealth(url=url, consecutive_failures=1, last_failure=datetime.now(UTC), error_threshold=3)
            self.session.add(health)
            await self.session.flush()

        is_newly_dead = False
        if health.consecutive_failures >= health.error_threshold and not health.is_quarantined:
            health.is_quarantined = True
            is_newly_dead = True

            dead_api = DeadApi(
                api_url=url,
                tool_id=tool_id,
                error_count=health.consecutive_failures,
                kill_reason=error_msg
            )
            self.session.add(dead_api)

        await self.session.commit()
        return is_newly_dead

    async def reset_api_health(self, url: str) -> None:
        """
        Resets consecutive failure count and clears quarantine after a successful call.
        Called by ApiWatchdog.record_success().

        Note: This intentionally clears is_quarantined on success — the watchdog
        recovery flow is: 3 failures → dead, then 1 success → healthy again.
        For a stricter "manual reactivation only" workflow, use reactivate_api() instead.
        """
        health = await self.session.get(ApiHealth, url)
        if not health:
            health = ApiHealth(url=url, consecutive_failures=0, error_threshold=3, is_quarantined=False)
            self.session.add(health)

        health.consecutive_failures = 0
        health.last_success = datetime.now(UTC)
        health.is_quarantined = False   # watchdog recovery path: one success clears quarantine

        await self.session.commit()

    async def update_api_health(self, url: str, success: bool) -> None:
        """
        Convenience method: increment_error on failure, reset on success.
        Useful for callers that don't need the fine-grained split.
        """
        if success:
            await self.reset_api_health(url)
        else:
            # BUG 54 fix: use None instead of 0 for tool_id to avoid FK issues
            await self.increment_error(url, tool_id=None, error_msg="health update")

    async def reactivate_api(self, url: str) -> None:
        """
        Manually reactivates a quarantined API.
        Must be called explicitly by an operator after the underlying issue is fixed.
        """
        health = await self.session.get(ApiHealth, url)
        if health:
            health.consecutive_failures = 0
            health.is_quarantined = False
            health.last_success = datetime.now(UTC)
            await self.session.commit()

        # Also mark corresponding DeadApi row as reactivated
        # BUG 56: Removed redundant local imports
        await self.session.execute(
            update(DeadApi)
            .where(DeadApi.api_url == url, DeadApi.reactivated == False)  # noqa: E712
            .values(reactivated=True)
        )
        await self.session.commit()

    async def register_tool_requirement(self, tool_id: int, api_key: str, service: str = "default") -> None:
        """Saves or updates an encrypted API key for a tool. BUG 279 (UPSERT)."""
        service = service or "default"
        # Since this is a specialized repo method, we handle the select/merge
        result = await self.session.execute(
            select(ToolRequirement).where(
                ToolRequirement.tool_id == tool_id, 
                ToolRequirement.service == service
            )
        )
        req = result.scalar_one_or_none()
        if req:
            req.api_key_value = api_key
        else:
            req = ToolRequirement(tool_id=tool_id, service=service, api_key_value=api_key)
            self.session.add(req)
        await self.session.commit()

    async def get_api_key(self, tool_id: int, service: str = "default") -> str | None:
        """Fetches the encrypted API key for a tool (optional service name). BUG 181."""
        result = await self.session.execute(
            select(ToolRequirement).where(
                ToolRequirement.tool_id == tool_id, 
                ToolRequirement.service == (service or "default")
            )
        )
        req = result.scalar_one_or_none()
        return req.api_key_value if req else None

    async def is_api_healthy(self, url: str) -> bool:
        """Returns False if the API is quarantined."""
        health = await self.session.get(ApiHealth, url)
        if health:
            return not health.is_quarantined
        return True

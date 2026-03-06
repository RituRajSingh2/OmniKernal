"""
PluginEngine — Declarative Plugin Discovery & Loading

Scans the plugins/ directory, validates manifest.json and commands.yaml,
and registers findings into the OmniRepository.

BUG 21 fix: Now uses PluginManifest.from_dict() to parse and validate
manifests formally, instead of raw dict access.

BUG 34 fix: Now enforces min_core_version — plugins that require a higher
core version than the currently running OMNIKERNAL_VERSION are rejected
at load time with a clear log message.

BUG 57 fix: Warns when a command_name from one plugin would overwrite a
command_name already registered by a different plugin, so admins know which
plugin "won" the collision.

BUG 58 fix: PluginEngine now accepts the running platform_name and skips
(or marks inactive) plugins that don't support the current platform. This
prevents polluting the DB with tools that can never execute.
"""

import os
import json
import yaml
from typing import TYPE_CHECKING, Optional
from src.core.logger import core_logger
from src.core.contracts.plugin_manifest import PluginManifest   # BUG 21

if TYPE_CHECKING:
    from src.database.repository import OmniRepository

# BUG 34 fix: single source of truth for the current Core version
OMNIKERNAL_VERSION: str = "0.1.0"


def _version_tuple(v: str) -> tuple[int, ...]:
    """Parse a semver-like string into a comparable tuple, e.g. '1.2.3' → (1, 2, 3)."""
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)


class PluginEngine:
    """
    Main orchestrator for Phase 3 plugin lifecycle.

    Args:
        repo:          The OmniRepository to register plugins/tools into.
        plugins_dir:   Directory to scan for plugin folders.
        platform_name: BUG 58 — running platform identifier (e.g. 'whatsapp').
                       Plugins that don't list this platform (or 'any') are skipped.
                       Pass None to disable platform filtering (all plugins load).
    """

    def __init__(
        self,
        repo: "OmniRepository",
        plugins_dir: str = "plugins",
        platform_name: Optional[str] = None,
    ):
        self.repo = repo
        self.plugins_dir = plugins_dir
        self.platform_name = platform_name   # BUG 58
        self.logger = core_logger.bind(subsystem="plugin_engine")

    async def discover_and_load(self):
        """
        Scans the plugins directory and registers valid plugins in the DB.
        """
        self.logger.info(f"Scanning for plugins in: {self.plugins_dir}")

        if not os.path.exists(self.plugins_dir):
            self.logger.warning(f"Plugins directory not found: {self.plugins_dir}")
            return

        for plugin_folder in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, plugin_folder)

            if not os.path.isdir(plugin_path):
                continue

            await self._load_plugin(plugin_folder, plugin_path)

    async def _load_plugin(self, folder_name: str, path: str):
        """Loads a single plugin folder."""
        manifest_path = os.path.join(path, "manifest.json")
        commands_path = os.path.join(path, "commands.yaml")

        if not os.path.exists(manifest_path):
            self.logger.debug(f"Skipping {folder_name}: No manifest.json found.")
            return

        manifest: Optional[PluginManifest] = None

        try:
            # 1. Load & Validate Manifest using formal contract (BUG 21 fix)
            with open(manifest_path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            manifest = PluginManifest.from_dict(raw)   # validates name/version

            # BUG 34 fix: enforce min_core_version before registration
            if manifest.min_core_version:
                required = _version_tuple(manifest.min_core_version)
                running  = _version_tuple(OMNIKERNAL_VERSION)
                if required > running:
                    self.logger.warning(
                        f"Plugin '{manifest.name}' requires core v{manifest.min_core_version} "
                        f"but running v{OMNIKERNAL_VERSION}. Skipping."
                    )
                    return

            # BUG 58 fix: skip plugins incompatible with the active platform
            if self.platform_name and not manifest.supports_platform(self.platform_name):
                self.logger.info(
                    f"Plugin '{manifest.name}' does not support platform "
                    f"'{self.platform_name}' (supports {manifest.platform}). Skipping."
                )
                return

            # 2. Register Plugin in DB
            await self.repo.register_plugin(
                name=manifest.name,
                version=manifest.version,
                author_name=manifest.author,
                description=manifest.description
            )

            # 3. Load & Process commands.yaml
            if os.path.exists(commands_path):
                with open(commands_path, "r", encoding="utf-8") as f:
                    cmd_cfg = yaml.safe_load(f)

                commands = cmd_cfg.get("commands", {})
                for cmd_name, cmd_info in commands.items():
                    # BUG 57 fix: warn if an existing tool with this name belongs
                    # to a different plugin (silent overwrite is a footgun).
                    existing = await self.repo.get_tool_by_command(cmd_name)
                    if existing and existing.plugin_name != manifest.name:
                        self.logger.warning(
                            f"Command name conflict: '{cmd_name}' is already registered "
                            f"by plugin '{existing.plugin_name}'. "
                            f"Plugin '{manifest.name}' will overwrite it."
                        )

                    await self.repo.register_tool(
                        command_name=cmd_name,
                        pattern=cmd_info.get("pattern"),
                        handler_path=cmd_info.get("handler"),
                        plugin_name=manifest.name,
                        description=cmd_info.get("description")
                    )

            self.logger.info(
                f"Loaded plugin: {manifest}"  # uses PluginManifest.__repr__
            )

        except Exception as e:
            self.logger.error(f"Failed to load plugin '{folder_name}': {e}")
            # BUG 13: mark plugin inactive in DB if partially registered
            if manifest is not None:
                try:
                    await self.repo.set_plugin_inactive(manifest.name)
                    self.logger.warning(
                        f"Plugin '{manifest.name}' marked inactive due to load failure."
                    )
                except Exception as inner:
                    self.logger.error(
                        f"Could not mark plugin '{manifest.name}' inactive: {inner}"
                    )

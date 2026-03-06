"""
PluginEngine — Declarative Plugin Discovery & Loading

Scans the plugins/ directory, validates manifest.json and commands.yaml,
and registers findings into the OmniRepository.
"""

import os
import json
import yaml
from typing import TYPE_CHECKING, Optional
from src.core.logger import core_logger

if TYPE_CHECKING:
    from src.database.repository import OmniRepository

class PluginEngine:
    """
    Main orchestrator for Phase 3 plugin lifecycle.
    """

    def __init__(self, repo: "OmniRepository", plugins_dir: str = "plugins"):
        self.repo = repo
        self.plugins_dir = plugins_dir
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

        name: Optional[str] = None  # track for degraded-status fallback

        try:
            # 1. Load & Validate Manifest
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            name = manifest.get("name")
            version = manifest.get("version")
            if not name or not version:
                raise ValueError("Manifest missing 'name' or 'version'")

            # BUG 6 fix: support both 'platform' (spec key) and the legacy
            # 'supported_platforms' key that was used in early manifests.
            # Normalise to 'platform' going forward.
            platform = manifest.get("platform") or manifest.get("supported_platforms") or ["any"]

            # 2. Register Plugin in DB
            await self.repo.register_plugin(
                name=name,
                version=version,
                author_name=manifest.get("author"),
                description=manifest.get("description")
            )

            # 3. Load & Process commands.yaml
            if os.path.exists(commands_path):
                with open(commands_path, "r", encoding="utf-8") as f:
                    cmd_cfg = yaml.safe_load(f)

                commands = cmd_cfg.get("commands", {})
                for cmd_name, cmd_info in commands.items():
                    await self.repo.register_tool(
                        command_name=cmd_name,
                        pattern=cmd_info.get("pattern"),
                        handler_path=cmd_info.get("handler"),
                        plugin_name=name,
                        description=cmd_info.get("description")
                    )

            self.logger.info(f"Successfully loaded plugin: {name} (v{version}) platforms={platform}")

        except Exception as e:
            self.logger.error(f"Failed to load plugin '{folder_name}': {e}")
            # BUG 13 fix: mark the plugin as inactive in DB if it was registered
            # before the failure occurred, so dispatching returns a clear "degraded"
            # signal instead of a silent "no route found".
            if name:
                try:
                    await self.repo.set_plugin_inactive(name)
                    self.logger.warning(
                        f"Plugin '{name}' marked inactive in DB due to load failure."
                    )
                except Exception as inner:
                    self.logger.error(f"Could not mark plugin '{name}' inactive: {inner}")

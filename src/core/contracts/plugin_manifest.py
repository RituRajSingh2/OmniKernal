"""
PluginManifest — Frozen Dataclass Contract

Represents the parsed contents of a plugin's manifest.json file.
Built by the PluginLoader (Phase 3) when scanning the plugins/ directory.
Used by the Core to register plugins in the DB and to validate
compatibility before loading.

Invariant: The Core reads manifest.json — it never imports plugin Python
files just to discover metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PluginManifest:
    """
    Parsed plugin identity from manifest.json.

    Attributes:
        name:             Unique plugin identifier. Must match folder name.
        version:          Semantic version string (e.g. '1.0.0').
        author:           Plugin author name or handle.
        description:      Human-readable description.
        platform:         List of supported platforms (e.g. ['whatsapp', 'any']).
        min_core_version: Minimum OmniKernal version required (e.g. '0.1.0').
                          Optional — older manifests may omit this field.
    """

    name: str
    version: str
    author: str
    description: str
    platform: list[str]
    # BUG 21 fix: made Optional so existing manifests without this key still load
    min_core_version: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest:
        """
        Constructs a PluginManifest from a parsed manifest.json dictionary.
        Supports both 'platform' and the legacy 'supported_platforms' key.

        Args:
            data: Raw dict from json.load(manifest.json).

        Returns:
            A validated, immutable PluginManifest instance.

        Raises:
            ValueError: If required fields (name, version) are missing.
        """
        name = data.get("name")
        version = data.get("version")
        if not name:
            raise ValueError("Plugin manifest missing required field: 'name'")
        if not version:
            raise ValueError("Plugin manifest missing required field: 'version'")

        # Normalise platform key (BUG 148 fix: robust list coercion)
        platform_raw = data.get("platform") or data.get("supported_platforms") or ["any"]
        if isinstance(platform_raw, str):
            platform = [platform_raw]
        elif isinstance(platform_raw, list):
            platform = [str(p) for p in platform_raw]
        else:
            platform = ["any"]

        return cls(
            name=name,
            version=version,
            author=data.get("author", "unknown"),
            description=data.get("description", ""),
            platform=platform,
            min_core_version=data.get("min_core_version"),
        )

    def supports_platform(self, platform_name: str) -> bool:
        """Return True if this plugin supports the given platform or 'any'."""
        return "any" in self.platform or platform_name in self.platform

    def __repr__(self) -> str:
        return (
            f"PluginManifest(name={self.name!r}, version={self.version!r}, "
            f"author={self.author!r}, platforms={self.platform!r})"
        )

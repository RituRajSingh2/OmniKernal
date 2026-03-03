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

from dataclasses import dataclass, field


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
    """

    name: str
    version: str
    author: str
    description: str
    platform: list[str]
    min_core_version: str

    def supports_platform(self, platform_name: str) -> bool:
        """Return True if this plugin supports the given platform or 'any'."""
        return "any" in self.platform or platform_name in self.platform

    def __repr__(self) -> str:
        return (
            f"PluginManifest(name={self.name!r}, version={self.version!r}, "
            f"author={self.author!r}, platforms={self.platform!r})"
        )

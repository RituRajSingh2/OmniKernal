"""
BasePlugin — Abstract Base Class

Defines the identity contract every plugin must expose.
The Core reads these properties to register the plugin in the DB.

Invariant: The Core never imports a plugin's Python handler files
to discover commands. Discovery is manifest/YAML-only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """
    Plugin identity contract.

    Every plugin folder that wishes to be recognised by the Core
    must provide a class satisfying this interface — though in practice
    Phase 3 uses manifest.json + commands.yaml for discovery (YAML-first).
    This ABC provides a programmatic identity surface for tooling and tests.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique plugin identifier.

        Must match the folder name under plugins/ and the 'name'
        field in manifest.json. Example: 'echo', 'ytplugin'.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """
        Semantic version string.

        Example: '1.0.0'. Must match manifest.json 'version'.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def platform(self) -> list[str]:
        """
        Platforms this plugin supports.

        Example: ['whatsapp', 'any'].
        The Core uses this to filter plugins per active adapter.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable plugin description.

        Example: 'Echo back the input text'.
        """
        raise NotImplementedError

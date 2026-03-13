"""
AdapterLoader — Dynamic Adapter Pack Discovery & Loading

Discovers adapter packs from the adapter_packs/ directory,
validates their descriptor and class, and returns a ready-to-use
PlatformAdapter instance.
"""

import importlib
import os
from typing import cast

from src.adapters.validator import AdapterValidator
from src.core.interfaces.platform_adapter import PlatformAdapter
from src.core.logger import core_logger


class AdapterLoader:
    """
    Discovers and loads adapter packs from the adapter_packs/ directory.

    Usage:
        loader = AdapterLoader()
        adapter = loader.load("console_mock")
        # adapter is now a PlatformAdapter instance ready for Core
    """

    def __init__(self, packs_dir: str = "adapter_packs"):
        self.packs_dir = packs_dir
        self.validator = AdapterValidator()
        self.logger = core_logger.bind(subsystem="adapter_loader")

    def load(self, pack_name: str, **kwargs) -> PlatformAdapter:
        """
        Loads an adapter pack by name.

        Steps:
          1. Reads adapter_packs/<pack_name>/adapter.yaml
          2. Validates the descriptor schema
          3. Dynamically imports the entry_class
          4. Validates ABC compliance
          5. Returns an instance with optional kwargs

        Args:
            pack_name: Name of the adapter pack folder.
            **kwargs: Arguments to pass to the adapter class constructor.

        Returns:
            A PlatformAdapter instance ready for Core.
        """
        # BUG 117 fix: sanitize pack_name to prevent directory traversal
        # Only allow alphanumeric and underscore characters.
        import re
        if not re.fullmatch(r"[a-zA-Z0-9_]+", pack_name):
            raise ValueError(f"Invalid pack name: '{pack_name}'. Only alphanumeric/underscore allowed.")

        pack_path = os.path.join(self.packs_dir, pack_name)

        if not os.path.isdir(pack_path):
            raise FileNotFoundError(f"Adapter pack not found: {pack_path}")

        yaml_path = os.path.join(pack_path, "adapter.yaml")
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Missing adapter.yaml in: {pack_path}")

        # 1. Validate descriptor
        descriptor = self.validator.validate_descriptor(yaml_path)

        # 2. Resolve entry_class from descriptor
        entry_class_path = descriptor["entry_class"]  # e.g. "adapter.ConsoleMockAdapter"
        module_path, class_name = entry_class_path.rsplit(".", 1)

        # Build the full import path: adapter_packs.<pack_name>.<module_path>
        full_module_path = f"adapter_packs.{pack_name}.{module_path}"

        self.logger.info(f"Loading adapter: {descriptor['name']} from {full_module_path}.{class_name}")

        # 3. Dynamic import
        try:
            module = importlib.import_module(full_module_path)
            cls = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(
                f"Failed to import entry class '{entry_class_path}' from pack '{pack_name}': {e}"
            ) from e

        # 4. Validate ABC compliance
        self.validator.validate_class(cls)

        # 5. Instantiate and return
        instance = cast(PlatformAdapter, cls(**kwargs))
        self.logger.info(f"Adapter loaded: {instance.platform_name} (v{descriptor['version']})")
        return instance

    def list_packs(self) -> list[str]:
        """Lists all available adapter pack names."""
        if not os.path.isdir(self.packs_dir):
            return []
        return [
            d for d in os.listdir(self.packs_dir)
            if os.path.isdir(os.path.join(self.packs_dir, d))
            and os.path.exists(os.path.join(self.packs_dir, d, "adapter.yaml"))
        ]

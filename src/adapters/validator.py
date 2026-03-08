"""
AdapterValidator — Schema & ABC Compliance Checker

Validates adapter pack descriptors (adapter.yaml) and ensures
the entry class fully implements the PlatformAdapter ABC contract.
"""


import yaml
import inspect  # BUG 76
from typing import Any

from src.core.interfaces.platform_adapter import PlatformAdapter
from src.core.logger import core_logger


class AdapterValidator:
    """
    Validates adapter packs before they are loaded by the Core.

    Two-stage validation:
      1. Descriptor validation — checks adapter.yaml has required fields.
      2. Class validation — checks the loaded class implements all ABC methods.
    """

    REQUIRED_FIELDS = {"name", "platform", "version", "entry_class"}
    REQUIRED_METHODS = {"connect", "fetch_new_messages", "send_message", "disconnect"}
    REQUIRED_PROPERTIES = {"platform_name"}

    def __init__(self) -> None:
        self.logger = core_logger.bind(subsystem="adapter_validator")

    def validate_descriptor(self, yaml_path: str) -> dict[str, Any]:
        """
        Reads and validates an adapter.yaml file.

        Args:
            yaml_path: Absolute path to the adapter.yaml file.

        Returns:
            The parsed descriptor dict if valid.

        Raises:
            ValueError: If required fields are missing or the file is malformed.
        """
        try:
            with open(yaml_path, encoding="utf-8") as f:
                descriptor = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to read adapter descriptor: {e}") from e

        if not isinstance(descriptor, dict):
            raise ValueError(f"Adapter descriptor is not a valid YAML mapping: {yaml_path}")

        missing = self.REQUIRED_FIELDS - set(descriptor.keys())
        if missing:
            raise ValueError(
                f"Adapter descriptor missing required fields: {missing} in {yaml_path}"
            )

        self.logger.debug(f"Descriptor validated: {descriptor.get('name')}")
        return descriptor

    def validate_class(self, cls: type) -> None:
        """
        Verifies that a class fully implements the PlatformAdapter ABC.

        Args:
            cls: The adapter class to validate.

        Raises:
            TypeError: If the class does not subclass PlatformAdapter or is missing methods.
        """
        if not issubclass(cls, PlatformAdapter):
            raise TypeError(
                f"{cls.__name__} must be a subclass of PlatformAdapter"
            )

        # Check required async methods (BUG 76 fix: verify they are coroutines)
        for method_name in self.REQUIRED_METHODS:
            method = getattr(cls, method_name, None)
            if method is None:
                raise TypeError(
                    f"{cls.__name__} is missing required method: {method_name}"
                )
            if not inspect.iscoroutinefunction(method):
                raise TypeError(
                    f"{cls.__name__}.{method_name} must be an 'async def' (coroutine)."
                )

        # Check required properties
        for prop_name in self.REQUIRED_PROPERTIES:
            if not isinstance(getattr(cls, prop_name, None), property):
                raise TypeError(
                    f"{cls.__name__} is missing required property: {prop_name}"
                )

        self.logger.debug(f"Class validated: {cls.__name__}")

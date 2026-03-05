"""
Tests for AdapterValidator and AdapterLoader (Phase 4).
"""

import os
import pytest
import tempfile
import yaml
from src.adapters.validator import AdapterValidator
from src.adapters.loader import AdapterLoader
from src.core.interfaces.platform_adapter import PlatformAdapter


class TestAdapterValidator:
    """Tests for descriptor and class validation."""

    def setup_method(self):
        self.validator = AdapterValidator()

    def test_valid_descriptor(self, tmp_path):
        desc = {
            "name": "test-adapter",
            "platform": "test",
            "version": "1.0.0",
            "entry_class": "adapter.TestAdapter",
        }
        yaml_file = tmp_path / "adapter.yaml"
        yaml_file.write_text(yaml.dump(desc))

        result = self.validator.validate_descriptor(str(yaml_file))
        assert result["name"] == "test-adapter"
        assert result["platform"] == "test"

    def test_missing_fields_rejected(self, tmp_path):
        desc = {"name": "incomplete"}  # missing platform, version, entry_class
        yaml_file = tmp_path / "adapter.yaml"
        yaml_file.write_text(yaml.dump(desc))

        with pytest.raises(ValueError, match="missing required fields"):
            self.validator.validate_descriptor(str(yaml_file))

    def test_malformed_yaml_rejected(self, tmp_path):
        yaml_file = tmp_path / "adapter.yaml"
        yaml_file.write_text("just a plain string, not a mapping")

        with pytest.raises(ValueError, match="not a valid YAML mapping"):
            self.validator.validate_descriptor(str(yaml_file))

    def test_valid_class_passes(self):
        """ConsoleMockAdapter should pass validation."""
        from adapter_packs.console_mock.adapter import ConsoleMockAdapter
        self.validator.validate_class(ConsoleMockAdapter)  # Should not raise

    def test_non_subclass_rejected(self):
        class FakeAdapter:
            pass

        with pytest.raises(TypeError, match="must be a subclass"):
            self.validator.validate_class(FakeAdapter)


class TestAdapterLoader:
    """Tests for dynamic adapter pack loading."""

    def test_load_console_mock(self):
        loader = AdapterLoader()
        adapter = loader.load("console_mock")

        assert isinstance(adapter, PlatformAdapter)
        assert adapter.platform_name == "console_mock"

    def test_load_nonexistent_pack_raises(self):
        loader = AdapterLoader()
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent_pack")

    def test_list_packs(self):
        loader = AdapterLoader()
        packs = loader.list_packs()
        assert "console_mock" in packs
        assert "whatsapp_playwright" in packs

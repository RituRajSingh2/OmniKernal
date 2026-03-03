"""
Minimal Plugin Loader ΓÇö Phase 1 & 2 Glue

In Phase 1 and 2, we manually register a mock command to verify the engine loop.
Now uses the OmniRepository for persistence.
"""

class MinimalLoader:
    """
    Glue logic for Phase 2 verification.
    """
    @staticmethod
    async def register_mock_commands(repo):
        """Registers the !echo command into the database."""
        # 1. Register Plugin Metadata
        await repo.register_plugin(
            name="test_plugin",
            version="1.0.0",
            author_name="Initial Setup",
            description="Phase 2 Verification Plugin"
        )
        
        # 2. Register Tool with handler path
        # In a real setup, this path must be importable.
        await repo.register_tool(
            command_name="echo",
            pattern="!echo <text>",
            handler_path="smoke_test.mock_echo_handler",
            plugin_name="test_plugin",
            description="Basic echo command"
        )

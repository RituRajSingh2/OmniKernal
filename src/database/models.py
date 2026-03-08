"""
Database Models ΓÇö SQLAlchemy Declarative Schema

Defines the tables for the Microkernel registry, execution logging,
and security watchdog (API health).
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

class Plugin(Base):
    """
    Registry for installed/discovered plugins.
    Primary source: manifest.json
    """
    __tablename__ = "plugins"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    version: Mapped[str] = mapped_column(String(20))
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    tools: Mapped[list["Tool"]] = relationship(back_populates="plugin", cascade="all, delete-orphan")

class Tool(Base):
    """
    Registry for individual command handlers.
    Primary source: commands.yaml
    """
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command_name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    pattern: Mapped[str] = mapped_column(String(255))
    handler_path: Mapped[str] = mapped_column(String(255)) # e.g. "plugins.echo.handlers.echo"
    plugin_name: Mapped[str] = mapped_column(ForeignKey("plugins.name", ondelete="CASCADE"))
    required_role: Mapped[str] = mapped_column(String(20), default="user") # BUG 71

    # Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    plugin: Mapped["Plugin"] = relationship(back_populates="tools")

class RoutingRule(Base):
    """
    Custom routing overrides (Phase 3).
    Allows mapping a custom regex to a tool.
    """
    __tablename__ = "routing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    regex_pattern: Mapped[str] = mapped_column(String(255), unique=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    tool: Mapped["Tool"] = relationship() # BUG 70

class ExecutionLog(Base):
    """
    Audit trail for every command execution.
    """
    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    user_id: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(50))
    command_name: Mapped[str] = mapped_column(String(50))
    raw_input: Mapped[str] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean)
    response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)  # BUG 33 fix
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

class ApiHealth(Base):
    """
    Health tracking for external API endpoints (Dead API Watchdog).
    """
    __tablename__ = "api_health"

    # BUG 127 fix: use Text for URLs to prevent length limitations
    url: Mapped[str] = mapped_column(Text, primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_success: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_quarantined: Mapped[bool] = mapped_column(Boolean, default=False)
    error_threshold: Mapped[int] = mapped_column(Integer, default=3)

class DeadApi(Base):
    """
    History and logging of quarantined APIs.
    """
    __tablename__ = "dead_apis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_url: Mapped[str] = mapped_column(Text, index=True) # BUG 127
    tool_id: Mapped[int | None] = mapped_column(ForeignKey("tools.id", ondelete="SET NULL"), nullable=True) # BUG 125
    error_count: Mapped[int] = mapped_column(Integer)
    killed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    kill_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reactivated: Mapped[bool] = mapped_column(Boolean, default=False)

class ToolRequirement(Base):
    """
    Stores encrypted API keys for tools.
    """
    __tablename__ = "tool_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id", ondelete="CASCADE"), index=True)
    service: Mapped[str] = mapped_column(String(50), default="default", index=True) # BUG 181
    api_key_value: Mapped[str] = mapped_column(Text) # Stored ENCRYPTED

    # BUG 181: allow one key per service per tool
    __table_args__ = (
        UniqueConstraint("tool_id", "service", name="uq_tool_service"),
    )

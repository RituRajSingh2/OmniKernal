"""
Database Models ΓÇö SQLAlchemy Declarative Schema

Defines the tables for the Microkernel registry, execution logging,
and security watchdog (API health).
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Integer, JSON, ForeignKey, Text
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
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    plugin_name: Mapped[str] = mapped_column(ForeignKey("plugins.name"))
    
    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id"))
    priority: Mapped[int] = mapped_column(Integer, default=0)

class ExecutionLog(Base):
    """
    Audit trail for every command execution.
    """
    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    user_id: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(50))
    command_name: Mapped[str] = mapped_column(String(50))
    raw_input: Mapped[str] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean)
    response_time_ms: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    error_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class ApiHealth(Base):
    """
    Health tracking for external API endpoints (Dead API Watchdog).
    """
    __tablename__ = "api_health"

    url: Mapped[str] = mapped_column(String(255), primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_success: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_failure: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_quarantined: Mapped[bool] = mapped_column(Boolean, default=False)
    error_threshold: Mapped[int] = mapped_column(Integer, default=3)

class DeadApi(Base):
    """
    History and logging of quarantined APIs.
    """
    __tablename__ = "dead_apis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_url: Mapped[str] = mapped_column(String(255), index=True)
    tool_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tools.id"), nullable=True)
    error_count: Mapped[int] = mapped_column(Integer)
    killed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    kill_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reactivated: Mapped[bool] = mapped_column(Boolean, default=False)

class ToolRequirement(Base):
    """
    Stores encrypted API keys for tools.
    """
    __tablename__ = "tool_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id"), unique=True)
    api_key_value: Mapped[str] = mapped_column(Text) # Stored ENCRYPTED

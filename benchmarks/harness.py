"""
Benchmark Harness — Shared test infrastructure for Phase 7.

Provides a reusable engine boot, message injection, and timing utilities
for all benchmark scripts.
"""

import asyncio
import time
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from src.database.session import async_session_factory, init_db
from src.database.repository import OmniRepository
from src.adapters.loader import AdapterLoader
from src.core.engine import OmniKernal


RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


async def build_engine(mode: str = "self", profile_name: str = "bench") -> tuple[OmniKernal, Any]:
    """
    Boots a real OmniKernal engine with the console_mock adapter.
    Returns (engine, adapter) without starting the poll loop.
    """
    await init_db()
    loader = AdapterLoader()
    adapter = loader.load("console_mock")

    async with async_session_factory() as session:
        repo = OmniRepository(session)
        engine = OmniKernal(
            adapter=adapter,
            repository=repo,
            profile_name=profile_name,
            mode=mode,
        )
        # Partial boot: init DB, profile, plugins, dispatcher — skip poll loop
        from src.core.loader import PluginEngine
        from src.core.dispatcher import EventDispatcher
        from src.profiles.manager import ProfileManager

        await init_db()

        pm = ProfileManager()
        if not pm.get_profile(profile_name):
            pm.create(profile_name, adapter.platform_name)
        pm.activate(profile_name)

        plugin_engine = PluginEngine(repo)
        await plugin_engine.discover_and_load()

        engine.dispatcher = EventDispatcher(repo)
        engine.is_running = True
        engine._repo_session = session  # keep session alive

    return engine, adapter, repo


async def timed(coro: Coroutine) -> tuple[Any, float]:
    """Runs a coroutine and returns (result, elapsed_ms)."""
    start = time.perf_counter()
    result = await coro
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result, elapsed_ms


def save_results(filename: str, data: dict) -> str:
    """Saves benchmark results as JSON to benchmarks/results/."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, filename)
    data["_timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[SAVED] {path}")
    return path

"""
Benchmark: Concurrent Message Processing

Uses asyncio.gather to simulate N concurrent core.process() calls.
Tests: 1, 10, 50 concurrent messages.

Output: benchmarks/results/concurrency.json
"""

import asyncio
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from src.core.contracts.message import Message
from src.core.contracts.user import User
from src.database.session import async_session_factory, init_db
from src.database.repository import OmniRepository
from src.adapters.loader import AdapterLoader
from src.core.loader import PluginEngine
from src.core.dispatcher import EventDispatcher
from src.core.engine import OmniKernal
from src.profiles.manager import ProfileManager
from benchmarks.harness import save_results


def make_message(i: int) -> Message:
    return Message(
        id=f"conc_{i}",
        raw_text="!echo concurrent",
        user=User(id=f"user_{i}", display_name="ConcUser", platform="console", role="admin"),
        timestamp=datetime.now(),
        platform="console",
    )


async def run_single_message(i: int, adapter, dispatcher) -> float:
    """Process one message with its own DB session (safe for concurrent gather)."""
    async with async_session_factory() as session:
        repo = OmniRepository(session)
        msg = make_message(i)
        start = time.perf_counter()
        # Run dispatcher directly to avoid per-engine boot overhead
        clean_text = "!echo concurrent"
        result = await dispatcher.dispatch(clean_text, msg.user)
        if result:
            await repo.log_execution(
                user_id=msg.user.id,
                platform=msg.platform,
                command_name="echo",
                raw_input=msg.raw_text,
                success=result.ok,
                response_time_ms=0,
                error_reason=result.error_reason,
            )
        return (time.perf_counter() - start) * 1000


async def run_concurrent(n: int, adapter, dispatcher) -> dict:
    start = time.perf_counter()
    latencies = await asyncio.gather(
        *[run_single_message(i, adapter, dispatcher) for i in range(n)]
    )
    total_ms = (time.perf_counter() - start) * 1000

    return {
        "n_concurrent": n,
        "total_ms": round(total_ms, 3),
        "per_msg_ms": round(sum(latencies) / n, 3),
        "throughput_msg_per_sec": round(n / (total_ms / 1000), 1),
    }


async def main():
    print("=== Phase 7: Concurrency Benchmark ===")
    await init_db()

    loader = AdapterLoader()
    adapter = loader.load("console_mock")
    results = {}

    # Boot dispatcher once (shared, read-only)
    async with async_session_factory() as session:
        repo = OmniRepository(session)
        plugin_engine = PluginEngine(repo)
        await plugin_engine.discover_and_load()

    # Use a fresh session for dispatcher queries
    async with async_session_factory() as session:
        repo = OmniRepository(session)
        from src.core.dispatcher import EventDispatcher
        dispatcher = EventDispatcher(repo)

        for n in [1, 10, 50]:
            print(f"  Running {n} concurrent messages...")
            data = await run_concurrent(n, adapter, dispatcher)
            results[f"{n}_concurrent"] = data
            print(f"    total={data['total_ms']}ms  per_msg={data['per_msg_ms']}ms  "
                  f"throughput={data['throughput_msg_per_sec']} msg/s")

    save_results("concurrency.json", results)
    print("\n[DONE] Concurrency benchmark complete.")


if __name__ == "__main__":
    asyncio.run(main())

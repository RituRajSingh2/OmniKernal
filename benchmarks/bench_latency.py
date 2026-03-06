"""
Benchmark: Message Processing Latency

Measures end-to-end latency of core.process(msg) at:
  - 1 simulated user  (sequential)
  - 10 simulated users (sequential)
  - 50 simulated users (sequential)

Output: benchmarks/results/latency.json
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
from src.profiles.manager import ProfileManager
from benchmarks.harness import save_results


def make_message(i: int) -> Message:
    return Message(
        id=f"bench_{i}",
        raw_text="!echo benchmark",
        user=User(id=f"user_{i % 10}", display_name="BenchUser", platform="console", role="admin"),
        timestamp=datetime.now(),
        platform="console",
    )


async def run_latency_bench(n_messages: int, repo, engine) -> dict:
    latencies = []

    for i in range(n_messages):
        msg = make_message(i)
        start = time.perf_counter()
        await engine.process(msg)
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(round(elapsed, 3))

    return {
        "n_messages": n_messages,
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
        "mean_ms": round(sum(latencies) / len(latencies), 3),
        "latencies": latencies,
    }


async def main():
    print("=== Phase 7: Latency Benchmark ===")
    await init_db()
    loader = AdapterLoader()
    adapter = loader.load("console_mock")

    results = {}

    async with async_session_factory() as session:
        repo = OmniRepository(session)

        # Boot engine components directly (skip poll loop)
        from src.core.engine import OmniKernal
        engine = OmniKernal(adapter=adapter, repository=repo, profile_name="bench_latency")

        pm = ProfileManager()
        if not pm.get_profile("bench_latency"):
            pm.create("bench_latency", "console")
        pm.activate("bench_latency")

        plugin_engine = PluginEngine(repo)
        await plugin_engine.discover_and_load()
        engine.dispatcher = EventDispatcher(repo)
        engine.is_running = True

        for n in [1, 10, 50]:
            print(f"  Running {n} messages...")
            data = await run_latency_bench(n, repo, engine)
            results[f"{n}_users"] = data
            print(f"    mean={data['mean_ms']}ms  min={data['min_ms']}ms  max={data['max_ms']}ms")

        pm.deactivate("bench_latency")

    save_results("latency.json", results)
    print("\n[DONE] Latency benchmark complete.")


if __name__ == "__main__":
    asyncio.run(main())

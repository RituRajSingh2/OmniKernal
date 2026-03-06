"""
Benchmark: Plugin Load Time

Measures time to run PluginEngine.discover_and_load() in isolation.
Runs 5 iterations to produce stable min/max/mean.

Output: benchmarks/results/plugin_load.json
"""

import asyncio
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.database.session import async_session_factory, init_db
from src.database.repository import OmniRepository
from src.core.loader import PluginEngine
from benchmarks.harness import save_results

ITERATIONS = 5


async def main():
    print("=== Phase 7: Plugin Load Benchmark ===")
    await init_db()
    times = []

    async with async_session_factory() as session:
        repo = OmniRepository(session)

        for i in range(ITERATIONS):
            start = time.perf_counter()
            loader = PluginEngine(repo)
            await loader.discover_and_load()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(round(elapsed, 3))
            print(f"  Iteration {i+1}: {elapsed:.3f}ms")

    results = {
        "iterations": ITERATIONS,
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "mean_ms": round(sum(times) / len(times), 3),
        "times_ms": times,
    }

    save_results("plugin_load.json", results)
    print(f"\n[DONE] Plugin load mean: {results['mean_ms']}ms")


if __name__ == "__main__":
    asyncio.run(main())

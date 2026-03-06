"""
Benchmark: DB Tool Lookup vs Dict Baseline

Measures OmniRepository.get_tool_by_command() (DB query) vs a baseline
in-memory dict lookup over 100 iterations each.

Output: benchmarks/results/db_lookup.json
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

ITERATIONS = 100


async def main():
    print("=== Phase 7: DB Lookup vs Baseline Benchmark ===")
    await init_db()

    async with async_session_factory() as session:
        repo = OmniRepository(session)

        # Ensure plugins and tools are registered
        loader = PluginEngine(repo)
        await loader.discover_and_load()

        # --- DB Lookup ---
        db_times = []
        print(f"  Running {ITERATIONS} DB lookups...")
        for _ in range(ITERATIONS):
            start = time.perf_counter()
            await repo.get_tool_by_command("echo")
            elapsed = (time.perf_counter() - start) * 1000
            db_times.append(round(elapsed, 3))

        # --- Baseline: in-memory dict ---
        baseline_dict = {"echo": {"handler": "handlers.echo.run", "requires_api": False}}
        dict_times = []
        print(f"  Running {ITERATIONS} dict lookups (baseline)...")
        for _ in range(ITERATIONS):
            start = time.perf_counter()
            _ = baseline_dict.get("echo")
            elapsed = (time.perf_counter() - start) * 1000
            dict_times.append(round(elapsed, 4))

    results = {
        "iterations": ITERATIONS,
        "db_lookup": {
            "min_ms": round(min(db_times), 3),
            "max_ms": round(max(db_times), 3),
            "mean_ms": round(sum(db_times) / len(db_times), 3),
        },
        "dict_baseline": {
            "min_ms": round(min(dict_times), 4),
            "max_ms": round(max(dict_times), 4),
            "mean_ms": round(sum(dict_times) / len(dict_times), 4),
        },
        "overhead_factor": round(
            (sum(db_times) / len(db_times)) / max(sum(dict_times) / len(dict_times), 0.0001), 1
        ),
    }

    save_results("db_lookup.json", results)
    print(f"\n  DB mean:   {results['db_lookup']['mean_ms']}ms")
    print(f"  Dict mean: {results['dict_baseline']['mean_ms']}ms")
    print(f"  Overhead:  {results['overhead_factor']}x")
    print("\n[DONE] DB lookup benchmark complete.")


if __name__ == "__main__":
    asyncio.run(main())

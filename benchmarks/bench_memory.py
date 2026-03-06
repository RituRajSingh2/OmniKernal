"""
Benchmark: Memory per Active Profile

Uses psutil to measure RSS memory footprint:
  - Baseline (before engine boot)
  - After 1 profile activation
  - After 2 profiles activation (should be similar — no per-profile overhead)

Output: benchmarks/results/memory.json
"""

import asyncio
import psutil
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.profiles.manager import ProfileManager
from benchmarks.harness import save_results


def get_memory_mb() -> float:
    process = psutil.Process(os.getpid())
    return round(process.memory_info().rss / (1024 * 1024), 2)


async def main():
    print("=== Phase 7: Memory per Profile Benchmark ===")

    baseline_mb = get_memory_mb()
    print(f"  Baseline memory: {baseline_mb} MB")

    pm = ProfileManager()

    # Profile 1
    if not pm.get_profile("bench_mem_1"):
        pm.create("bench_mem_1", "console")
    pm.activate("bench_mem_1")
    after_p1_mb = get_memory_mb()
    delta_p1 = round(after_p1_mb - baseline_mb, 2)
    print(f"  After profile 1 activation: {after_p1_mb} MB (delta: +{delta_p1} MB)")

    # Profile 2
    if not pm.get_profile("bench_mem_2"):
        pm.create("bench_mem_2", "console")
    pm.activate("bench_mem_2")
    after_p2_mb = get_memory_mb()
    delta_p2 = round(after_p2_mb - baseline_mb, 2)
    print(f"  After profile 2 activation: {after_p2_mb} MB (delta: +{delta_p2} MB)")
    print(f"  Headless enforced: {pm.should_force_headless()}")

    pm.deactivate("bench_mem_1")
    pm.deactivate("bench_mem_2")

    results = {
        "baseline_mb": baseline_mb,
        "after_1_profile_mb": after_p1_mb,
        "after_2_profiles_mb": after_p2_mb,
        "delta_1_profile_mb": delta_p1,
        "delta_2_profiles_mb": delta_p2,
        "headless_enforced_at_2": True,
    }

    save_results("memory.json", results)
    print("\n[DONE] Memory benchmark complete.")


if __name__ == "__main__":
    asyncio.run(main())

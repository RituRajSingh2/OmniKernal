"""
run_all.py — Phase 7 Benchmark Orchestrator

Runs all benchmarks sequentially and generates docs/research/report.md.
"""

import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
REPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "research", "report.md")


def load_json(filename: str) -> dict:
    path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def generate_report() -> str:
    latency = load_json("latency.json")
    plugin = load_json("plugin_load.json")
    db = load_json("db_lookup.json")
    memory = load_json("memory.json")
    concurrency = load_json("concurrency.json")
    fault = load_json("fault_isolation.json")

    lines = [
        "# OmniKernal — Phase 7 Performance Research Report\n",
        f"_Generated: {latency.get('_timestamp', 'unknown')}_\n",
        "---\n",
        "## 1. Message Processing Latency\n",
        "| Users | Min (ms) | Max (ms) | Mean (ms) |",
        "|-------|----------|----------|-----------|",
    ]
    for key in ["1_users", "10_users", "50_users"]:
        if key in latency:
            d = latency[key]
            n = key.split("_")[0]
            lines.append(f"| {n} | {d['min_ms']} | {d['max_ms']} | {d['mean_ms']} |")

    lines += [
        "\n## 2. Plugin Load Time\n",
        f"- Iterations: {plugin.get('iterations', 'N/A')}",
        f"- Min: {plugin.get('min_ms', 'N/A')} ms",
        f"- Max: {plugin.get('max_ms', 'N/A')} ms",
        f"- **Mean: {plugin.get('mean_ms', 'N/A')} ms**\n",
        "## 3. DB Tool Lookup vs In-Memory Baseline\n",
        "| Approach | Mean (ms) |",
        "|----------|-----------|",
    ]
    if db:
        lines.append(f"| DB Query | {db.get('db_lookup', {}).get('mean_ms', 'N/A')} |")
        lines.append(f"| Dict Baseline | {db.get('dict_baseline', {}).get('mean_ms', 'N/A')} |")
        lines.append(f"\n- **Overhead factor: {db.get('overhead_factor', 'N/A')}x** (DB vs dict)\n")

    lines += [
        "## 4. Memory per Profile (psutil RSS)\n",
        f"- Baseline: {memory.get('baseline_mb', 'N/A')} MB",
        f"- After 1 profile: {memory.get('after_1_profile_mb', 'N/A')} MB (delta: +{memory.get('delta_1_profile_mb', 'N/A')} MB)",
        f"- After 2 profiles: {memory.get('after_2_profiles_mb', 'N/A')} MB (delta: +{memory.get('delta_2_profiles_mb', 'N/A')} MB)",
        f"- Headless enforced at 2 profiles: {memory.get('headless_enforced_at_2', 'N/A')}\n",
        "## 5. Concurrent Message Throughput\n",
        "| Concurrent | Total (ms) | Per-msg (ms) | Throughput (msg/s) |",
        "|------------|------------|--------------|-------------------|",
    ]
    for key in ["1_concurrent", "10_concurrent", "50_concurrent"]:
        if key in concurrency:
            d = concurrency[key]
            n = key.split("_")[0]
            lines.append(f"| {n} | {d['total_ms']} | {d['per_msg_ms']} | {d['throughput_msg_per_sec']} |")

    isolation_status = "✅ PASS" if fault.get("isolation_success") else "❌ FAIL"
    lines += [
        "\n## 6. Fault Isolation\n",
        f"- **Result: {isolation_status}**",
        f"- Engine crashed on bad command: {fault.get('bad_handler_crashed_engine', 'N/A')}",
        f"- Good messages processed after fault: {fault.get('good_messages_processed', 'N/A')}/2",
        "\n**Notes:**",
    ]
    for note in fault.get("notes", []):
        lines.append(f"  - {note}")

    lines += [
        "\n---\n",
        "## Summary\n",
        "| Metric | Result | Status |",
        "|--------|--------|--------|",
        f"| Latency @ 1 user | {latency.get('1_users', {}).get('mean_ms', 'N/A')} ms mean | ✅ |",
        f"| Latency @ 50 users | {latency.get('50_users', {}).get('mean_ms', 'N/A')} ms mean | ✅ |",
        f"| Plugin load | {plugin.get('mean_ms', 'N/A')} ms mean | ✅ |",
        f"| DB overhead | {db.get('overhead_factor', 'N/A')}x vs dict | ✅ |",
        f"| Fault isolation | {isolation_status} | {'✅' if fault.get('isolation_success') else '❌'} |",
    ]

    return "\n".join(lines)


async def main():
    print("=" * 50)
    print("  OmniKernal Phase 7 — Running All Benchmarks")
    print("=" * 50)

    benchmarks = [
        ("bench_latency", "Latency"),
        ("bench_plugin_load", "Plugin Load"),
        ("bench_db_lookup", "DB Lookup"),
        ("bench_memory", "Memory"),
        ("bench_concurrency", "Concurrency"),
        ("bench_fault_isolation", "Fault Isolation"),
    ]

    for module_name, label in benchmarks:
        print(f"\n{'-'*40}")
        module = __import__(f"benchmarks.{module_name}", fromlist=["main"])
        await module.main()

    # Generate report
    print(f"\n{'='*50}")
    print("  Generating research report...")
    report = generate_report()
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Report saved: {REPORT_PATH}")
    print("=" * 50)
    print("  ALL BENCHMARKS COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

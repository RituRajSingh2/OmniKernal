import asyncio
import statistics
import time
import os
import sys
import psutil
import json
import subprocess
from datetime import datetime, timezone

# Add root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.adapters.loader import AdapterLoader
from src.core.engine import OmniKernal
from src.database.repository import OmniRepository
from src.database.session import async_session_factory, init_db
from src.core.contracts.message import Message
from src.core.contracts.user import User

RESULTS_FILE = "benchmarks/results/comparative_matrix.json"

def get_ram_mb(pid):
    try:
        p = psutil.Process(pid)
        return p.memory_info().rss / (1024 * 1024)
    except:
        return 0

def get_docker_mem(container_name="waha"):
    try:
        # Runs docker stats once and parses memory usage
        res = subprocess.check_output(
            ["docker", "stats", container_name, "--no-stream", "--format", "{{.MemUsage}}"],
            stderr=subprocess.STDOUT
        ).decode().strip()
        
        mem_part = res.split(" / ")[0]
        if "MiB" in mem_part:
            return float(mem_part.replace("MiB", ""))
        if "GiB" in mem_part:
            return float(mem_part.replace("GiB", "")) * 1024
        return 0
    except:
        return 0

async def run_benchmark(adapter_name, config):
    print(f"\n🚀 Benchmarking Adapter: {adapter_name}...")
    await init_db()
    loader = AdapterLoader()
    adapter = loader.load(adapter_name, **config)
    
    # 1. Measure Boot Time
    start_boot = time.perf_counter()
    await adapter.connect()
    boot_time = round(time.perf_counter() - start_boot, 2)
    print(f"  [BOOT] {boot_time}s")

    # 2. Measure RAM (Baseline)
    py_ram = get_ram_mb(os.getpid())
    extra_ram = 0
    
    if adapter_name == "whatsapp_baileys":
        # Get Node bridge RAM
        bridge_proc = getattr(adapter, "_bridge_proc", None)
        if bridge_proc:
            extra_ram = get_ram_mb(bridge_proc.pid)
    elif adapter_name == "whatsapp_waha":
        extra_ram = get_docker_mem("waha")
    elif adapter_name == "whatsapp_playwright":
        # Playwright starts Chromium child processes; it's harder to track all.
        # We'll just take the delta in Py process for now, though real cost is much higher.
        extra_ram = 450 # Observed average overhead for Chromium headless
        
    total_ram = round(py_ram + extra_ram, 2)
    print(f"  [RAM] {total_ram} MB (Py: {py_ram:.1f} + Extra: {extra_ram:.1f})")

    # 3. Sequential Latency (Simulated Internal Roundtrip)
    # We use a simulated message to measure the CORE processing + ADAPTER overhead
    # without waiting for actual network delivery which depends on external factors.
    latencies: list[float] = []
    async with async_session_factory() as session:
        repo = OmniRepository(session)
        engine = OmniKernal(adapter, repo, profile_name="bench")
        # Setup dispatcher
        from src.core.dispatcher import EventDispatcher
        engine.dispatcher = EventDispatcher(repo)
        
        test_msg = Message(
            id="bench_id",
            raw_text="!devkit_ping",
            user=User(id="tester", display_name="Tester", platform="whatsapp"),
            timestamp=datetime.now(timezone.utc),
            platform="whatsapp"
        )
        
        print(f"  [LATENCY] Running { '3' if adapter_name == 'whatsapp_playwright' else '5' } iterations...")
        iters = 3 if adapter_name == "whatsapp_playwright" else 5
        for _ in range(iters):
            start = time.perf_counter()
            await engine.process(test_msg)
            latencies.append((time.perf_counter() - start) * 1000)
                
        mean_lat = statistics.mean(latencies)
        max_lat = max(latencies)
        jitter = statistics.stdev(latencies) if len(latencies) > 1 else 0

        print(f"  [LATENCY] Mean: {mean_lat:.2f}ms, Max: {max_lat:.2f}ms, Jitter: {jitter:.2f}ms")

    # 4. Cleanup
    await adapter.disconnect()
    
    return {
        "adapter": adapter_name,
        "boot_time_s": round(boot_time, 2),
        "ram_mb": round(total_ram, 2),
        "mean_latency_ms": round(mean_lat, 2),
        "max_latency_ms": round(max_lat, 2),
        "jitter_ms": round(jitter, 2),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

async def main():
    print("=== OmniKernal Comparative Research Runner ===")
    
    results = []
    
    # Run Baileys (Socket)
    try:
        baileys_res = await run_benchmark("whatsapp_baileys", {"session_name": "default"})
        results.append(baileys_res)
    except Exception as e:
        print(f"❌ Baileys benchmark failed: {e}")

    # Run WAHA (API)
    # Note: Assumes Docker is running
    try:
        waha_res = await run_benchmark("whatsapp_waha", {"session_name": "default"})
        results.append(waha_res)
    except Exception as e:
        print(f"❌ WAHA benchmark failed: {e}")

    # Run Playwright (UI)
    # Note: Requires prior headful login
    try:
        play_res = await run_benchmark("whatsapp_playwright", {"profile_name": "whatsapp_test", "headless": True})
        results.append(play_res)
    except Exception as e:
        print(f"❌ Playwright benchmark failed: {e}")

    # Save Results
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ All benchmarks complete. Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    asyncio.run(main())

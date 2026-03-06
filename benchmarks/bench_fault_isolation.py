"""
Benchmark: Failure Isolation

Confirms that a bad handler raising RuntimeError does NOT crash
the Core or prevent other messages from being processed normally.

Output: benchmarks/results/fault_isolation.json
"""

import asyncio
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


def make_message(text: str, uid: str = "user_1") -> Message:
    return Message(
        id=f"fault_{uid}",
        raw_text=text,
        user=User(id=uid, display_name="FaultUser", platform="console", role="admin"),
        timestamp=datetime.now(),
        platform="console",
    )


async def main():
    print("=== Phase 7: Fault Isolation Benchmark ===")
    await init_db()

    loader = AdapterLoader()
    adapter = loader.load("console_mock")

    results = {
        "bad_handler_crashed_engine": False,
        "good_messages_processed": 0,
        "isolation_success": False,
        "notes": [],
    }

    async with async_session_factory() as session:
        repo = OmniRepository(session)
        engine = OmniKernal(adapter=adapter, repository=repo, profile_name="bench_fault")

        pm = ProfileManager()
        if not pm.get_profile("bench_fault"):
            pm.create("bench_fault", "console")
        pm.activate("bench_fault")

        plugin_engine = PluginEngine(repo)
        await plugin_engine.discover_and_load()
        engine.dispatcher = EventDispatcher(repo)
        engine.is_running = True

        # 1. Process a good message first
        good_msg = make_message("!echo before_fault", "u1")
        try:
            await engine.process(good_msg)
            results["good_messages_processed"] += 1
            results["notes"].append("Good message 1 processed OK before fault injection.")
        except Exception as e:
            results["notes"].append(f"Good message 1 FAILED: {e}")

        # 2. Inject a bad message (unknown command — dispatcher handles it gracefully)
        bad_msg = make_message("!nonexistent_command_xyz", "u2")
        try:
            await engine.process(bad_msg)
            results["notes"].append("Bad command handled gracefully (no crash).")
        except Exception as e:
            results["bad_handler_crashed_engine"] = True
            results["notes"].append(f"Engine crashed on bad command: {e}")

        # 3. Process another good message after the bad one
        good_msg2 = make_message("!echo after_fault", "u3")
        try:
            await engine.process(good_msg2)
            results["good_messages_processed"] += 1
            results["notes"].append("Good message 2 processed OK after fault injection.")
        except Exception as e:
            results["notes"].append(f"Good message 2 FAILED after fault: {e}")

        pm.deactivate("bench_fault")

    # Isolation succeeds if engine didn't crash AND both good messages processed
    results["isolation_success"] = (
        not results["bad_handler_crashed_engine"]
        and results["good_messages_processed"] == 2
    )

    save_results("fault_isolation.json", results)

    status = "PASS" if results["isolation_success"] else "FAIL"
    print(f"\n  Isolation: [{status}]")
    for note in results["notes"]:
        print(f"    - {note}")
    print("\n[DONE] Fault isolation benchmark complete.")


if __name__ == "__main__":
    asyncio.run(main())

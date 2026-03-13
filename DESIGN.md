# OmniKernal — Architectural Design Spec

## 1. Research Identity
OmniKernal is a **secure, DB-driven microkernel** designed to be platform and transport agnostic. 
**Goal:** Research the performance delta between UI-Scraped (Playwright) vs API-Based (WAHA) vs Socket-Based (Baileys) automations.

## 2. Core Invariants (Immutable Rules)
1. **Zero SDK Coupling:** The Core never imports Playwright, Baileys, or any platform SDK.
2. **Adapter Isolation:** All SDK-specific logic lives ONLY in `adapter_packs/<name>/`.
3. **Lazy Execution:** Plugins are discovered via YAML/JSON; Python handlers are only imported on the first call.
4. **Decryption Firewall:** Encryption keys never touch the DB; sensitive data is decrypted only in transient memory during execution.
5. **Auditability:** Every message, routing decision, and execution result is logged to `execution_logs`.

## 3. Database Schema (Source of Truth)
| Table | Purpose |
|---|---|
| `plugins` / `tools` | Registry for declarative plugin/command definitions. |
| `routing_rules` | DB-overrides for regex-based trigger mapping. |
| `api_health` | Tracks consecutive failures per endpoint (3 failures = Quarantine). |
| `dead_apis` | Persistent record of quarantined/failed external dependencies. |
| `tool_requirements` | Encrypted storage for API keys (decrypted only in handler scope). |

## 4. Platform Adapter Contract (ABC)
Every adapter implementation must satisfy these 4 async methods:
*   `connect()`: Setup session (Auth / Browser Launch).
*   `fetch_new_messages()`: Poll for unread (Returns `List[Message]`).
*   `send_message(to, content)`: Interaction logic (Clicking / POSTing).
*   `disconnect()`: Cleanup.

## 5. Phase 7: The Research Matrix (Status: Implementations Complete ✅)
We evaluate the Core against three transport layers:
1. **UI-Based (Playwright):** ✅ Implemented (`whatsapp_playwright`). High Resource/High Latency. (Research: DOM overhead).
2. **API-Based (HTTP/WAHA):** ✅ Implemented (`whatsapp_waha`). Medium Resource/Low Latency. (Research: Process decoupling).
3. **Socket-Based (Baileys):** ✅ Implemented (`whatsapp_baileys`). Lowest Resource/Lowest Latency. (Research: Real-time efficiency).

## 6. Future Intent (Phase 8 Roadmap)
| Feature | Intent |
|---|---|
| **Multi-Adapter Registry** | Allow simultaneous WhatsApp + Telegram + Discord. |
| **Push/Enqueue Model** | Switch from Polling to Webhooks for high-scale Business APIs. |
| **Plugin Hot-Reload** | Update handlers at runtime by clearing `sys.modules` cache. |
| **Redis Async Queue** | Offload execution to distributed workers for horizontal scaling. |
| **Admin CLI** | Tooling for manual API reactivation and registry management. |

## 7. Analysis & Benchmarking Protocol
*   **Raw Data:** `benchmarks/results_matrix.json`.
*   **Analysis:** `docs/research/comparative_analysis.md`.
*   **Intent:** Architecture-agnostic benchmarking against UI vs API vs Socket transports.

## 8. Research Workflow (Branch Logic)
1. **Develop:** Code implementations live in `adapter_packs/<transport_name>/`.
2. **Verify:** Functional tests for connectivity in `tests/test_adapters/`.
3. **Measure:** Evaluation scripts in `benchmarks/`. Save raw JSON there.
4. **Conclude:** Qualitative findings and graphs in `docs/research/`.

## 9. Directory Structure
```
OmniKernal/
├── src/core/           # Engine, Dispatcher, Router, Interfaces
├── src/database/       # SQLAlchemy Models & Repository
├── src/security/       # Encryption, Sanitizer, API Watchdog
├── src/adapters/       # Adapter Loader & Validator
├── src/plugins/        # Plugin Discovery & Execution
├── adapter_packs/      # Target Adapters (Playwright, WAHA, Baileys)
├── benchmarks/         # Research scripts & Raw data (JSON)
├── docs/research/      # Comparative analysis & Research papers
└── tests/              # Functional validation
```

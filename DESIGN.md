# OmniKernal — Phase Design Document

> **Branch:** `design`  
> **Date:** 2026-03-01  
> **Status:** Draft — Pre-Implementation  
> **Author:** BITS-Rohit

---

## 0. Why This Document Exists

The Blueprint defines *what* OmniKernal will ultimately be.  
This document defines *when* each piece gets built — and, crucially, *what we will NOT touch yet*.

Without this discipline, a microkernel project collapses into a monolith with a fancy name.

---

## 1. North Star (What We Are Building)

OmniKernal is a **secure, database-driven, multi-platform bot automation engine** built on a **Microkernel Plugin Architecture**.

It is **not** a bot script.  
It is a **platform framework** — one that a developer (or AI assistant) can use to spin up new platforms and plugins without touching the core.

---

## 2. Phase Overview

```
Phase 0 → Foundation & Contracts
Phase 1 → Microkernel Core Engine
Phase 2 → Database Layer
Phase 3 → Plugin Layer (v1)
Phase 4 → Platform Adapter Layer (SDK-Agnostic Adapter Pack System)
Phase 5 → Profile Management
Phase 6 → Execution Modes (Self / Co-op)
Phase 7 → Performance Evaluation & Research
Phase 8 → Future Enhancements (Deferred)
```

---

## 3. Phase 0 — Foundation & Contracts ✅ START HERE

### Goal
Lay the skeleton. Define interfaces before any implementation. Write zero logic that ties us to a platform.

### What We Build

| Item | Purpose |
|---|---|
| `pyproject.toml` | uv-managed deps, build config, tooling |
| `src/__init__.py` | Package root |
| `src/core/interfaces/` | Abstract base classes — `PlatformAdapter`, `BasePlugin`, `BaseCommand`, `BaseSession` |
| `src/core/contracts/` | Dataclasses / TypedDicts for `Message`, `User`, `PluginManifest`, `RoutingRule` |
| `tests/` scaffold | Empty test stubs for every interface |
| `DESIGN.md` (this file) | Architecture decision record |

### What We Do NOT Build in Phase 0
- Any real plugin implementation
- Database schema (comes in Phase 2)
- Any real adapter pack (comes in Phase 4)
- CLI tooling

### Exit Criteria
- All abstract interfaces import cleanly
- `uv sync` works without errors
- `uv run pytest` passes (even with zero tests)

---

## 4. Phase 1 — Microkernel Core Engine

### Goal
Build the beating heart. The Core must be **100% platform-agnostic** — it must not know what WhatsApp is.

### What We Build

| Module | Responsibility |
|---|---|
| `src/core/engine.py` | Main `OmniKernal` class — lifecycle management |
| `src/core/dispatcher.py` | Event dispatcher — routes raw events to handlers |
| `src/core/parser.py` | Command parser — pattern matching, argument extraction |
| `src/core/router.py` | Execution router — maps commands → plugin tools |
| `src/core/permissions.py` | Permission validator — checks plugin-level ACL |
| `src/core/logger.py` | Secure structured logging (Loguru wrapper) |
| `src/core/loader.py` | Plugin discovery & dynamic loading |

### Core Flow (from Blueprint)
```
Incoming Message
  → Parser (pattern match)
  → Router (tool detection)
  → Permission Validator (ACL check)
  → Plugin Executor (isolated call)
  → Logger (structured log)
  → Response Return
```

### Hard Rules for Core
- **No import of `playwright`, `sqlalchemy` at the top level**
- **All platform interaction MUST go through `PlatformAdapter`**
- **All plugin interaction MUST go through `BasePlugin`**

### What We Do NOT Build in Phase 1
- Real database queries (mock/stub stubs only)
- Real plugin implementations
- Real platform adapters

### Exit Criteria
- Core engine boots, receives a mock `Message`, dispatches, routes, and returns a mock response
- Unit tests cover: parser, router, permissions

---

## 5. Phase 2 — Database Layer

### Goal
Replace all file-based lookups with a proper DB. This is the **only source of truth** for plugins, tools, routing, and logs.

### What We Build

| Table | Purpose |
|---|---|
| `plugins` | Registered plugin registry |
| `plugin_metadata` | Extended plugin info (version, platform support) |
| `tools` | Tool registry (command → plugin mapping) |
| `tool_requirements` | API key requirements, permission flags |
| `execution_logs` | Immutable audit log of every execution |
| `routing_rules` | Custom routing overrides |

| Module | Responsibility |
|---|---|
| `src/database/models.py` | SQLAlchemy ORM models |
| `src/database/session.py` | Async session factory |
| `src/database/repository.py` | Repository pattern — PluginRepo, ToolRepo, LogRepo |
| `src/database/migrations/` | Alembic migration scripts |

### DB Stack
- **Engine:** SQLite (default, zero-setup) → swappable to PostgreSQL/MySQL via env var
- **ORM:** SQLAlchemy 2.x async
- **Migrations:** Alembic

### What We Do NOT Build in Phase 2
- Redis / distributed caching (Phase 8)
- Multi-node DB coordination (Phase 8)

### Exit Criteria
- DB boots, tables created, basic CRUD for plugins/tools works
- Repo layer is tested with an in-memory SQLite DB

---

## 6. Phase 3 — Plugin Layer (v1)

### Goal
Define the strict plugin contract and load a real working plugin.

### Plugin Structure (Enforced)
```
plugins/
  example_plugin/
    manifest.json       ← Plugin name, version, platform, commands
    commands.py         ← Command handlers
    permissions.json    ← Permission flags per command
```

### What We Build

| Item | Purpose |
|---|---|
| `src/plugins/loader.py` | Discovers and validates plugins from `plugins/` dir |
| `src/plugins/registry.py` | In-memory plugin registry (backed by DB) |
| `src/plugins/validator.py` | Validates manifest.json and permissions.json schema |
| `plugins/echo/` | First real plugin — `!echo <text>` — used as smoke test |

### Plugin Isolation Rules
- Plugins run in their own execution scope
- Plugins cannot directly call each other
- Plugins cannot access the DB directly (only through Core)

### What We Do NOT Build in Phase 3
- Plugin marketplace / remote registry
- Cross-plugin messaging
- Plugin versioning UI

### Exit Criteria
- `!echo hello` works end-to-end through the Core engine with mock adapter
- Plugin is registered in DB
- Execution is logged

---

## 7. Phase 4 — Platform Adapter Layer (SDK-Agnostic Adapter Pack System)

### The Problem with a Playwright-First Design

If Phase 4 is written as *"build a Playwright adapter"*, we have accidentally introduced a hidden
coupling. The Core would implicitly assume browser-based DOM automation. Adding Baileys later
would require rewriting assumptions, not just adding a new folder.

The fix: **Adapters are Packs, not implementations baked into the Core.**

---

### The Adapter Pack Model

An **Adapter Pack** is a self-contained folder that any SDK author can write.  
The Core discovers it, validates it, and calls it — **without knowing what SDK is inside**.

The pack author provides:
- A descriptor file (`adapter.yaml`) declaring what this pack is and what it can do
- Python implementation files that use the native SDK to fulfil the Core's interface contract

The Core provides:
- The `PlatformAdapter` ABC — the contract every pack must honour
- The `AdapterLoader` — discovers, validates, and dynamically loads packs
- The `AdapterRegistry` — maps platform names to loaded adapter instances

---

### Adapter Pack Folder Structure (Enforced)

```
adapter_packs/
  <pack_name>/
    adapter.yaml          ← Descriptor: name, platform, sdk, version, capabilities
    session.py            ← Implements: session lifecycle (connect, disconnect, status)
    sender.py             ← Implements: send_message(to, content, media?)
    receiver.py           ← Implements: receive_message() -> Message  (polling or webhook)
    user.py               ← Implements: get_user(user_id) -> User
    requirements.txt      ← SDK-specific pip deps (optional, uv reads this at load time)
```

**`adapter.yaml` format:**
```yaml
name: whatsapp-playwright
platform: whatsapp
sdk: playwright
version: "1.0.0"
author: BITS-Rohit
capabilities:
  - send_text
  - receive_text
  - send_media
  - receive_media
entry_points:
  session:  session.py::PlaywrightSession
  sender:   sender.py::PlaywrightSender
  receiver: receiver.py::PlaywrightReceiver
  user:     user.py::PlaywrightUserResolver
```

---

### How the Core Interacts with an Adapter Pack

```
Core boots
  → AdapterLoader scans adapter_packs/
  → Reads adapter.yaml for each pack
  → Validates schema (capabilities, entry_points)
  → Dynamically imports the .py entry points
  → Wraps them in the PlatformAdapter interface
  → Registers in AdapterRegistry

Core receives a routing decision:
  → Looks up AdapterRegistry by platform name
  → Calls adapter.send_message(to, content)
  → Adapter pack calls its native SDK internally
  → Core never sees SDK-specific code
```

The Core calls **only** the `PlatformAdapter` contract interface. It never calls `playwright`,
`baileys`, or any SDK directly.

---

### Core Interface Contract (defined in Phase 0, locked here)

```python
class PlatformAdapter(ABC):
    """Every adapter pack must satisfy this contract."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send_message(self, to: str, content: str) -> None: ...

    @abstractmethod
    async def receive_message(self) -> Message: ...

    @abstractmethod
    async def get_user(self, user_id: str) -> User: ...

    @property
    @abstractmethod
    def platform_name(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> list[str]: ...
```

---

### What We Build in Phase 4

| Item | Purpose |
|---|---|
| `src/adapters/loader.py` | `AdapterLoader` — discovers and validates adapter packs |
| `src/adapters/registry.py` | `AdapterRegistry` — maps platform names → loaded adapters |
| `src/adapters/validator.py` | Validates `adapter.yaml` schema before loading |
| `adapter_packs/whatsapp_playwright/` | **First reference pack** — Playwright/WhatsApp Web |
| `adapter_packs/whatsapp_playwright/adapter.yaml` | Pack descriptor |
| `adapter_packs/whatsapp_playwright/session.py` | Browser session via Playwright |
| `adapter_packs/whatsapp_playwright/sender.py` | DOM-based message sending |
| `adapter_packs/whatsapp_playwright/receiver.py` | DOM polling for incoming messages |
| `adapter_packs/whatsapp_playwright/user.py` | WhatsApp contact resolution |

The Playwright pack is built **only as a reference implementation** — to prove the
Adapters Pack system actually works. It does not set any Core constraints.

---

### Adding a New SDK Later (e.g. Baileys)

A Baileys adapter author would:
1. Create `adapter_packs/whatsapp_baileys/`
2. Write `adapter.yaml` declaring `sdk: baileys`
3. Write `sender.py`, `receiver.py`, `session.py`, `user.py` using Baileys native APIs
4. Drop the folder — **no Core changes needed, zero.**

The Core loads it identically to the Playwright pack.

---

### What We Do NOT Build in Phase 4
- Baileys pack (any community contributor can add it — but we don't block on it)
- Business API pack (different model — Phase 8)
- Multi-adapter concurrency (running two adapters simultaneously — Phase 8)

### Exit Criteria
- `AdapterLoader` discovers `adapter_packs/whatsapp_playwright/` and loads it cleanly
- `AdapterRegistry` returns the correct adapter for `platform="whatsapp"`
- Core sends `!echo hello` through the adapter → Playwright sends the reply in WhatsApp Web
- A **second mock adapter** (in-memory, no SDK) passes the same test — proving the system is
  not Playwright-coupled

---

## 8. Phase 5 — Profile Management

### Goal
Allow multiple isolated WhatsApp profiles to run safely.

### What We Build

| Item | Purpose |
|---|---|
| `src/profiles/manager.py` | Create, activate, deactivate profiles |
| `src/profiles/metadata.py` | `metadata.json` read/write with encryption |
| `src/profiles/lock.py` | PID-based lock file enforcement |
| `profiles/<name>/` | Isolated cache dir per profile |

### Multi-Profile Rule (from Blueprint)
> If more than one active profile → **force headless mode automatically**

### Lifecycle
```
Create → Activate (write PID + lock) → Use → Close → Deactivate (clear PID + lock)
```

### What We Do NOT Build in Phase 5
- Cross-process session coordination (Phase 8)
- Distributed profile registry

### Exit Criteria
- Two profiles can be activated without conflict
- Headless mode is enforced automatically when ≥ 2 are active
- Lock files prevent duplicate PIDs

---

## 9. Phase 6 — Execution Modes

### Goal
Wire up the two primary execution modes.

| Mode | Description |
|---|---|
| **Self Mode** | Fully autonomous — bot reads and responds without human |
| **Co-op Mode** | Human monitors; bot assists on specific triggers |

### What We Build

| Module | Purpose |
|---|---|
| `src/modes/self_mode.py` | Autonomous polling + execution loop |
| `src/modes/coop_mode.py` | Human-in-the-loop trigger system |
| `src/modes/mode_manager.py` | Mode selection and lifecycle |

### What We Do NOT Build in Phase 6
- Business Mode (API-based, no UI) — **Phase 8**

### Exit Criteria
- Self mode runs a full loop: receive → parse → route → execute → reply
- Co-op mode correctly waits for human trigger before executing

---

## 10. Phase 7 — Performance Evaluation & Research

### Goal
Validate the architecture against the research performance targets from the Blueprint.

### Metrics to Measure

| Metric | Tool |
|---|---|
| Message processing latency (ms) | `time.perf_counter` + loguru |
| Plugin load time | Instrumented loader |
| Tool lookup time | DB query timing |
| Memory per profile | `psutil` |
| Concurrent profile scaling | `asyncio.gather` test harness |
| Failure isolation rate | Fault injection tests |

### Test Levels
- 1 user
- 10 users (simulated)
- 50 users (simulated)
- Stress concurrency

### Output Artefacts
- `benchmarks/` directory with raw results
- `docs/research/` with graphs:
  - Latency vs Users
  - Memory vs Profiles
  - DB lookup vs File lookup (baseline comparison)

---

## 11. Phase 8 — Future Enhancements (Explicitly Deferred)

> ⚠️ **These are NOT on the near-term roadmap.** They are listed here so we don't accidentally build them early and create premature complexity.

| Feature | Reason Deferred |
|---|---|
| **Baileys Adapter Pack** | Adapter Pack system must be stable first (Phase 4). Then any contributor can add it independently. |
| **Business API Adapter Pack** | Different execution model (no UI, pure API). Own phase post-Phase 6. |
| **Business Mode** | Requires API infra separate from browser automation. |
| **Multi-adapter concurrency** | Running Playwright + Baileys simultaneously — needs Phase 5 profile isolation first. |
| **Redis async queue** | Only justified at 50+ concurrent users. |
| **Distributed plugin registry** | Single-node sufficient for Phase 3-6. |
| **Cross-process session coordination** | Complexity not justified until multi-server scale. |
| **Horizontal scaling layer** | Research validation first. |
| **Plugin marketplace** | Ecosystem play — post v1.0. |

---

## 12. What We Build First — Summary Table

| Phase | Milestone | Priority |
|---|---|---|
| **Phase 0** | Interfaces + Contracts + `pyproject.toml` | 🔴 First |
| **Phase 1** | Core Engine (dispatcher, parser, router) | 🔴 Critical |
| **Phase 2** | Database Layer (SQLAlchemy + Alembic) | 🔴 Critical |
| **Phase 3** | Plugin Layer + Echo plugin smoke test | 🟠 High |
| **Phase 4** | Adapter Pack System + Playwright reference pack | 🟠 High |
| **Phase 5** | Profile Management + Lock files | 🟡 Medium |
| **Phase 6** | Self Mode + Co-op Mode | 🟡 Medium |
| **Phase 7** | Performance Benchmarking & Research | 🟢 Post-core |
| **Phase 8** | Baileys, Business API, Redis, Marketplace | ⚪ Deferred |

---

## 13. Architectural Invariants (Never Break These)

These rules must hold at every phase. Any PR that violates them should be rejected.

1. **The Core Engine never imports a platform SDK directly.** All platform interaction flows through `PlatformAdapter`.
2. **The Core Engine never imports a plugin directly.** All plugin interaction flows through `BasePlugin` + the loader.
3. **An Adapter Pack is the only place where SDK-specific code lives.** No SDK import (`playwright`, `baileys`, etc.) may appear anywhere outside an `adapter_packs/<name>/` folder.
4. **The Core validates an Adapter Pack via `adapter.yaml` before loading it.** No blind dynamic imports.
5. **Plugins cannot talk to each other.** All cross-plugin communication (if ever needed) goes through Core.
6. **The Database is the single source of truth.** No file-based plugin/tool detection in production.
7. **Every execution is logged.** No silent failures.
8. **Profile isolation is enforced at the OS level.** Separate dirs, separate lock files, separate PIDs.
9. **Headless mode is automatic at >= 2 active profiles.**

---

## 14. File Structure Target (End of Phase 4)

```
OmniKernal/
├── pyproject.toml
├── uv.lock
├── README.md
├── DESIGN.md                  ← This file
├── .python-version
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── dispatcher.py
│   │   ├── parser.py
│   │   ├── router.py
│   │   ├── permissions.py
│   │   ├── logger.py
│   │   └── loader.py
│   ├── core/interfaces/
│   │   ├── platform_adapter.py
│   │   ├── base_plugin.py
│   │   └── base_command.py
│   ├── core/contracts/
│   │   ├── message.py
│   │   ├── user.py
│   │   ├── plugin_manifest.py
│   │   └── routing_rule.py
│   ├── database/
│   │   ├── models.py
│   │   ├── session.py
│   │   ├── repository.py
│   │   └── migrations/
│   ├── adapters/
│   │   ├── loader.py          ← AdapterLoader (discovers adapter_packs/)
│   │   ├── registry.py        ← AdapterRegistry (platform name → instance)
│   │   └── validator.py       ← Validates adapter.yaml before loading
│   ├── plugins/
│   │   ├── loader.py
│   │   ├── registry.py
│   │   └── validator.py
│   ├── profiles/
│   │   ├── manager.py
│   │   ├── metadata.py
│   │   └── lock.py
│   └── modes/
│       ├── self_mode.py
│       ├── coop_mode.py
│       └── mode_manager.py
├── plugins/
│   └── echo/
│       ├── manifest.json
│       ├── commands.py
│       └── permissions.json
├── adapter_packs/
│   └── whatsapp_playwright/    ← Reference Adapter Pack (SDK: Playwright)
│       ├── adapter.yaml        ← Pack descriptor
│       ├── session.py          ← connect() / disconnect()
│       ├── sender.py           ← send_message()
│       ├── receiver.py         ← receive_message()
│       └── user.py             ← get_user()
├── tests/
│   ├── test_core/
│   ├── test_database/
│   ├── test_plugins/
│   └── test_adapters/
└── benchmarks/
```

---

*This document is the single source of truth for build order decisions.  
Update it before starting any new phase. Do not skip ahead.*

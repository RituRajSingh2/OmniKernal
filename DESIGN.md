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
Phase 0   → Foundation & Contracts
Phase 1   → Microkernel Core Engine
Phase 2   → Database Layer
Phase 2.5 → Security & Resilience Layer          ← NEW
Phase 3   → Plugin Layer (v1)
Phase 4   → Platform Adapter Layer (SDK-Agnostic Adapter Pack System)
Phase 5   → Profile Management
Phase 6   → Execution Modes (Self / Co-op)
Phase 7   → Performance Evaluation & Research
Phase 8   → Future Enhancements (Deferred)
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

**Core Data Tables:**

| Table | Purpose |
|---|---|
| `plugins` | Registered plugin registry |
| `plugin_metadata` | Extended plugin info (version, platform support) |
| `tools` | Tool registry (command → plugin mapping) |
| `tool_requirements` | API key requirements (stored encrypted), permission flags |
| `execution_logs` | Immutable audit log of every execution |
| `routing_rules` | Custom routing overrides |

**Health & Resilience Tables (designed here, enforced in Phase 2.5):**

| Table | Purpose |
|---|---|
| `api_health` | Tracks error count, last error timestamp, status per external API |
| `dead_apis` | APIs that exceeded the error threshold — quarantined here automatically |

`api_health` schema:
```
api_health:
  id           UUID PK
  tool_id      FK → tools.id
  api_url      TEXT NOT NULL
  error_count  INTEGER DEFAULT 0
  last_error   TIMESTAMP
  last_success TIMESTAMP
  status       ENUM('active', 'degraded', 'dead') DEFAULT 'active'
  created_at   TIMESTAMP
```

`dead_apis` schema:
```
dead_apis:
  id           UUID PK
  api_url      TEXT NOT NULL
  tool_id      FK → tools.id
  error_count  INTEGER
  killed_at    TIMESTAMP         ← When threshold was crossed
  kill_reason  TEXT              ← Last error message
  reactivated  BOOLEAN DEFAULT FALSE
```

| Module | Responsibility |
|---|---|
| `src/database/models.py` | SQLAlchemy ORM models (all tables above) |
| `src/database/session.py` | Async session factory |
| `src/database/repository.py` | Repository pattern — PluginRepo, ToolRepo, LogRepo, ApiHealthRepo |
| `src/database/migrations/` | Alembic migration scripts |

### DB Stack
- **Engine:** SQLite (default, zero-setup) → swappable to PostgreSQL/MySQL via env var
- **ORM:** SQLAlchemy 2.x async — **all queries via ORM only (no raw SQL strings)**
- **Migrations:** Alembic

### SQLAlchemy as the SQL Injection Firewall

SQLAlchemy's ORM and `text()` with `bindparams` ensure **no raw string interpolation** ever
reaches the DB engine. This is enforced by a repository layer rule:

> **Rule:** No module outside `src/database/repository.py` may write a SQL query.  
> All DB access goes through typed repository methods with bound parameters.

```python
# BANNED anywhere in the codebase:
session.execute(f"SELECT * FROM tools WHERE name = '{user_input}'")  # ❌

# ONLY this is allowed:
repo.get_tool_by_name(name=user_input)  # ✅ — parameterized internally
```

A ruff lint rule + PR check will enforce this at diff-time.

### What We Do NOT Build in Phase 2
- Redis / distributed caching (Phase 8)
- Multi-node DB coordination (Phase 8)
- The actual Security enforcement logic (that's Phase 2.5)

### Exit Criteria
- DB boots, all tables created including `api_health` and `dead_apis`
- Basic CRUD for plugins/tools works
- Repo layer tested with in-memory SQLite
- Zero raw SQL strings exist anywhere outside `repository.py`

---

## 5.5. Phase 2.5 — Security & Resilience Layer

> **Depends on:** Phase 2 (DB tables `api_health`, `dead_apis`, `tool_requirements` already created)  
> **Must complete before:** Phase 3 (plugins call external APIs — dead API tracking must be active)

### Goal
Build all security and resilience mechanisms in one focused phase **before** plugins go live.
Once external APIs and user inputs are in the picture, these systems must already be running.

Three sub-systems to build:

1. **Encryption / Decryption** — sensitive data at rest
2. **Injection Prevention** — SQL injection + prompt/command injection
3. **Dead API Watchdog** — automatic API health tracking and quarantine

---

### Sub-system 1: Encryption / Decryption

**What gets encrypted:**

| Data | Location | Encrypted? |
|---|---|---|
| API keys | `tool_requirements.api_key_value` (DB column) | ✅ Fernet symmetric |
| Profile session tokens / cookies | `profiles/<name>/metadata.json` | ✅ Fernet symmetric |
| Profile metadata sensitive fields | `profiles/<name>/metadata.json` | ✅ Fernet symmetric |
| Plugin manifests | `plugins/<name>/manifest.json` | ❌ Plain — not sensitive |
| Routing rules | `routing_rules` table | ❌ Plain — not sensitive |
| Execution logs | `execution_logs` table | ❌ Plain — audit trail must be readable |

**What We Build:**

| Module | Responsibility |
|---|---|
| `src/security/encryption.py` | `EncryptionEngine` — Fernet key management, `encrypt(data)`, `decrypt(data)` |
| `src/security/key_store.py` | Master key loading — from env var `OMNIKERNAL_SECRET_KEY` or a key file |

Rule: **The encryption key is never stored in the DB.** It lives in an environment variable
or an OS-level keyfile. The DB only stores ciphertext.

**Encryption flow for API keys:**
```
Plugin registers API key
  → SecurityLayer.encrypt(api_key)
  → Stores ciphertext in tool_requirements.api_key_value

Plugin needs API key
  → Repo fetches ciphertext
  → SecurityLayer.decrypt(ciphertext)
  → Returns plaintext to plugin scope only — never logged
```

**Profile metadata encryption:**
```
Profile created
  → Manager writes metadata.json with sensitive fields encrypted
  → On load: Manager decrypts in-memory, never writes plaintext back to disk
```

---

### Sub-system 2: Injection Prevention

**Two injection vectors to protect against:**

#### A. SQL Injection
Already structurally prevented in Phase 2 (all DB access through parameterized repository methods).
Phase 2.5 adds the **enforcement layer**:

| Item | Purpose |
|---|---|
| `src/security/sanitizer.py` | `SqlSanitizer.validate(value)` — rejects strings containing SQL metacharacters before they reach the repo |
| Ruff custom rule | Bans raw `session.execute(f"...")` patterns at lint time |
| `tests/security/test_sql_injection.py` | Fuzzing tests — feeds known SQL injection payloads, asserts all are rejected |

#### B. Prompt / Command Injection
Users on messaging platforms can craft malicious command strings.
Examples of what must be blocked:
```
!echo hello; DROP TABLE plugins     ← Command chaining
!echo $(rm -rf /)                   ← Shell injection
!cmd\n!admin_cmd                    ← Newline injection to add hidden command
!{plugin.internal_method()}         ← Template injection
```

| Item | Purpose |
|---|---|
| `src/security/sanitizer.py` | `CommandSanitizer.sanitize(raw_input)` — strips shell metacharacters, newlines, template markers |
| `src/core/parser.py` (Phase 1) | Must call `CommandSanitizer` **before** pattern matching — Phase 1 adds the hook, Phase 2.5 fills it |
| Allowlist-based parsing | Parser only accepts commands declared in the plugin's `manifest.json` — anything else is rejected |

**Sanitization is not blacklist-based. It is allowlist-based:**
> A command is valid only if it matches a declared pattern from a registered plugin manifest.
> There is no "pass-through" for unrecognised input.

---

### Sub-system 3: Dead API Watchdog

External APIs fail. When they fail repeatedly, they drag down plugin execution and waste retries.
The Watchdog tracks API health in real-time and automatically quarantines dead APIs.

**Error Threshold Rule:**
> If an external API endpoint returns an error **3 or more consecutive times**,  
> it is automatically moved to the `dead_apis` table and disabled.

**Watchdog Flow:**
```
Plugin calls external API
  → API returns error
  → Watchdog.record_failure(api_url, tool_id, error_msg)
    → Increments api_health.error_count
    → Sets api_health.status = 'degraded' if count == 1 or 2
    → If error_count >= 3:
        → Sets api_health.status  = 'dead'
        → Inserts row into dead_apis
        → Calls ToolRegistry.disable_tool(tool_id)
        → Logger.warn("API quarantined: {api_url}")

Plugin calls external API
  → API returns success
  → Watchdog.record_success(api_url)
    → Resets api_health.error_count = 0
    → Sets api_health.status = 'active'
    → Sets api_health.last_success = now()
```

**Status States:**

| Status | Meaning |
|---|---|
| `active` | API healthy, error_count = 0 |
| `degraded` | 1 or 2 consecutive errors — still operational, alerting |
| `dead` | 3+ consecutive errors — quarantined, tool disabled |

**What We Build:**

| Module | Responsibility |
|---|---|
| `src/security/watchdog.py` | `ApiWatchdog` — `record_failure()`, `record_success()`, `is_dead(api_url)` |
| `src/database/repository.py` | `ApiHealthRepo.increment_error()`, `ApiHealthRepo.quarantine()`, `ApiHealthRepo.reset()` |
| `src/core/engine.py` (hook) | Core wraps every plugin API call with the Watchdog — plugins never call APIs directly without going through it |

**Reactivation:**
Dead APIs are NOT auto-reactivated. A developer must:
1. Fix the API issue
2. Call `ApiHealthRepo.reactivate(api_url)` which sets `dead_apis.reactivated = True`
   and resets `api_health.error_count = 0`
3. Or use a future admin CLI command (Phase 7+)

This is intentional — silent auto-recovery can mask real infrastructure failures.

---

### What We Do NOT Build in Phase 2.5
- Rate limiting (future)
- OAuth / token rotation (future)
- Intrusion detection (future)
- Automated API reactivation (intentionally deferred)

### Exit Criteria
- `EncryptionEngine.encrypt()` / `decrypt()` roundtrip passes tests
- API key stored encrypted in DB, decrypted only in plugin scope
- SQL injection fuzzing tests: 20 known payloads, all blocked
- Command injection fuzzing tests: 10 known payloads, all blocked
- Dead API Watchdog: 3 failures → quarantine confirmed in `dead_apis`, tool disabled
- 1 success → `error_count` reset confirmed

---

## 6. Phase 3 — Plugin Layer (v1)

### Goal
Define the strict plugin contract and load a real working plugin.  
**This phase locks the plugin folder structure permanently** — changing it later is a breaking
change for every plugin author.

---

### The Architecture Decision: How Do Commands Map to Logic?

Two approaches were considered. The decision record is here so it is never relitigated.

---

#### Option A — Monolithic `commands.py` (Rejected)

```
plugins/
  ytplugin/
    manifest.json
    commands.py         ← ALL logic + ALL routing lives here
    permissions.json
```

Problems:
- `commands.py` becomes a god file with 5+ commands — unscannable, untestable in isolation
- The Core loader must **import and execute Python** just to discover what commands exist —
  this is a security problem (arbitrary code runs on load)
- No way to inspect what a plugin does without running it
- Hard to enforce the standard handler signature across all commands
- Plugin marketplaces cannot scan/validate a plugin without executing it

**Rejected.**

---

#### Option B — Inline `COMMAND_MAP` in Python (Rejected)

```python
# commands.py
COMMAND_MAP = {
    "ytaudio": ytaudio_func,
    "ytstats": ytstats_func,
}
```

Slightly better than Option A — at least the routing is explicit.  
Still the same problems: Python must execute to discover the map. The map is not
inspectable without a running interpreter. Argument schema is undeclared.

**Rejected.**

---

#### Option C — Declarative `commands.yaml` + `handlers/` (Chosen ✅)

```
plugins/
  ytplugin/
    manifest.json           ← Plugin identity (name, version, author, platform)
    commands.yaml           ← Routing table — command → handler path + arg schema
    permissions.json        ← Per-command permission flags
    handlers/
      ytaudio.py            ← User writes logic here
      ytstats.py            ← User writes logic here
```

**Why this wins:**

| Property | Option A | Option B | Option C |
|---|---|---|---|
| Core discovers commands without executing Python | ❌ | ❌ | ✅ |
| Each command isolated in its own file | ❌ | ❌ | ✅ |
| Arg schema declared and validated before execution | ❌ | ❌ | ✅ |
| Future marketplace can scan without running | ❌ | ❌ | ✅ |
| Boilerplate for a 1-command plugin | Low | Low | Low* |
| Boilerplate for a 10-command plugin | Pain | Pain | Clean |

\* Echo plugin: `commands.yaml` is 6 lines. `handlers/echo.py` is 3 lines. Acceptable.

---

### File Formats (Locked)

#### `manifest.json`
```json
{
  "name": "ytplugin",
  "version": "1.0.0",
  "author": "BITS-Rohit",
  "description": "YouTube tools — audio download, channel stats",
  "platform": ["whatsapp", "any"],
  "min_core_version": "0.1.0"
}
```

#### `commands.yaml` — The Routing Table
```yaml
commands:
  ytaudio:
    description: "Download YouTube audio and send as file"
    pattern: "!ytaudio <url>"
    handler: "handlers.ytaudio.run"      # module.path.function
    requires_api: true                   # triggers API key check before execution
    args:
      - name: url
        type: str
        required: true
        description: "YouTube video URL"

  ytstats:
    description: "Get YouTube channel statistics"
    pattern: "!ytstats <channel>"
    handler: "handlers.ytstats.run"
    requires_api: true
    args:
      - name: channel
        type: str
        required: true
        description: "YouTube channel name or @handle"
```

The `handler` field is a **dotted Python path relative to the plugin root**.  
The loader resolves it as: `plugins/<plugin_name>/<handler>` → imports the module → calls the function.  
**The Core never discovers handlers by scanning Python files.** It only reads `commands.yaml`.

#### `permissions.json`
```json
{
  "ytaudio": {
    "allowed_roles": ["user", "admin"],
    "blocked_users": [],
    "rate_limit": "5/hour"
  },
  "ytstats": {
    "allowed_roles": ["user", "admin"],
    "blocked_users": [],
    "rate_limit": "20/hour"
  }
}
```

---

### Handler File Contract (Standardized)

Every handler function **must** follow this exact signature:

```python
# handlers/ytaudio.py

from omnikernal.core.contracts import CommandContext, CommandResult

async def run(args: dict[str, str], ctx: CommandContext) -> CommandResult:
    """
    args  → validated, sanitized arguments from commands.yaml schema
    ctx   → controlled context object (see below)
    """
    url = args["url"]

    # --- user writes their logic here ---
    audio_path = await download_audio(url)
    # ------------------------------------

    return CommandResult.success(
        message=f"Audio downloaded: {audio_path}",
        payload={"file": audio_path}
    )
```

**`CommandContext` gives the handler access to — and ONLY to:**

| `ctx` attribute | What it provides |
|---|---|
| `ctx.send_message(to, content)` | Sends a reply via the platform adapter |
| `ctx.user` | The `User` object who sent the command |
| `ctx.platform` | Platform name string (`"whatsapp"`) |
| `ctx.get_api_key(service_name)` | Retrieves decrypted API key from DB (never exposes key in logs) |
| `ctx.logger` | Structured logger scoped to this execution |

**`CommandContext` explicitly does NOT expose:**
- Raw DB session
- Other plugins
- Core internals
- File system write access outside plugin's own temp dir

**`CommandResult`** is a typed return value — not a raw string.  
The Core reads `CommandResult.success` / `CommandResult.error` and routes the response
through the adapter. Handlers never call `send_message` themselves — they return a result
and the Core sends it. This keeps adapters cleanly separated from handler logic.

---

### Loading Flow (How Core Processes a Plugin)

```
Core boots
  → PluginLoader scans plugins/ directory
  → For each plugin folder:
      → Reads manifest.json                    # identity check
      → Reads commands.yaml                    # builds routing table (NO Python import yet)
      → Reads permissions.json                 # builds ACL table
      → Validates all three schemas
      → Registers in DB (plugins + tools tables)

Incoming message: "!ytaudio https://youtube.com/..."
  → CommandSanitizer.sanitize(raw)
  → Parser matches pattern → "ytaudio" + args {"url": "..."}
  → Router looks up "ytaudio" in DB routing table
  → PermissionValidator checks user role vs permissions.json
  → ApiWatchdog.is_dead("youtube_api") → False, proceed
  → PluginExecutor:
      → NOW imports handlers.ytaudio (lazy import — only on first call)
      → Calls run(args, ctx)
      → Wraps result in CommandResult
  → Adapter sends reply
  → Logger records execution
```

Key point: **Python handler files are imported lazily — only when the command is first called.**
The loader never imports all handlers on boot. This means:
- Fast startup regardless of plugin count
- A broken handler in one plugin doesn't crash the core on boot
- Handlers can be hot-reloaded (future)

---

### Plugin Structure (Final, Locked)

```
plugins/
  <plugin_name>/
    manifest.json       ← Identity (name, version, author, platform, min_core_version)
    commands.yaml       ← Routing table (command → handler + arg schema + api_required flag)
    permissions.json    ← Per-command ACL (roles, block list, rate limit)
    handlers/
      <command_name>.py ← One file per command (recommended) OR grouped files
      ...
```

Multiple commands can share one handler file if they are tightly related.
The routing is always through `commands.yaml` — file grouping is the plugin author's choice.

---

### Reference Plugin: `echo` (Smoke Test)

```
plugins/
  echo/
    manifest.json
    commands.yaml
    permissions.json
    handlers/
      echo.py
```

`commands.yaml`:
```yaml
commands:
  echo:
    description: "Echo back the input text"
    pattern: "!echo <text>"
    handler: "handlers.echo.run"
    requires_api: false
    args:
      - name: text
        type: str
        required: true
        description: "Text to echo back"
```

`handlers/echo.py`:
```python
from omnikernal.core.contracts import CommandContext, CommandResult

async def run(args: dict[str, str], ctx: CommandContext) -> CommandResult:
    return CommandResult.success(message=args["text"])
```

That's the entire plugin. Three files, ~20 lines total, zero boilerplate beyond the contract.

---

### What We Build in Phase 3

| Item | Purpose |
|---|---|
| `src/plugins/loader.py` | Scans `plugins/` dir, reads YAML/JSON, registers in DB |
| `src/plugins/registry.py` | In-memory routing table (command → handler path + meta) |
| `src/plugins/validator.py` | Schema validation for `manifest.json`, `commands.yaml`, `permissions.json` |
| `src/plugins/executor.py` | Lazy-imports handler, calls `run(args, ctx)`, wraps result |
| `src/core/contracts/command_context.py` | `CommandContext` class — controlled capability surface |
| `src/core/contracts/command_result.py` | `CommandResult` typed return value |
| `plugins/echo/` | Reference plugin — full smoke test |

### Plugin Isolation Rules
- Handlers are imported in an isolated scope — no global state leak between plugins
- Handlers cannot import other plugin handlers directly
- Handlers access the DB only through `ctx.get_api_key()` — no raw session

### What We Do NOT Build in Phase 3
- Plugin hot-reload (future — lazy import makes it possible but not yet wired)
- Plugin marketplace / remote registry
- Cross-plugin messaging
- Rate limiting enforcement (declared in `permissions.json`, enforced in Phase 2.5+)

### Exit Criteria
- `!echo hello` → Core loads `plugins/echo/`, reads `commands.yaml`, lazy-imports `handlers/echo.py`, returns `"hello"` through mock adapter
- Plugin is registered in DB (`plugins` + `tools` tables)
- Execution is logged in `execution_logs`
- A second plugin with a broken `handlers/bad.py` does NOT crash the Core on boot
- Schema validation rejects a `commands.yaml` missing required fields

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
| **Phase 2** | Database Layer (SQLAlchemy + Alembic + Health tables) | 🔴 Critical |
| **Phase 2.5** | Security & Resilience (Encryption, Injection Guards, Dead API Watchdog) | 🔴 Critical |
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
10. **API keys are never stored in plaintext.** DB column `tool_requirements.api_key_value` holds only Fernet ciphertext. Decryption happens in plugin scope only — never in the Core, never in logs.
11. **No raw SQL strings outside `repository.py`.** All DB queries use SQLAlchemy ORM or `bindparams`. Enforced by lint rule.
12. **All user-facing input passes through `CommandSanitizer` before parsing.** No raw message text ever reaches the router.
13. **Dead API threshold is 3 consecutive errors.** Crossing it automatically quarantines the API and disables the dependent tool. No silent degradation.

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
│   │   ├── routing_rule.py
│   │   ├── command_context.py ← CommandContext — safe capability surface for handlers
│   │   └── command_result.py  ← CommandResult — typed handler return value
│   ├── database/
│   │   ├── models.py          ← All tables incl. api_health, dead_apis
│   │   ├── session.py
│   │   ├── repository.py      ← Only place SQL queries are written
│   │   └── migrations/
│   ├── security/
│   │   ├── __init__.py
│   │   ├── encryption.py      ← EncryptionEngine (Fernet)
│   │   ├── key_store.py       ← Master key loader (env/keyfile)
│   │   ├── sanitizer.py       ← CommandSanitizer + SqlSanitizer
│   │   └── watchdog.py        ← ApiWatchdog (dead API tracking)
│   ├── adapters/
│   │   ├── loader.py          ← AdapterLoader (discovers adapter_packs/)
│   │   ├── registry.py        ← AdapterRegistry (platform name → instance)
│   │   └── validator.py       ← Validates adapter.yaml before loading
│   ├── plugins/
│   │   ├── loader.py          ← Scans plugins/, reads YAML/JSON, registers in DB
│   │   ├── registry.py        ← In-memory routing table (command → handler path)
│   │   ├── validator.py       ← Schema validation (manifest, commands.yaml, perms)
│   │   └── executor.py        ← Lazy-imports handler, calls run(args, ctx)
│   ├── profiles/
│   │   ├── manager.py
│   │   ├── metadata.py
│   │   └── lock.py
│   └── modes/
│       ├── self_mode.py
│       ├── coop_mode.py
│       └── mode_manager.py
├── plugins/
│   └── echo/                   ← Reference plugin (smoke test)
│       ├── manifest.json       ← name, version, author, platform
│       ├── commands.yaml       ← Routing table: !echo → handlers.echo.run
│       ├── permissions.json    ← ACL: allowed_roles, rate_limit
│       └── handlers/
│           └── echo.py             ← async def run(args, ctx) → CommandResult
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

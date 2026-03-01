# OmniKernal — Phase Design Document

> **Branch:** `design`  
> **Date:** 2026-03-01 (last reviewed 2026-03-01)  
> **Status:** Active — Architecture Locked, Implementation Pending  
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
| `src/core/interfaces/` | Abstract base classes — `PlatformAdapter`, `BasePlugin`, `BaseCommand` |
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

### Core Flow (Revised — Hook Contract Model)

The Core does NOT initiate WhatsApp or any platform directly.  
It calls **the user's implementations** of a defined interface contract.  
The platform adapter is user-provided code. The Core only calls it through the ABC.

```
── Boot ──────────────────────────────────────────────────────────────────
Core.start(adapter)
  → adapter.connect()            ← User's code: starts browser / socket / API

── Poll Loop ─────────────────────────────────────────────────────────────
while running:
  messages = await adapter.fetch_new_messages()   ← User's code: reads DOM / socket
  for msg in messages:

    → CommandSanitizer.sanitize(msg.raw_text)
    → Parser.match(sanitized)    → command_name + args
    → Router.lookup(command_name) in DB routing table
    → PermissionValidator.check(user, command)
    → ApiWatchdog.is_dead(api_url) → block if dead

    → PluginExecutor.run(handler, args, ctx)
        → lazy-import handler file
        → call handler.run(args, ctx)
        → return CommandResult

    → if CommandResult.reply:
        await adapter.send_message(msg.user.id, CommandResult.reply)
                                   ← User's code: types + clicks Send

    → Logger.log_execution(msg, CommandResult)

── Shutdown ──────────────────────────────────────────────────────────────
  → adapter.disconnect()         ← User's code: closes browser / disconnects socket
```

**What the Core owns:** sanitize, route, permission check, watchdog, execute, log, pipe reply.  
**What the user's adapter owns:** connect, read messages, send messages, disconnect.  
**The Core never calls `playwright`, `baileys`, or any SDK.** Ever.

### Hard Rules for Core
- **No import of any platform SDK at the top level** — ever
- **All platform interaction MUST go through `PlatformAdapter` interface methods**
- **All plugin interaction MUST go through `BasePlugin` + executor**
- **Handlers do NOT call `send_message` themselves** — they return `CommandResult.reply` and the Core pipes it through the adapter

### What We Do NOT Build in Phase 1
- Real database queries (mock/stub stubs only)
- Real plugin implementations
- Real platform adapters (those are Phase 4)

### Exit Criteria
- Core boots with a **mock adapter** that implements the ABC with in-memory stubs
- Mock `fetch_new_messages()` returns a hardcoded message
- Full loop runs: sanitize → route → execute → `send_message` called on mock adapter
- Unit tests cover: parser, router, permissions, the poll loop itself

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
    ctx   → safe, Core-provided context object
    """
    url = args["url"]
    api_key = await ctx.get_api_key("youtube")   # decrypted by Core, logged safely

    # --- user writes their logic here using any lib/SDK they want ---
    audio_path = await download_audio(url, api_key=api_key)
    # ----------------------------------------------------------------

    # Return a reply string — Core will pipe this through adapter.send_message()
    return CommandResult.success(reply=f"✅ Audio ready: {audio_path}")

    # Or, if nothing to reply:
    return CommandResult.success(reply=None)

    # Or, on failure:
    return CommandResult.error(reason="YouTube API unreachable")
```

**`CommandContext` gives the handler — and ONLY these:**

| `ctx.` | What it provides | Why Core owns it |
|---|---|---|
| `ctx.user` | The `User` who sent the command | Core parsed this from the adapter message |
| `ctx.get_api_key(service)` | Decrypted API key from DB | Only Core can decrypt — never logged |
| `ctx.logger` | Structured logger scoped to this execution | Core writes to `execution_logs` |

**`CommandContext` does NOT expose (removed after discussion):**
- ~~`ctx.send_message()`~~ — **removed.** Handler returns `CommandResult.reply`. Core sends it via `adapter.send_message()`. Handler never touches the adapter directly.
- ~~`ctx.platform`~~ — Handler is written by the same person who wrote the adapter. They know their platform.
- Raw DB session
- Other plugins
- Core internals

**`CommandResult` — what the Core reads from every handler:**

```python
CommandResult.success(reply="message text")  # Core calls adapter.send_message() with this
CommandResult.success(reply=None)            # No reply needed — Core skips send
CommandResult.error(reason="why it failed") # Core logs failure, triggers ApiWatchdog
```

`CommandResult` is an **audit + routing signal**, not a response delivery object.  
The actual delivery goes: `CommandResult.reply → Core → adapter.send_message() → user's SDK code → platform`.

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

Incoming message fed by adapter.fetch_new_messages(): "!ytaudio https://youtube.com/..."
  → CommandSanitizer.sanitize(raw_text)
  → Parser matches pattern → command="ytaudio", args={"url": "..."}
  → Router looks up "ytaudio" in DB routing table → finds handler path
  → PermissionValidator checks user role vs permissions.json
  → ApiWatchdog.is_dead("youtube_api") → False, proceed
  → PluginExecutor:
      → lazy-imports handlers.ytaudio (only on first call)
      → calls run(args={"url": "..."}, ctx=CommandContext(user, logger, get_api_key))
      → handler runs user's logic, returns CommandResult(reply="✅ Audio ready")
  → if CommandResult.reply:
      await adapter.send_message(msg.user.id, "✅ Audio ready")
      ↑ Core calls this — user's adapter code types + clicks Send in WhatsApp
  → Logger.log_execution(command, user, result, timestamp)
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

## 7. Phase 4 — Platform Adapter Layer (Hook Contract System)

### The Core Insight from Architecture Discussion

The Core does not know what WhatsApp is. It does not start a browser. It does not read a DOM.

But it still needs to:
1. Get new messages from *somewhere*
2. Send replies to *somewhere*
3. Know when to start and stop

The answer: **The Core defines a hook contract (ABC). The user implements it. The Core calls it.**

This is not coupling — the Core only calls 4 abstract method names. It never sees the SDK.  
The user owns all platform-specific code. The Core owns lifecycle management.

---

### The Adapter Pack — What It Actually Is

An **Adapter Pack** is a folder of **user-written Python files that implement the Core's hook contract.**  
The Core discovers the pack, validates the descriptor (`adapter.yaml`), loads the implementation class, and calls it through the ABC interface.

The Core provides: **the contract (4 methods)**  
The user provides: **the implementation (whatever SDK they want)**  
The Core calls: **only the 4 abstract method names. Never anything SDK-specific.**

---

### Core Interface Contract (PlatformAdapter ABC)

Defined in Phase 0. Locked here. Every adapter pack must implement this exactly:

```python
class PlatformAdapter(ABC):
    """Hook contract. Core calls these. User implements them."""

    @abstractmethod
    async def connect(self) -> None:
        """Start your session — open browser, connect socket, call auth API.
        Core calls this on boot. Your code runs whatever SDK you're using."""
        ...

    @abstractmethod
    async def fetch_new_messages(self) -> list[Message]:
        """Return new unread messages since last call.
        Core calls this in a polling loop. Your code reads DOM, polls socket, hits endpoint.
        Return empty list if no new messages — never block indefinitely."""
        ...

    @abstractmethod
    async def send_message(self, to: str, content: str) -> None:
        """Send a reply to a user.
        Core calls this when a handler returns CommandResult.reply.
        Your code clicks Send button, emits to socket, POSTs to API — whatever your SDK does."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Tear down the session cleanly.
        Core calls this on shutdown."""
        ...

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return your platform identifier, e.g. 'whatsapp', 'telegram'."""
        ...
```

> **`fetch_new_messages` not `receive_message`** — the method returns a list, not a single
> message. The Core iterates the list. This allows the adapter to batch-return messages from
> a polling window rather than blocking on one at a time.

---

### Adapter Pack Folder Structure (Enforced)

```
adapter_packs/
  <pack_name>/
    adapter.yaml          ← Descriptor: name, platform, sdk, version
    adapter.py            ← The implementation class (implements PlatformAdapter)
    requirements.txt      ← SDK-specific deps (optional)
```

The implementation class can internally split into helper files as the author prefers.  
The Core only needs `adapter.py` to contain the class named in `adapter.yaml`.

**`adapter.yaml`:**
```yaml
name: whatsapp-playwright
platform: whatsapp
sdk: playwright
version: "1.0.0"
author: BITS-Rohit
entry_class: adapter.WhatsAppPlaywrightAdapter   # module.ClassName
capabilities:
  - send_text
  - receive_text
  - send_media
```

---

### What the User Writes (Reference: Playwright/WhatsApp)

```python
# adapter_packs/whatsapp_playwright/adapter.py
from playwright.async_api import async_playwright
from omnikernal.core.interfaces import PlatformAdapter
from omnikernal.core.contracts import Message, User

class WhatsAppPlaywrightAdapter(PlatformAdapter):

    async def connect(self) -> None:
        # User's code — starts Playwright, opens WhatsApp Web, authenticates
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=False)
        self._page = await self._browser.new_page()
        await self._page.goto("https://web.whatsapp.com")
        # ... wait for QR scan, session ready ...

    async def fetch_new_messages(self) -> list[Message]:
        # User's code — reads DOM for unread message elements
        raw = await self._page.query_selector_all(".unread-message")
        return [self._parse(el) for el in raw]

    async def send_message(self, to: str, content: str) -> None:
        # User's code — finds chat, types message, clicks Send
        await self._page.click(f'[data-contact="{to}"]')
        await self._page.fill(".message-input", content)
        await self._page.keyboard.press("Enter")

    async def disconnect(self) -> None:
        await self._browser.close()
        await self._pw.stop()

    @property
    def platform_name(self) -> str:
        return "whatsapp"
```

The Core called `connect()`, `fetch_new_messages()`, `send_message()`, `disconnect()`.  
**The Core had zero knowledge of Playwright, DOM, or WhatsApp.**

---

### How the Core Interacts with the Adapter

```
Core.start(adapter=WhatsAppPlaywrightAdapter())
  → adapter.connect()                  ← user's code boots the session

while running:
  messages = await adapter.fetch_new_messages()   ← user's code reads messages
  for msg in messages:
      result = await self.process(msg)            ← Core's routing pipeline
      if result.reply:
          await adapter.send_message(msg.user.id, result.reply)  ← user's code sends

await adapter.disconnect()             ← user's code tears down
```

---

### v1 Limitation — Single Adapter at Boot

> **v1 supports exactly one adapter at a time.**  
> The Core is instantiated with one `PlatformAdapter` object passed at startup.

This is an intentional simplification for Phase 4. It means:
- One WhatsApp session at a time
- No simultaneous Playwright + Baileys
- No runtime adapter switching

This is **acceptable for the initial build.** Multi-adapter concurrency is Phase 8 (Future Ideas).

The ABC contract is already designed for multi-adapter — adding it later is an `AdapterRegistry`
change in the Core, not a change to the ABC or any adapter pack.

---

### What We Build in Phase 4

| Item | Purpose |
|---|---|
| `src/adapters/loader.py` | `AdapterLoader` — finds pack by `adapter.yaml`, imports the entry class |
| `src/adapters/validator.py` | Validates `adapter.yaml` schema and that the class implements all ABC methods |
| `adapter_packs/whatsapp_playwright/adapter.yaml` | Pack descriptor |
| `adapter_packs/whatsapp_playwright/adapter.py` | Full `WhatsAppPlaywrightAdapter` implementation |

### What We Do NOT Build in Phase 4
- Baileys pack (ABC makes it trivial to add — defer to community or Phase 8)
- Multi-adapter registry (Phase 8 — Future Ideas)
- Business API pack (Phase 8)
- Webhook-based receive (adapter.yaml can declare `receive_mode: webhook` — future)

### Exit Criteria
- `AdapterLoader` validates and loads `adapter_packs/whatsapp_playwright/adapter.yaml`
- Core calls `connect()` → Playwright browser opens, WhatsApp Web loads
- Core calls `fetch_new_messages()` → at least one Message returned from DOM
- Handler runs, returns `CommandResult.reply`
- Core calls `send_message()` → reply appears in WhatsApp
- A **second mock adapter** (in-memory stubs, no Playwright) passes the same full loop test  
  proving the Core is not Playwright-coupled

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
| `src/modes/self_mode.py` | Autonomous polling loop — calls `adapter.fetch_new_messages()` on interval |
| `src/modes/coop_mode.py` | Human-in-the-loop — only executes commands on explicit approval |
| `src/modes/mode_manager.py` | Mode selection, lifecycle, graceful shutdown |

**Self Mode inner loop:**
```python
# self_mode.py — simplified
async def run(core: OmniKernal, adapter: PlatformAdapter, poll_interval: float = 1.0):
    await adapter.connect()
    while core.is_running:
        messages = await adapter.fetch_new_messages()
        for msg in messages:
            await core.process(msg, adapter)
        await asyncio.sleep(poll_interval)
    await adapter.disconnect()
```

The `core.process(msg, adapter)` method runs the full pipeline:  
sanitize → route → permission → watchdog → execute handler → send reply via adapter.

### What We Do NOT Build in Phase 6
- Business Mode (API-based, no UI) — **Future Ideas**
- Configurable poll interval per adapter — **Future Ideas**

### Exit Criteria
- Self mode runs a full loop: `fetch_new_messages` → sanitize → route → execute → `send_message`
- Co-op mode correctly holds execution, waits for human confirmation, then routes

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

## 11. Future Ideas (Explicitly Deferred)

> ⚠️ **These are NOT on the near-term roadmap.**  
> They are listed here so we don't accidentally build them early.  
> The current architecture is already designed to support most of these — they are deferred for simplicity, not impossibility.

### Adapter Layer — Future

| Idea | Why Deferred | How to Add When Ready |
|---|---|---|
| **Baileys Adapter Pack** | Phase 4 ABC must be stable first. Community can add independently. | New `adapter_packs/whatsapp_baileys/` folder + `adapter.py` implementing the same ABC. No Core changes. |
| **Multi-Adapter Registry** | v1 is single-adapter. Phase 5 profile isolation needed first. | Replace single `adapter` arg with `AdapterRegistry`. Core picks adapter by `platform_name`. |
| **Push/Enqueue Model** | Alternative to polling — adapter calls `core.enqueue(user, raw_text)` instead of Core polling `fetch_new_messages()`. More event-driven. Better for webhooks (e.g. Business API). | Expose `Core.enqueue()` public method. Adapter calls it from its own event listener. Core processes queue async. |
| **Webhook-based Receive** | Polling works for Playwright/Baileys. Webhooks needed for Business API. | `adapter.yaml` declares `receive_mode: webhook`. `AdapterLoader` wires up a FastAPI route. Core receives via `enqueue()`. |
| **Business API Adapter Pack** | Different execution model — no browser, pure HTTP. Needs webhook receive. | New adapter pack + webhook mode. No Core changes. |
| **Business Mode** | Requires Business API adapter + webhook server running. | Phase after Baileys and webhook support are stable. |

### Plugin Layer — Future

| Idea | Why Deferred | How to Add When Ready |
|---|---|---|
| **Plugin Hot-Reload** | Lazy import makes this possible — just clear the module from `sys.modules` and re-import. | Add `PluginExecutor.reload(plugin_name)` triggered by a `!reload <plugin>` admin command. |
| **Cross-Plugin Messaging** | Adds complexity without a clear v1 use case. | Define a `PluginBus` in Core — plugins post events, other plugins subscribe. Core mediates. |
| **Remote Plugin Registry / Marketplace** | Single-node registry sufficient through Phase 7. | Add a `registry.yaml` URL in `manifest.json`. `PluginLoader` fetches and verifies remote plugins. |
| **Rate Limiting Enforcement** | Declared in `permissions.json` from Phase 3 — enforcement deferred. | Add `RateLimiter` in Core using `execution_logs` timestamps. Enforced before `PluginExecutor`. |

### Infrastructure — Future

| Idea | Why Deferred | How to Add When Ready |
|---|---|---|
| **Redis Async Queue** | Only justified at 50+ concurrent users. SQLite handles single-node fine. | Replace in-memory execution queue with Redis streams. Core processes remain identical. |
| **Distributed Plugin Registry** | Single-node sufficient through Phase 7. | Postgres-backed registry + service discovery layer. |
| **Cross-Process Session Coordination** | One process per profile is sufficient for Phase 5-7. | Shared Redis lock instead of file-based lock. Core lock API unchanged. |
| **Horizontal Scaling** | Research validation (Phase 7) must justify it first. | Stateless Core behind a load balancer. DB is the shared state. |
| **Admin CLI** | Useful but not blocking. | `uv run omnikernal admin` — wraps `ApiHealthRepo.reactivate()`, plugin reload, status checks. |

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
| **Phase 8** | Future Ideas (Baileys, Multi-Adapter, Push Model, Marketplace) | ⚪ Deferred |

---

## 13. Architectural Invariants (Never Break These)

These rules must hold at every phase. Any PR that violates them should be rejected.

**Platform Adapter:**
1. **The Core never imports a platform SDK.** All platform interaction flows through `PlatformAdapter` ABC methods only.
2. **An Adapter Pack is the only place where SDK-specific code lives.** No `playwright`, `baileys`, or any SDK import may appear anywhere outside `adapter_packs/<name>/`.
3. **The Core validates `adapter.yaml` before loading any pack.** No blind dynamic imports.
4. **Handlers never call `send_message` directly.** They return `CommandResult.reply`. The Core pipes it through `adapter.send_message()`. Adapters stay decoupled from handler logic.
5. **v1 supports one adapter at boot.** Multi-adapter is a Future Idea — do not pre-build it.

**Plugin Layer:**
6. **The Core never imports a plugin's Python files to discover commands.** Discovery is YAML-only. Handler files are lazy-imported only on first execution.
7. **The Core never imports a plugin directly.** All plugin interaction flows through the loader + executor.
8. **Plugins cannot talk to each other.** No cross-plugin imports. No direct calls between handlers.
9. **Handlers access the DB only through `ctx.get_api_key()`.** No raw DB session in handler scope.

**Database & Security:**
10. **The Database is the single source of truth.** No file-based plugin/tool detection in production.
11. **No raw SQL strings outside `repository.py`.** All queries via SQLAlchemy ORM or `bindparams`. Enforced by lint rule + tests.
12. **All user-facing input passes through `CommandSanitizer` before parsing.** No raw message text reaches the router.
13. **API keys are never stored in plaintext.** Only Fernet ciphertext in DB. Decryption in Core scope only — never logged.
14. **Dead API threshold = 3 consecutive errors.** Quarantine is automatic. Reactivation is manual. No silent degradation.

**General:**
15. **Every execution is logged.** No silent failures.
16. **Profile isolation is OS-level.** Separate dirs, lock files, PIDs.
17. **Headless mode is automatic at ≥ 2 active profiles.**

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
│   │   ├── loader.py          ← AdapterLoader (loads pack from adapter.yaml)
│   │   └── validator.py       ← Validates adapter.yaml + checks ABC compliance
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
│   └── whatsapp_playwright/    ← Reference Pack (SDK: Playwright)
│       ├── adapter.yaml        ← name, platform, sdk, entry_class
│       └── adapter.py          ← WhatsAppPlaywrightAdapter(PlatformAdapter)
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

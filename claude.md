# OmniKernal — Agent Summary (Token-Optimised)
> Generated: 2026-03-06 | Status: Phase 0–6 implemented, Phase 7–8 deferred | Bugs fixed: 62
> Author: BITS-Rohit | Python ≥3.12 | uv-managed | MIT

---

## IDENTITY
Secure, DB-driven, multi-platform **bot automation microkernel**.
Not a bot script — a platform framework.
Core = 100% platform-agnostic. SDK lives ONLY in adapter_packs/.

---

## PHASE MAP
```
Ph0  Foundation & Contracts       ✅
Ph1  Microkernel Core Engine      ✅
Ph2  Database Layer               ✅
Ph2.5 Security & Resilience       ✅
Ph3  Plugin Layer (v1)            ✅
Ph4  Platform Adapter Layer       ✅ (scaffold)
Ph5  Profile Management           ✅
Ph6  Execution Modes (Self/Coop)  ✅
Ph7  Research & Benchmarking      🔄 (Comparative transport analysis)
Ph8  Future (Redis, multi-node)   ❌ deferred
```

---

## CORE INVARIANTS (NEVER BREAK)
1. Core never imports any platform SDK (playwright, baileys, etc.)
2. All platform I/O → only through PlatformAdapter ABC (4 methods)
3. Handlers never call `send_message()` → return `CommandResult.reply`; Core pipes it
4. No raw SQL outside `repository.py` (SQLAlchemy ORM only)
5. Plugin Python files never executed for discovery — YAML/JSON only
6. Handlers lazy-imported on first call (not on boot)
7. DB = only source of truth for plugins/tools/routing/logs
8. Encryption key never in DB; lives in `OMNIKERNAL_SECRET_KEY` env var

---

## DIRECTORY TREE
```
OmniKernal/
├─ src/
│  ├─ core/
│  │  ├─ engine.py          OmniKernal (main class, lifecycle)
│  │  ├─ dispatcher.py      EventDispatcher (route → execute)
│  │  ├─ parser.py          CommandParser (pattern → args dict)
│  │  ├─ router.py          CommandRouter (DB-backed lookup)
│  │  ├─ permissions.py     PermissionValidator (role check)
│  │  ├─ logger.py          core_logger (loguru wrapper)
│  │  ├─ loader.py          PluginEngine (discover & register)
│  │  ├─ contracts/
│  │  │  ├─ command_context.py   CommandContext (handler capability surface)
│  │  │  ├─ command_result.py    CommandResult (handler return type)
│  │  │  ├─ message.py           Message (frozen, adapter→core)
│  │  │  ├─ user.py              User (frozen, id/role/platform)
│  │  │  └─ plugin_manifest.py   PluginManifest (parsed manifest.json)
│  │  └─ interfaces/
│  │     ├─ platform_adapter.py  PlatformAdapter (ABC, 4 abstract methods)
│  │     ├─ base_plugin.py       BasePlugin (ABC, identity)
│  │     └─ base_command.py      BaseCommand (ABC, run signature)
│  ├─ database/
│  │  ├─ models.py       SQLAlchemy ORM: Plugin,Tool,RoutingRule,ExecutionLog,ApiHealth,DeadApi,ToolRequirement
│  │  ├─ repository.py   OmniRepository (ALL SQL encapsulated here)
│  │  └─ session.py      async engine factory, init_db()
│  ├─ security/
│  │  ├─ encryption.py   EncryptionEngine (Fernet, env key)
│  │  ├─ sanitizer.py    CommandSanitizer (strip shell metacharacters)
│  │  └─ watchdog.py     ApiWatchdog (failure tracking → quarantine)
│  ├─ profiles/
│  │  ├─ manager.py      ProfileManager (create/activate/deactivate)
│  │  ├─ lock.py         ProfileLock (PID-based, stale-lock cleanup)
│  │  └─ metadata.py     ProfileMetadata (encrypted metadata.json R/W)
│  ├─ modes/
│  │  ├─ mode_manager.py  ModeManager (self|coop lifecycle)
│  │  ├─ self_mode.py     SelfMode (autonomous polling loop)
│  │  └─ coop_mode.py     CoopMode (human-in-loop, approval queue)
│  └─ adapters/
│     ├─ loader.py        AdapterLoader (discover+load adapter packs)
│     └─ validator.py     AdapterValidator (descriptor + ABC check)
├─ adapter_packs/
│  ├─ console_mock/       ConsoleMockAdapter (in-memory, for tests/CI)
│  └─ whatsapp_playwright/ WhatsAppPlaywrightAdapter (scaffold, NotImplemented)
├─ plugins/
│  └─ echo/               Reference plugin (smoke test)
│     ├─ manifest.json
│     ├─ commands.yaml
│     └─ handlers/
├─ tests/                  pytest, asyncio_mode=auto
├─ benchmarks/             harness.py + bench_*.py
├─ DESIGN.md               1263-line architecture ADR
└─ pyproject.toml          uv, hatchling, ruff, mypy, pytest
```

---

## BOOT FLOW
```
OmniKernal.start(adapter, repository, profile_name, mode)
  → init_db()
  → ProfileManager.activate(profile_name)       # PID lock + headless resolve
  → PluginEngine.discover_and_load()            # scan plugins/, YAML only
  → adapter.connect()                           # user's code
  → ModeManager.start(mode, core, adapter)      # SelfMode or CoopMode task
  → _stop_event.wait()
  → stop() → ModeManager.stop() → adapter.disconnect() → ProfileManager.deactivate()
```

## MESSAGE PROCESSING PIPELINE
```
adapter.fetch_new_messages() → [Message]
  per msg:
    CommandSanitizer.sanitize(raw_text)    # strip ; & | ` $ ( ) etc.
    if not starts with "!" → skip
    EventDispatcher.dispatch(text, user)
      → router.get_route(trigger)          # Resolved via routing_rules (regex) then tools (exact)
      → if match → CommandParser.match(text, pattern)
      → if match → importlib.import_module(handler_path)
      → handler.run(args, CommandContext)
      → CommandResult
    repo.log_execution(...)                # immutable audit log
    if result.reply → adapter.send_message(user.id, reply)
```

---

## KEY CLASSES

### OmniKernal (engine.py)
```python
OmniKernal(adapter, repository, profile_name="main", profiles_dir="profiles", mode="self")
.start()   # full boot
.stop()    # graceful shutdown
.process(msg: Message)  # public pipeline entry (called by modes)
```

### CommandContext (contracts/command_context.py)
Handler-safe capability surface. Exposes ONLY:
- `ctx.user` — User who sent command
- `ctx.logger` — Scoped logger
- `await ctx.get_api_key(service)` — Decrypts via EncryptionEngine; never logged
No raw DB session. No adapter ref.

### CommandResult (contracts/command_result.py)
```python
CommandResult.success(reply="text")   # Core → adapter.send_message()
CommandResult.success(reply=None)     # No reply, Core skips send
CommandResult.error(reason="why")     # Logged, triggers watchdog path
```

### PlatformAdapter ABC (interfaces/platform_adapter.py)
4 abstract methods the Core calls:
```python
async connect() -> None
async fetch_new_messages() -> list[Message]
async send_message(to: str, content: str) -> None
async disconnect() -> None
@property platform_name -> str
```

### CommandRouter (core/router.py)
DB-backed route resolution. Resolution order:
1. `_rules_cache` (in-memory, loaded once from `routing_rules` table) — regex match via `re.fullmatch`. BUG 45 fix.
2. Exact `command_name` lookup in `tools` table.
Call `router.invalidate_route_cache()` after inserting a routing rule at runtime.

### OmniRepository (database/repository.py)
Single gateway for all DB. Key methods:
```python
register_plugin(name, version, author, description)  # BUG 52: preserves is_active
register_tool(command_name, pattern, handler_path, plugin_name, description)
get_tool_by_command(command_name) -> Tool | None
get_all_routing_rules() -> Sequence[RoutingRule]   # ordered by priority DESC
get_tool_by_id(tool_id) -> Tool | None
log_execution(user_id, platform, command_name, raw_input, success, ...)
increment_error(url, tool_id, error_msg) -> bool  # True if newly quarantined
reset_api_health(url)
get_api_key(tool_id) -> str | None  # returns ENCRYPTED value
is_api_healthy(url) -> bool
```

### DB Models (database/models.py)
| Table | PK | Notes |
|---|---|---|
| plugins | name (str) | manifest.json source |
| tools | id (int) | commands.yaml source, unique command_name |
| routing_rules | id (int) | custom regex overrides |
| execution_logs | id (int) | immutable audit trail |
| api_health | url (str) | consecutive_failures, is_quarantined |
| dead_apis | id (int) | quarantine history, reactivated flag |
| tool_requirements | id (int) | ENCRYPTED api_key_value |

### EncryptionEngine (security/encryption.py)
```python
EncryptionEngine.encrypt(plaintext: str) -> str   # Fernet
EncryptionEngine.decrypt(ciphertext: str) -> str
# Key from OMNIKERNAL_SECRET_KEY env var; auto-generates dev key if missing (warn)
```

### CommandSanitizer (security/sanitizer.py)
Strips: `; & | \` $ ( ) [ ] { } < > \n \r` then collapses spaces.
Called BEFORE parser. Allowlist-based — unrecognised input rejected.

### ApiWatchdog (security/watchdog.py)
```python
await watchdog.record_failure(api_url, tool_id, error_msg)  # ≥3 → quarantine
await watchdog.record_success(api_url)                       # resets count
await watchdog.is_dead(api_url) -> bool
# Quarantine threshold: 3 consecutive failures → dead_apis insert, tool disabled
# Reactivation: manual only (ApiHealthRepo.reactivate)
```

### ProfileManager (profiles/manager.py)
```python
ProfileManager(profiles_dir="profiles")
.create(name, platform)     # mkdir + metadata.json
.activate(name) -> dict     # PID lock + force_headless if ≥2 active
.deactivate(name)           # release lock
.list_profiles() -> list[str]
.should_force_headless() -> bool  # True if lock.get_active_count() >= 2
```

### ProfileLock (profiles/lock.py)
PID-based `lock.pid` files. Stale locks auto-cleared. Uses `os.O_EXCL` for atomic creation.

### ProfileMetadata (profiles/metadata.py)
R/W `metadata.json`. `SENSITIVE_FIELDS={"session_data"}` → Fernet-encrypted at rest.
Schema: `{name, platform, created_at, headless, session_data}`

### ModeManager (modes/mode_manager.py)
```python
await manager.start(mode_name, core, adapter, poll_interval=1.0)
await manager.stop()
manager.active_mode  # "self" | "coop" | None
```

### SelfMode (modes/self_mode.py)
Autonomous: `while core.is_running: fetch → process → sleep(poll_interval)`

### CoopMode (modes/coop_mode.py)
Human-in-loop: messages queued in `_pending`. Async `approve(msg_id)` / `reject(msg_id)`.
Each message gets its own asyncio.Event. Approved → `core.process()`.

---

## PLUGIN CONTRACT (LOCKED STRUCTURE)
```
plugins/<name>/
  manifest.json       {name, version, author, description, platform[], min_core_version}
  commands.yaml       {commands: {cmd: {description, pattern, handler, requires_api, args[]}}}
  permissions.json    {cmd: {allowed_roles[], blocked_users[], rate_limit}}
  handlers/
    <cmd>.py          async def run(args: dict[str,str], ctx: CommandContext) -> CommandResult
```
Handler path in commands.yaml = dotted Python path relative to plugin root.
Core reads YAML to register; **never imports handlers on boot** (lazy only).

---

## ADAPTER PACK CONTRACT
```
adapter_packs/<name>/
  adapter.yaml    {name, platform, version, entry_class: "module.ClassName"}
  adapter.py      class <Name>(PlatformAdapter): ...
```
AdapterLoader validates adapter.yaml schema, dynamically imports entry_class, validates ABC compliance, returns instance.

---

## SECURITY SUMMARY
| Vector | Mechanism |
|---|---|
| SQL injection | ORM-only (no raw SQL outside repo); sanitizer pre-validates |
| Command/shell injection | CommandSanitizer strips metacharacters before parser |
| API key at rest | Fernet encrypted in DB; decrypted only in handler scope |
| Profile session data | Fernet encrypted in metadata.json |
| Dead APIs | ApiWatchdog: 3 failures → quarantine; manual reactivation only |
| Plugin isolation | Handlers lazy-imported; no cross-plugin imports; no raw DB session |

---

## TOOLCHAIN
```
uv          package manager (pyproject.toml)
ruff        linter + formatter (line-length=100, py312, no raw SQL rule)
mypy        strict type checking
pytest      asyncio_mode=auto, cov=src
loguru      structured logging (core_logger.bind(subsystem=..., profile=...))
SQLAlchemy  2.x async ORM (aiosqlite default, swappable via DATABASE_URL env)
Fernet      symmetric encryption (cryptography package)
```

---

## ENV VARS
| Var | Purpose | Default |
|---|---|---|
| `OMNIKERNAL_SECRET_KEY` | Fernet master key | Auto-generates dev key, persists to `.dev.key` (warns; use in dev only) |
| `OMNIKERNAL_STRICT_KEY` | Raise immediately if key is missing | `""` (disabled) |
| `DATABASE_URL` | DB connection string | `sqlite+aiosqlite:///omnikernal.db` |
| `OMNIKERNAL_ADMINS` | Comma-separated platform IDs elevated to admin | `""` (empty, none) |
| `SQLALCHEMY_ECHO` | Enable SQL query logging | `""` (disabled) |

---

## REFERENCE PLUGIN: echo
```yaml
# plugins/echo/commands.yaml
commands:
  echo:
    description: "Echo back the input text"
    pattern: "!echo <text>"
    handler: "handlers.echo.run"
    requires_api: false
    args:
      - {name: text, type: str, required: true}
```
```python
# plugins/echo/handlers/echo.py
async def run(args, ctx): return CommandResult.success(reply=args["text"])
```

---

## KNOWN LIMITATIONS & DESIGN DEBT
- **Multi-key API (BUG 55 deferred):** `ctx.get_api_key(service)` looks up only the single key stored per `tool_id`. Supporting multiple distinct API keys per tool (e.g. a tool that calls both YouTube and OpenAI) is a Phase 8 design task.
- **Lock Cleanup (BUG 61 ✅ fixed):** `ProfileLock.is_locked` now calls `os.remove` directly for stale locks from dead processes, bypassing ownership check in `release()`.

## RESEARCH & ANALYSIS PROTOCOL
To maintain architectural evaluation integrity across sessions:
1. **Raw Data:** Save metrics (latency, RAM) to `benchmarks/results_matrix.json`.
2. **Analysis:** Document comparative findings in `docs/research/comparative_analysis.md`.
3. **Intent:** Evaluates **UI-based (Playwright)** vs **API-based (WAHA)** vs **Socket-based (Baileys)**.

## WHAT IS NOT YET BUILT
- WhatsApp Playwright adapter logic (Finalizing high-level mapping)
- WAHA (HTTP API) adapter pack (Phase 7 Research Target)
- Baileys (Socket) adapter pack (Phase 7 Research Target)
- Comparative Performance Matrix (Phase 7 Research)
- Rate limiting enforcement (declared in `permissions.json`, not wired)
- Named services in `ctx.get_api_key(service)` (BUG 55 — currently ignores `service` arg)
- Hot-reload of plugins
- Admin CLI (Phase 7+)
- Redis / distributed cache (Phase 8)
- Multi-node DB coordination (Phase 8)
- OAuth / token rotation (Phase 8)
- Plugin marketplace (Phase 8)
- Webhook receive mode (Phase 8)
- Automated API reactivation (intentionally deferred)

Scope: Only `src/` and `adapter/` are allowed. `tests/` and `docs/` are strictly out of scope. Access `Profiles/` or `benchmarks/` only after explicit approval with clear intent.
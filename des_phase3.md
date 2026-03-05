# PR Title: Phase 3 — Declarative Plugin Discovery & Microkernel Integration

## Summary
This phase transitions the OmniKernal from manual stubs to a fully declarative **Plugin Discovery System** AND fully implements the **Phase 2.5 Security & Resilience Layer**. The Core now automatically scans the `plugins/` directory, validates manifests, and populates the database routing table on boot while securing external tool calls with an API Watchdog, input sanitizer, and encryption engine.

## Key Changes

### 1. PluginEngine (The "Real" Loader)
- Implemented `PluginEngine` in `src/core/loader.py` to replace the Phase 2 `MinimalLoader`.
- **Atomic Discovery**: Scans `plugins/` for `manifest.json` and `commands.yaml`.
- **Database Synchronization**: Automatically registers plugins and their tools/commands into the SQLAlchemy repository during the boot sequence.

### 2. Standardized Plugin Structure
- Established and locked the atomic directory standard:
  ```text
  plugins/
    <name>/
      |- manifest.json  (Identity)
      |- commands.yaml  (Routing & Schemas)
      |- handlers/      (Execution Logic)
  ```
- Created a reference `echo` plugin to verify the structure.

### 3. Core Engine Refinement (Microkernel Loop)
- Integrated discovery into the `OmniKernal` boot sequence.
- **Lazy Loading**: The `EventDispatcher` now follows the dotted path in `commands.yaml` to dynamically import handlers only when triggered.
- **Bug Fixes**: Resolved property name mismatches (`result.ok` vs `result.success`) and fixed `UnicodeEncodeError` on Windows consoles by switching logs to ASCII-safe symbols.

### 4. Code Quality & Type Safety
- Addressed project admin feedback by replacing `| None` with `Optional[T]` across all contracts.
- Improved abstract base classes to raise `NotImplementedError` for missing properties.
- Introduced `TYPE_CHECKING` blocks in core modules to prevent future circular imports.

### 5. Phase 2.5 — Security & Resilience Layer
- **Encryption Engine (`src/security/encryption.py`)**: Fernet-based symmetric encryption for sensitive data at rest. Handlers automatically receive plaintext keys via `CommandContext.get_api_key(service)`. DB only stores ciphertexts.
- **Injection Prevention (`src/security/sanitizer.py`)**: `CommandSanitizer` rigorously strips shell metacharacters and prevents command chaining or new-line injections.
- **Dead API Watchdog (`src/security/watchdog.py`)**: Real-time health tracking mapped via SQLAlchemy models (`ApiHealth`, `DeadApi`). Automatically quarantines APIs that hit an error threshold (e.g. 3 consecutive failures), shielding the system from cascading blocks.
- **Test Coverage (`tests/security/`)**: Full fuzzing suites written for injection prevention, roundtrip encryption assertions, and full-loop Watchdog quarantine/recovery flow tests.

## Verification Results
Passed the updated `smoke_test.py` with the following sequence:
1. Engine Boot -> SQL Schema Init.
2. Discovery -> Scanned `plugins/echo` -> DB Tool Registration.
3. Execution -> Simulated `!echo` -> Dynamic Import -> Audit Log in DB.
4. Output -> `[PASS] SMOKE TEST PASSED`.

## Dependencies
- Synced `pyproject.toml` and `requirements.txt`.
- Added `asyncio-mqtt` to core dependencies.

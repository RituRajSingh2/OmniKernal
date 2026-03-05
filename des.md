# PR Description: Phase 0 ΓÇö Foundation & Contracts (Synced & Resolved)

## Summary
This Pull Request implements **Phase 0** of the OmniKernal project, establishing the architectural foundation and core data contracts. This phase focused on defining the "shapes" of the microkernel without introducing platform-specific logic.

**Note:** This branch has been synchronized with the latest `upstream/main`. All conflicts in `pyproject.toml` have been resolved, and the branch is now fully aligned with the updated `DESIGN.md`.

## Proposed Changes

### 1. Structural Scaffolding
- **`pyproject.toml`**: Fully updated with core dependencies (`loguru`, `cryptography`, `sqlalchemy`, etc.) and development tooling (`pytest`, `ruff`, `mypy`). Configured for `hatchling` build-backend and `uv` dev-environment.
- **Package Hierarchy**: Established the `src/core/interfaces` and `src/core/contracts` hierarchy.

### 2. Core Abstract Interfaces (ABCs)
Defined in `src/core/interfaces/` to ensure platform agnosticism:
- **`PlatformAdapter`**: Standard hook for platform modules (WhatsApp, etc.).
- **`BasePlugin`**: Identity contract for plugin discovery.
- **`BaseCommand`**: Execution contract for all command handlers.

### 3. Immutable Data Contracts
Implemented in `src/core/contracts/` to standardize data flow:
- **`User` & `Message`**: Frozen dataclasses representing inbound data.
- **`PluginManifest` & `RoutingRule`**: Structures for the plugin registry.
- **`CommandContext` & `CommandResult`**: The standardized "Surface Area" for handler execution.

### 4. Verification & Testing
- Integrated **`pytest`** with stubs in `tests/` to verify ABC enforcement and contract immutability.
- Branch handles all current linter (`ruff`) and type-checking (`mypy`) requirements.

## Reviewer Feedback Implementation
- Updated branch to include the latest `design.md` from `main`.
- Manually merged and reconciled `pyproject.toml` to ensure no metadata or dependencies were lost during the upstream sync.
- Verified that all contracts are "Frozen" and "Immutable" as per the microkernel spec.

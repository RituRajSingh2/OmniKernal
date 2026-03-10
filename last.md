# OmniKernal — Current Branch State & Handoff

## 1. Previous Work (Phase 1-6 Hardening & Typings)
*   **Security & Concurrency Fixed:** Resolved 130+ bugs including PID lock-hijacking, atomic SQL increments, path traversal, shell injection, and case-insensitive role elevation.
*   **Typing & Linting:** Tuned MyPy/Ruff config, fixed exception chaining (`B904`), and added `deptry` to `pyproject.toml`. 
*   **Missing Typings (To-Do):** `src/core/engine.py:139` (ModeManager explicit Literal), `response_time_ms` expected as `int|None`.

## 2. Current Focus: Phase 7 Comparative Research 
We have initiated the **Phase 7 Architectural Evaluation**, measuring the microkernel against 3 transport modes:
1.  **UI-Based (Playwright)** → `adapter_packs/whatsapp_playwright/`
2.  **API-Based (WAHA)** → `adapter_packs/whatsapp_waha/`
3.  **Socket-Based (Baileys)** → `adapter_packs/whatsapp_baileys/`

*Data will be saved to `benchmarks/results_matrix.json` and analyzed in `docs/research/comparative_analysis.md`.*

## 3. Immediate Next Steps (Playwright & WhatsPlay)
We are currently building the first adapter: **WhatsApp Playwright via the `whatsplay` Python library**.
*   [x] Installed `whatsplay`, `playwright`, `numpy`, `opencv-python`.
*   [x] Explored `whatsplay.Client` API (has `start()`, `wait_until_logged_in()`, `collect_messages()`, `send_message()`).
*   [ ] **Pending:** Implement `WhatsAppPlaywrightAdapter` in `adapter_packs/whatsapp_playwright/adapter.py`.
*   [ ] **Pending:** Verify login and connection success.
*   [ ] **Pending:** Build a basic test plugin (e.g., `!sys plugins` to list plugins) to verify end-to-end command routing from WhatsApp UI → Core → WhatsApp UI.

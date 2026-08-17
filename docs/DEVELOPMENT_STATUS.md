# Development Status

## Current Stage

Stage 04 — Concept, Prompt, Report & Final Frontend (complete)

## Completed

- Stage 01 Foundation: FastAPI, SQLite/Alembic, core task/content/configuration models, adapter contracts, and Vue research-workbench foundation.
- Baseline validation: `uv run pytest` (6 passed) and `npm run build` completed on 2026-08-13.
- Stage 02 Collection: configurable Query Expansion, public-page Playwright adapter, generic platform registry, SQLite content/snapshot/media persistence, task execution APIs, and collection UI.
- Stage 03 Ranking & AI Analysis: Hot/Rising and metric boards, snapshot velocity, structured text/visual/content analysis, aggregated trends, persisted analysis records, and analysis workspace tabs.
- Stage 04 Concept, Prompt, Report & Final Frontend: persisted multi-source Creative Concepts, text-only image Prompts, Markdown/JSON research reports, report exports, final task-detail tabs, and report-default/template configuration.
- Model Gateway hardening: business services now submit provider-neutral `ModelRequest`s to `ModelGateway`; configured protocol adapters handle OpenAI Responses/Chat, Anthropic Messages, Gemini and Ollama. Provider settings persist protocol, declared capabilities and priority, with retry-safe cross-provider fallback.
- Task-level analysis: the agent selects bounded, read-only evidence tools and persists one model-authored synthesis per task. Analysis/trend GET endpoints are read-only; content-level AI loops are no longer on the runtime path. Re-running a synthesis invalidates derived Concepts, Prompts and reports so they rebuild from current evidence.
- Collection reliability: browser page timeout defaults to 120 seconds (with a migration for prior 30-second SQLite settings); long-running collection/model requests have explicit frontend budgets. Query expansion now validates the category contract, performs one repair for malformed or echo-only model output, and uses a logged local fallback only if the provider still cannot expand. Valid expansion results are persisted and reused only when the same task is run again.
- Vision-media reliability: downloaded public media and legacy `.bin` files are sniffed for JPEG/PNG/GIF/WebP bytes before a vision request. Unsupported bytes are retained out of the vision path with a clear local error instead of being sent as `application/octet-stream`.
- Windows portable release: a PyInstaller distribution bundles the Vue workspace, FastAPI service, Alembic migrations and Playwright Chromium. It opens locally on `127.0.0.1`, stores user state under `%LOCALAPPDATA%\\TrendScope`, and seeds a sanitized initial snapshot without AI Provider configuration or browser authentication headers.
- macOS portable release: a matching PyInstaller `.app` script uses `~/Library/Application Support/TrendScope` for user state and the same sanitized initial snapshot.

## In Progress

- No active implementation work. Version 1 workflow is complete.

## Tests

- Final backend tests: 53 passed.
- Alembic upgrade to `0009_browser_timeout_default`: passed.
- Final frontend production build: passed.
- Portable EXE smoke test: `TrendScope.exe` started successfully and `/health` returned `ok` on 2026-08-15.

## Known Limitations

- Live collection requires the separately installed Playwright Chromium runtime: `uv run playwright install chromium`.
- Collection is intentionally limited to publicly visible HTTP(S) pages; authentication, CAPTCHA, verification and access restrictions are recorded without bypass attempts.
- No enabled, complete LLM/Vision configuration falls back to deterministic Mock providers for offline use. A configured model that lacks a required capability is reported as an analysis error rather than silently routed to an incompatible model.
- Reports are generated locally under `reports/{task_id}/`; the system outputs prompts only and does not invoke any image-generation or publishing API.

## Git Commit

- `34fb147 feat: initialize content trend agent`
- `cd0bc7d feat: add configurable collection pipeline`
- `24786f1 feat: add ranking and ai analysis`
- `feat: complete content trend research workflow` (Stage 04)

## Next Step

Version 1 is ready for local use. Future work can add concrete vendor Provider implementations and additional platform-specific public-page adapters without changing the core workflow.

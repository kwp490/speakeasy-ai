# Changelog

All notable changes to SpeakEasy AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - ASR Throughput Instrumentation & Sparkline Enhancements

### Added
- **ASR throughput section** in Developer Panel Realtime tab: displays realtime factor, decoder token rate, total tokens, and total audio processed from the Cohere engine
- **ASR sparkline**: plots realtime factor over time with a 1.0x reference line; uses sticky-max scaling to prevent visual creep during CUDA warm-up
- **Engine instrumentation** (`CohereTranscribeEngine`): tracks per-chunk throughput counters (`token_stats` property) including inference sequence number for sparkline deduplication
- **LLM call sequence tracking** (`TextProcessor`): `token_stats` now returns a monotonic `call_seq` counter for consistent sparkline updates
- **Parallel test execution**: added `pytest-xdist` dev dependency; build script now runs `pytest -n auto`
- **Session-scoped QApplication fixture** in `conftest.py` for xdist worker isolation

### Changed
- **TokenSparkline** widget overhauled: sticky-max Y-axis scaling, configurable value units/format, optional horizontal reference line, current/max text overlay, border frame, and "awaiting samples" placeholder state
- **RealtimeDataWidget**: replaced audio input-level meter with dedicated ASR Throughput and LLM Throughput sections; both sparklines use spike-and-zero semantics with sequence-based deduplication
- **Main window resource monitor**: now forwards both ASR and LLM token stats to the Developer Panel on each poll tick; pushes engine state to panel on first open
- **Inno Setup**: added `LZMANumBlockThreads=8` for faster fast-compression dev builds

---

## [0.6.0] - Developer Panel & UI Overhaul

### Added
- **Developer Panel**: Snappable side window (toggle with **Ctrl+Alt+D**) with four tabs:
  - **Settings** — quick access to engine, audio, and UX settings via reusable `SettingsWidget`
  - **Realtime** — live engine status, RAM/VRAM progress bars, GPU metrics, and token throughput sparkline
  - **Logs** — scrollable read-only application log viewer with clear and copy buttons (500-block rolling buffer)
  - **Pro Mode** — embedded Professional Mode configuration (API key, presets, vocabulary)
- **Design token system** (`theme.py`): single source of truth for colors, typography, spacing, and stylesheet helpers
- **`RealtimeDataWidget`**: live engine monitoring with RAM/VRAM usage, GPU temperature/utilization, and reload/validate actions
- **`TokenSparkline`**: custom-painted line chart for real-time token throughput visualization
- **`LogsWidget`**: application log display with real-time streaming from `QtLogHandler`
- **`ProModeWidget`**: embeddable Professional Mode UI for API key, preset, and instruction management
- Six new developer panel settings: `dev_panel_open`, `dev_panel_active_tab`, `dev_panel_width`, `dev_panel_height`, `dev_panel_snapped`, `hotkey_dev_panel`
- Dev dependencies: `pytest-qt`, `pytest-cov`, `pytest-mock`
- Comprehensive test suite for Developer Panel, RealtimeDataWidget, TokenSparkline, LogsWidget, ProModeWidget, and SettingsWidget

### Changed
- **Settings Dialog**: simplified by extracting Professional Mode section into dedicated `ProSettingsDialog`; now focuses on engine, audio, and UX settings
- **Hotkey system**: added Developer Panel toggle hotkey (Ctrl+Alt+D) with `dev_panel_toggle_requested` signal
- **Main window**: refactored to manage Developer Panel lifecycle, snapping behavior, and state persistence

---

## [0.5.1] - Per-User Logs & Hardening

### Changed
- **Per-user log directory**: Logs now write to `%LOCALAPPDATA%\SpeakEasy AI\logs`
  instead of the shared `%ProgramData%` path, preventing cross-user log access
  on shared machines. Dev/source mode (`SPEAKEASY_HOME`) is unchanged.
- **Audio resampling**: Replaced manual linear-interpolation resampler with
  `librosa.resample()` for higher-quality sample-rate conversion.

### Security
- **HuggingFace token masking**: The model-download token dialog now uses
  password echo mode so the token is not visible on screen.
- **Dependency auditing**: CI workflow runs `pip-audit --strict` on every push
  and PR to catch known-vulnerable dependencies.
- **Dependabot**: Automated weekly dependency update PRs for pip packages and
  GitHub Actions.

### Added
- **`RELEASE.md`**: Step-by-step release checklist (version bump → tag → publish).
- **`.github/dependabot.yml`**: Automated dependency update configuration.
- **`pip-audit`** added to dev dependencies.

### Removed
- Installer no longer creates or manages a shared `logs/` directory under
  `%ProgramData%\SpeakEasy AI` — log storage is now per-user.

---

## [0.5.0] - Streaming Partials

### Added
- **Live-draft transcription**: long recordings (>30 s) now stream each internal
  transcription chunk into the history pane as soon as it is ready, instead of
  showing nothing until the entire recording has been transcribed. The draft
  entry is updated in place and replaced by the authoritative stitched text
  once the final chunk completes. Clipboard and auto-paste still fire exactly
  once, on the final result. Controlled by the new
  `streaming_partials_enabled` setting (default on; toggle in Settings)
- **`SpeechEngine` partial-callback contract**: `transcribe()` / `_transcribe_impl()`
  accept an optional `partial_callback(text, chunk_index, total_chunks)` which
  the Cohere engine invokes after each chunk of a multi-chunk transcription;
  callback exceptions are logged and swallowed
- **`WorkerSignals.partial(str, int, int)`** signal for routing per-chunk
  updates from the engine worker to the UI thread via `Qt.QueuedConnection`

---

## [0.4.0] - RegisterHotKey & Privacy Disclosure

### Changed
- **Hotkey system rewrite**: Replaced the `keyboard` library (low-level `SetWindowsHookEx`
  hook) with the Win32 `RegisterHotKey` API — only the configured chord is delivered to the
  application; no global keyboard hook is installed
- **Auto-paste rewrite**: `simulate_paste()` now uses Win32 `keybd_event` instead of
  `keyboard.send()`, removing the last `keyboard` library dependency
- **Dependency removed**: `keyboard` package removed from `pyproject.toml`

### Added
- **Professional Mode data-privacy disclosure**: One-time dialog warns users that
  transcribed text is transmitted to `api.openai.com` under their personal API key
  before Professional Mode can be enabled (shown in both the main window toggle and
  the Pro Settings dialog)
- **`pro_disclosure_accepted`** setting persisted so the notice is shown only once

### Security
- **SECURITY.md** updated to reflect the new hotkey mechanism and corrected log/data paths
- **README.md** adds a data-privacy callout in the Professional Mode section

---

## [0.3.3] - Permission Fix

### Fixed
- **Log directory permissions**: Installer now grants the `Users` group write access
  to all `C:\ProgramData\SpeakEasy AI` subdirectories (`logs`, `config`, `temp`, `models`),
  fixing a `PermissionError: [Errno 13]` crash on first launch for standard (non-admin) accounts
- **Logging fallback**: App no longer crashes if the log file is unwritable; falls back to
  console-only logging so the application always starts

---

## [0.3.1] - CPU Build Fix

### Fixed
- **CPU build variant patching**: Moved `_build_variant.py` restore in `speakeasy-cpu.spec` from after `Analysis()` to after `PYZ()` so the frozen CPU build correctly has `VARIANT = "cpu"`
- **Settings dialog CUDA guard**: CPU edition now shows both device options in the dropdown but blocks CUDA selection with an inline warning and disables the OK button, preventing users from saving an invalid device setting

### Added
- **CPU build variant** (`speakeasy-cpu.spec`, `speakeasy-cpu-setup.iss`): smaller installer without CUDA/GPU dependencies
- **Build installer script**: `Install-SpeakEasy-Source.ps1` for automated source installs with GPU/CPU variant support
- **Copilot instructions**: `.github/copilot-instructions.md` for AI-assisted development

### Changed
- **Build system**: RAM disk acceleration (via [AIM Toolkit](https://sourceforge.net/projects/aim-toolkit/)), source-hash caching, and improved build pipeline
- **GPU monitor**: CPU variant gracefully skips GPU metrics

---

## [0.3.0] - Cohere-Only Release

### Changed
- **Single engine**: Replaced dual-engine architecture with Cohere Transcribe 03-2026 as the sole speech engine
- **HuggingFace token**: Installation now prompts for a HuggingFace API token (required for gated model access)
- **Punctuation control**: New setting replaces the legacy keywords field — toggle automatic punctuation on/off
- **Simplified settings**: Removed engine selection dropdown, streamlined UI
- **Language dropdown**: Settings now shows all 14 Cohere-supported languages in a dropdown

### Removed
- **Previous secondary speech engine** and all related code
- **Keywords** setting (replaced by punctuation toggle)
- **Engine selection** UI (single engine, no choice needed)

---

## [0.1.0] - Initial Release

### Added
- **Secondary compact speech engine** — 1B-parameter model, ~3 GB VRAM, 7 languages
- **Cohere Transcribe 03-2026** engine — high-accuracy 2B-parameter model, ~5 GB VRAM, 14 languages
- Both engines run via HuggingFace `transformers` — single-process, no subprocess bridge
- Automatic model download from HuggingFace Hub
- PySide6 (Qt) GUI with real-time resource monitoring (RAM, VRAM, GPU temperature)
- Global hotkeys (start/stop recording, quit) with sleep/wake recovery
- Auto-paste transcribed text into the active window
- Professional Mode with AI-powered text cleanup via OpenAI API
  - 5 built-in presets + custom presets
  - Domain vocabulary preservation
  - Per-preset model selection and custom system prompts
- Microphone device selection
- Single-instance guard (system mutex)
- PyInstaller binary distribution + Inno Setup installer
- Source install via `uv` + automated `Install-SpeakEasy-Source.ps1`
- Windows Defender exclusion configuration

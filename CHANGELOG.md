# Changelog

All notable changes to SpeakEasy AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

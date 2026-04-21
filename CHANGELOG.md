# Changelog

All notable changes to dictat0r.AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - CPU Build Fix

### Fixed
- **CPU build variant patching**: Moved `_build_variant.py` restore in `dictator-cpu.spec` from after `Analysis()` to after `PYZ()` so the frozen CPU build correctly has `VARIANT = "cpu"`
- **Settings dialog CUDA guard**: CPU edition now shows both device options in the dropdown but blocks CUDA selection with an inline warning and disables the OK button, preventing users from saving an invalid device setting

### Added
- **CPU build variant** (`dictator-cpu.spec`, `dictator-cpu-setup.iss`): smaller installer without CUDA/GPU dependencies
- **Build installer script**: `Install-Dictator-Source.ps1` for automated source installs with GPU/CPU variant support
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
- Source install via `uv` + automated `Install-Dictator-Source.ps1`
- Windows Defender exclusion configuration

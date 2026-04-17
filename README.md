# dictat0r.AI — Native Windows Voice-to-Text

**Real-time speech transcription on Windows using NVIDIA GPUs.**

Press a hotkey, speak, and your transcribed text is pasted into the active window. GPU-accelerated, runs natively — no setup complexity.

## Getting Started

There are two ways to install dictat0r.AI: download the pre-built installer (recommended), or build from source.

**Requirements (both methods):** Windows 10/11 (64-bit), [HuggingFace account](https://huggingface.co/join) with access to [CohereLabs/cohere-transcribe-03-2026](https://huggingface.co/CohereLabs/cohere-transcribe-03-2026). An NVIDIA GPU (RTX 30-series or newer, 6+ GB VRAM, Driver 525+) is recommended for fast inference but not required — the app can run on CPU (slower).

### Option 1 — Installer (recommended)

Download **[dictator-AI-Setup-0.3.0.exe](https://github.com/kwp490/dictat0rAI-v3/releases/download/v0.3.0/dictator-AI-Setup-0.3.0.exe)** from the [Releases](https://github.com/kwp490/dictat0rAI-v3/releases/latest) page.

Double-click the installer and follow the prompts. No Python, no command line required. The installer will:

1. Extract application files to `C:\Program Files\dictat0r.AI`
2. Prompt for your HuggingFace API token (required for gated model access)
3. Download the Cohere Transcribe speech model from HuggingFace
4. Create desktop and Start Menu shortcuts
5. Configure Windows Defender exclusions

### Option 2 — Run from source

For developers or users who prefer to build and run from source. Requires [Git](https://git-scm.com/downloads/win) and [uv](https://docs.astral.sh/uv/) (installed in step 1 below).

```powershell
# 1. Install uv (Python package manager)
irm https://astral.sh/uv/install.ps1 | iex

# 2. Clone and install dependencies
git clone https://github.com/kwp490/dictat0rAI-v3.git
cd dictat0rAI-v3
uv sync

# 3. Download the model and launch
uv run dictator download-model --token YOUR_HF_TOKEN
uv run dictator
```

Or use the automated source installer (requires admin):

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\installer\Install-Dictator-Source.ps1
```

## Features

- **Cohere Transcribe 03-2026**: High-accuracy 2B-parameter ASR model, 14 languages, ~5 GB VRAM
- **Professional Mode**: AI-powered text cleanup via OpenAI API with a preset system — 5 built-in presets, custom presets, domain vocabulary preservation, and per-preset model selection
- **Punctuation control**: Enable or disable automatic punctuation in transcription output
- **Global hotkeys**: Start/stop recording from any application (configurable bindings)
- **Auto-paste**: Transcribed text goes directly to your active window
- **GPU-accelerated**: Leverages NVIDIA CUDA for fast inference
- **Microphone selection**: Choose a specific input device or use the system default
- **Sleep/wake recovery**: Hotkeys automatically re-register after Windows resume from sleep
- **Single-instance guard**: Prevents multiple dictat0r.AI processes from running simultaneously
- **Real-time resource monitoring**: RAM, VRAM, and GPU temperature displayed in the diagnostics panel
- **Audio feedback**: Beep tones on recording start/stop
- **Runs natively on Windows** — single installer, no dependencies

## Settings

| Setting              | Default                                | Description                                      |
| -------------------- | -------------------------------------- | ------------------------------------------------ |
| `engine`             | `cohere`                               | Speech engine (Cohere Transcribe)                |
| `model_path`         | `C:\Program Files\dictat0r.AI\models` | Directory for model weights                      |
| `device`             | `cuda`                                 | Inference device: `cuda` or `cpu`                |
| `language`           | `en`                                   | Language code                                    |
| `punctuation`        | `true`                                 | Enable automatic punctuation in transcription    |
| `inference_timeout`  | `30`                                   | Max seconds per transcription                    |
| `auto_copy`          | `true`                                 | Auto-copy transcription to clipboard             |
| `auto_paste`         | `true`                                 | Auto-paste via Ctrl+V after transcription        |
| `hotkeys_enabled`    | `true`                                 | Master toggle for global hotkeys                 |
| `hotkey_start`       | `ctrl+alt+p`                           | Start-recording hotkey                           |
| `hotkey_stop`        | `ctrl+alt+l`                           | Stop/transcribe hotkey                           |
| `hotkey_quit`        | `ctrl+alt+q`                           | Quit application hotkey                          |
| `clear_logs_on_exit` | `true`                                 | Clear log files when the application exits       |
| `mic_device_index`   | `-1`                                   | Microphone device index (`-1` = system default)  |
| `sample_rate`        | `16000`                                | Recording sample rate (Hz) - resampled to 16 kHz |
| `silence_threshold`  | `0.0015`                               | RMS threshold for silence detection              |
| `silence_margin_ms`  | `500`                                  | Silence margin (ms) added around voiced regions  |
| `professional_mode`  | `false`                                | Enable AI text cleanup (requires OpenAI API key) |
| `pro_active_preset`  | `General Professional`                 | Active Professional Mode preset name             |
| `store_api_key`      | `false`                                | Persist API key in Windows Credential Manager    |

Settings are stored at `C:\Program Files\dictat0r.AI\config\settings.json`.

> **Note:** The OpenAI API key is **never** stored in `settings.json`. It is held in memory only, unless you enable "Remember API key", which saves it securely via Windows Credential Manager (DPAPI).

## Hotkeys

| Hotkey (default)     | Action                               |
| -------------------- | ------------------------------------ |
| `Ctrl+Alt+P`         | Start recording                      |
| `Ctrl+Alt+L`         | Stop recording & transcribe          |
| `Ctrl+Alt+Q`         | Quit application                     |

All hotkey bindings are configurable in Settings. Hotkeys can also be disabled entirely via the `hotkeys_enabled` toggle. After Windows resumes from sleep, hotkeys are automatically re-registered.

## Professional Mode

Optional AI-powered post-processing that cleans up your dictated text before it reaches the clipboard. Configure it via the **Professional Mode Settings** button in the main window.

**What it does:**
- **Fix tone** — rewrites emotional, aggressive, or unprofessional language while preserving meaning
- **Fix grammar** — corrects grammar errors
- **Fix punctuation** — adds proper punctuation and capitalization
- **Custom instructions** — free-text system prompt per preset for fine-tuning AI behavior
- **Vocabulary preservation** — domain-specific terms (comma/newline-separated) are preserved verbatim during cleanup

Each option is configured per preset — you can have different cleanup rules for different contexts. When enabled, the transcription history shows both the original and cleaned text.

### Presets

Five built-in presets are included:

| Preset | Description |
|---|---|
| **General Professional** | Neutral business tone, clear and concise |
| **Technical / Engineering** | Preserves jargon, acronyms, and technical terminology |
| **Casual / Friendly** | Warm, approachable, conversational tone |
| **Email / Correspondence** | Professional email with greeting/sign-off, short paragraphs |
| **Simplified (8th Grade)** | Short sentences, common words, simple structures |

You can also create, duplicate, and delete custom presets. Each preset has its own toggle settings, custom system prompt, vocabulary list, and optional model override.

**Requirements:** An OpenAI API key. Enter it in Professional Mode Settings — the key is held in memory only by default and is **never** written to `settings.json` or any log file. Optionally check "Remember API key" to store it securely via Windows Credential Manager.

## Architecture

```
┌────────────────────────────────────────────┐
│       dictat0r.AI GUI  (PySide6 / Qt)      │
│ ┌────────────┐  ┌──────────────────┐       │
│ │ Hotkey Mgr │  │ Resource Monitor │       │
│ │ (sleep/    │  │ (RAM + VRAM +    │       │
│ │  wake safe)│  │  GPU temp)       │       │
│ └────────────┘  └──────────────────┘       │
├────────────────────────────────────────────┤
│   Engine: Cohere Transcribe (transformers) │
│   ┌───────────────────────────────────┐    │
│   │ Cohere Transcribe 03-2026         │    │
│   │ (2B params, ~5 GB VRAM, 14 langs) │    │
│   └────────────────┬──────────────────┘    │
│                    ▼                       │
│        NVIDIA GPU (CUDA) / CPU             │
├────────────────────────────────────────────┤
│   Professional Mode (optional)             │
│   ┌──────────────────────────────────────┐ │
│   │ ProPreset → TextProcessor →          │ │
│   │ OpenAI API                           │ │
│   │ (5 built-in + custom presets,        │ │
│   │  vocabulary, custom prompts)         │ │
│   └──────────────────────────────────────┘ │
└────────────────────────────────────────────┘
```

## Supported Languages

Cohere Transcribe supports 14 languages:

| Code | Language   | Code | Language    |
|------|------------|------|-------------|
| `en` | English    | `el` | Greek       |
| `fr` | French     | `nl` | Dutch       |
| `de` | German     | `pl` | Polish      |
| `it` | Italian    | `zh` | Chinese     |
| `es` | Spanish    | `ja` | Japanese    |
| `pt` | Portuguese | `ko` | Korean      |
| `vi` | Vietnamese | `ar` | Arabic      |

## Antivirus & Anti-Malware Notes

Some antivirus products may flag the PyInstaller-packaged `.exe` as suspicious. This is a known false positive common to all PyInstaller applications. You can:

1. Add `C:\Program Files\dictat0r.AI` to your antivirus exclusion list
2. The installer automatically configures Windows Defender exclusions

## License

[MIT](LICENSE)

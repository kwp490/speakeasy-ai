# dictat0r.AI — Native Windows Voice-to-Text

**Real-time speech transcription on Windows using NVIDIA GPUs.**

Press a hotkey, speak, and your transcribed text is pasted into the active window. GPU-accelerated, runs natively — no setup complexity.

## Download & Install

> **[Download dictator-AI-Setup-0.1.0.exe](https://github.com/kwp490/dictat0r.AI/releases/latest)**
>
> Double-click the installer and follow the prompts. No Python, no command line required.

The installer will:

1. Extract application files to `C:\Program Files\dictat0r.AI`
2. Download both speech engine models from HuggingFace
3. Create desktop and Start Menu shortcuts
4. Configure Windows Defender exclusions

**Requirements:** Windows 10/11 (64-bit), NVIDIA GPU (RTX 30-series or newer, 6+ GB VRAM recommended), NVIDIA Driver 525+.

## Features

- **Two speech engines**: IBM Granite 4.0 1B Speech and Cohere Transcribe 03-2026 — switch between them at any time
- **Professional Mode**: AI-powered text cleanup via OpenAI API with a preset system — 5 built-in presets, custom presets, domain vocabulary preservation, and per-preset model selection
- **Global hotkeys**: Start/stop recording from any application (configurable bindings)
- **Auto-paste**: Transcribed text goes directly to your active window
- **GPU-accelerated**: Both engines leverage NVIDIA CUDA for fast inference
- **Microphone selection**: Choose a specific input device or use the system default
- **Sleep/wake recovery**: Hotkeys automatically re-register after Windows resume from sleep
- **Single-instance guard**: Prevents multiple dictat0r.AI processes from running simultaneously
- **Real-time resource monitoring**: RAM, VRAM, and GPU temperature displayed in the diagnostics panel
- **Audio feedback**: Beep tones on recording start/stop
- **Runs natively on Windows** — single installer, no dependencies

## Source Install

For developers or users who want to run from source:

```powershell
# 1. Install uv
irm https://astral.sh/uv/install.ps1 | iex

# 2. Clone and install
git clone https://github.com/kwp490/dictat0r.AI.git
cd dictat0r.AI
uv sync

# 3. Download models and launch
uv run dictator download-model --engine granite
uv run dictator download-model --engine cohere
uv run dictator
```

Or use the automated source installer (requires admin):

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\installer\Install-Dictator-Source.ps1
```

## Settings

| Setting              | Default                                  | Description                                              |
|----------------------|------------------------------------------|----------------------------------------------------------|
| `engine`             | `granite`                                | Speech engine: `granite` or `cohere`                     |
| `model_path`         | `C:\Program Files\dictat0r.AI\models`    | Directory for model weights                              |
| `device`             | `cuda`                                   | Inference device: `cuda` or `cpu`                        |
| `language`           | `en`                                     | Language code                                            |
| `inference_timeout`  | `30`                                     | Max seconds per transcription                            |
| `auto_copy`          | `true`                                   | Auto-copy transcription to clipboard                     |
| `auto_paste`         | `true`                                   | Auto-paste via Ctrl+V after transcription                |
| `hotkeys_enabled`    | `true`                                   | Master toggle for global hotkeys                         |
| `hotkey_start`       | `ctrl+alt+p`                             | Start-recording hotkey                                   |
| `hotkey_stop`        | `ctrl+alt+l`                             | Stop/transcribe hotkey                                   |
| `hotkey_quit`        | `ctrl+alt+q`                             | Quit application hotkey                                  |
| `clear_logs_on_exit` | `true`                                   | Clear log files when the application exits               |
| `mic_device_index`   | `-1`                                     | Microphone device index (`-1` = system default)          |
| `sample_rate`        | `16000`                                  | Recording sample rate (Hz) — resampled to 16 kHz         |
| `silence_threshold`  | `0.0015`                                 | RMS threshold for silence detection                      |
| `silence_margin_ms`  | `500`                                    | Silence margin (ms) added around voiced regions          |
| `professional_mode`  | `false`                                  | Enable AI text cleanup (requires OpenAI API key)         |
| `pro_active_preset`  | `General Professional`                   | Active Professional Mode preset name                     |
| `store_api_key`      | `false`                                  | Persist API key in Windows Credential Manager            |

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
│   Engine Abstraction (transformers)        │
│   ┌──────────────┐ ┌───────────────────┐   │
│   │ Granite      │ │ Cohere Transcribe │   │
│   │ (1B params,  │ │ (2B params,       │   │
│   │  ~3 GB VRAM) │ │  ~5 GB VRAM)      │   │
│   └──────┬───────┘ └────────┬──────────┘   │
│          │                  │              │
│          ▼                  ▼              │
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

## Model Comparison

|                      | IBM Granite 4.0 1B Speech                        | Cohere Transcribe 03-2026                         |
| -------------------- | ------------------------------------------------ | ------------------------------------------------- |
| **HuggingFace**      | `ibm-granite/granite-4.0-1b-speech`              | `CohereLabs/cohere-transcribe-03-2026`            |
| **Parameters**       | 1B                                               | 2B                                                |
| **VRAM**             | ~3 GB                                            | ~5 GB                                             |
| **WER**              | 5.52                                             | 5.42                                              |
| **Languages**        | 7 (en, fr, de, es, pt, ja)                       | 14 (en, fr, de, it, es, pt, el, nl, pl, zh, ja, ko, vi, ar) |
| **License**          | Apache 2.0                                       | Apache 2.0                                        |
| **Speed**            | Very fast (smaller model)                        | Fast                                              |

## Antivirus & Anti-Malware Notes

Some antivirus products may flag the PyInstaller-packaged `.exe` as suspicious. This is a known false positive common to all PyInstaller applications. You can:

1. Add `C:\Program Files\dictat0r.AI` to your antivirus exclusion list
2. The installer automatically configures Windows Defender exclusions

## License

Apache License 2.0. See [LICENSE](LICENSE).

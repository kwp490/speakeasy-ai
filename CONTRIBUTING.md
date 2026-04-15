# Contributing to dictat0r.AI

## Dev Setup

```bash
# Clone and install all dependencies (including dev tools)
git clone https://github.com/kwp490/dictat0r.AI.git
cd dictat0r.AI
uv sync --extra dev
```

## Running Tests

```bash
uv run pytest
```

## Compile Check

```bash
uv run python -m compileall dictator
```

## Verify Engine Availability

```bash
uv run python -c "from dictator.engine import ENGINES; print(list(ENGINES.keys()))"
```

## Code Style

- Use type hints where practical
- Follow existing patterns in the codebase
- Keep imports sorted (stdlib → third-party → local)

## Architecture Notes

- **Thread safety**: Clipboard writes (`set_clipboard_text`) must only happen on the main Qt thread. Worker threads emit signals; connected slots run on the main thread.
- **Audio format**: All engine calls receive 1D float32 mono numpy arrays. Audio is resampled to 16 kHz before engine input, regardless of recording sample rate.
- **Single process**: Both engines (Granite and Cohere) run in-process via HuggingFace `transformers`. No subprocess bridge needed.
- **GPU cleanup**: `unload()` methods must explicitly `del` the model, call `gc.collect()`, and `torch.cuda.empty_cache()` to free VRAM.
- **Professional Mode**: Text cleanup runs on a `Worker` thread via the OpenAI API (no GPU conflict). The API key is held in memory on `MainWindow._api_key` — it must **never** be logged, printed, or serialized to `settings.json`. Use `_sanitize_error()` from `text_processor.py` when handling API exceptions.
- **Preset system**: Professional Mode uses `ProPreset` dataclass instances. Five built-in presets are always available; user presets are stored as JSON files in `config/presets/`. Built-in presets cannot be deleted.
- **Sleep/wake recovery**: `HotkeyManager.re_register()` is called on `WM_POWERBROADCAST` / `PBT_APMRESUMEAUTOMATIC` to restore keyboard hooks invalidated during sleep.
- **Single-instance guard**: A Windows named mutex (`Global\Dictator0rAIMutex`) prevents multiple processes.

## Building the Binary

```bash
uv sync --extra dev
uv run pyinstaller dictator.spec
```

## Building the Installer

After building the binary, compile the Inno Setup installer:

```bash
# Requires Inno Setup 6.x — https://jrsoftware.org/isdl.php
iscc installer\dictator-setup.iss
# Output: installer/Output/dictator-AI-Setup-0.1.0.exe
```

Or run the combined build script:

```powershell
.\installer\Build-Installer.ps1
```

## Filing Issues

Please use the [GitHub Issues](https://github.com/kwp490/dictat0r.AI/issues) page. Include:

- dictat0r.AI version
- Windows version
- GPU model and driver version
- Steps to reproduce
- Relevant log output from `logs/dictator.log`

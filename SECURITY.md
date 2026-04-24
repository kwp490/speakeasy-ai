# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in SpeakEasy AI, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, email the maintainer directly or use [GitHub's private vulnerability reporting](https://github.com/kwp490/SpeakEasyAI/security/advisories/new).

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response timeline

- **Acknowledgment**: within 48 hours
- **Initial assessment**: within 1 week
- **Fix or mitigation**: depends on severity, typically within 2 weeks for critical issues

## Known Security Considerations

- **Hotkeys**: Global hotkeys are registered via the Win32 `RegisterHotKey` API — only the configured chord is delivered to the application. No global keyboard hook (`SetWindowsHookEx`) is installed.
- **Administrator privileges**: The installer requires elevation to write to `C:\Program Files\SpeakEasy AI`.
- **Defender exclusions**: The GUI installer automatically adds Windows Defender exclusions for the install directory and `speakeasy.exe` to prevent false positives.
- **`uv.exe` false positives**: Some anti-malware tools (e.g. Malwarebytes) may quarantine `uv.exe` during source installs. If this happens, restore it and add it to your allow list. [uv](https://github.com/astral-sh/uv) is a widely used open-source Python package manager.
- **API key handling (Professional Mode)**: OpenAI API keys entered in Settings are held in memory only by default and are **never** written to `settings.json` or any log file. If "Remember API key" is enabled, the key is stored via Windows Credential Manager (protected by Windows DPAPI encryption). API keys are never displayed in the UI log panel, and all error messages are sanitized to redact key content.
- **Single-instance mutex**: A Windows named mutex (`Global\SpeakEasyAIMutex`) prevents multiple SpeakEasy AI processes from running simultaneously, avoiding resource conflicts.


## Privacy & Data Handling

**Audio**: Recorded audio is processed entirely in memory as numpy arrays and discarded after transcription. No temporary files are written to disk during processing.

**Transcriptions**: Transcribed text is displayed in the UI and optionally copied to the clipboard. Transcription content is **not** written to log files — only character counts are logged. When **Professional Mode** is enabled, transcribed text is sent to the OpenAI API for cleanup (see Network below).

**Logs**: Application logs are stored at `%ProgramData%\SpeakEasy AI\logs\` as rotating plaintext files (~6 MB max). Logs contain diagnostic information (engine status, GPU metrics, error traces) but no speech content. Logs are cleared on exit by default (`clear_logs_on_exit: true`).

**Network**: SpeakEasy AI makes network requests **only** in two scenarios:

1. **Model downloads** — to HuggingFace Hub (authentication required for the gated Cohere Transcribe model) when downloading the speech engine model.
2. **Professional Mode** (when enabled) — transcribed text is sent to the OpenAI API (`api.openai.com`) for tone, grammar, and punctuation cleanup. This requires a user-provided API key and is **opt-in only** — disabled by default. No audio data is sent; only the transcribed text string is transmitted.

No telemetry, analytics, or usage data is collected or transmitted.

**Hotkeys**: Global hotkeys use the Win32 `RegisterHotKey` API — only the configured chord is delivered to the application. No global keyboard hook is installed and no keystrokes are captured or logged.

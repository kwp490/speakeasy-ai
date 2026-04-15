# ─────────────────────────────────────────────────────────────────────────────
# Cohere Transcribe Model Setup
#
# This script guides the user through downloading the gated Cohere
# Transcribe model from HuggingFace.  It is launched by the main
# dictat0r.AI installer when the user selects "Granite + Cohere".
#
# The HuggingFace token is used for this single download only.
# It is NOT stored anywhere — not in settings, not on disk, not in
# environment variables.
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = 'Stop'

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Exe    = Join-Path $AppDir 'dictator.exe'

function Write-Banner {
    Write-Host ''
    Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Cyan
    Write-Host '  Cohere Transcribe — Model Setup' -ForegroundColor Cyan
    Write-Host '════════════════════════════════════════════════════════════════' -ForegroundColor Cyan
    Write-Host ''
}

function Write-Instructions {
    Write-Host 'Cohere Transcribe requires a free HuggingFace account.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '  Step 1: Create a free account at' -ForegroundColor White
    Write-Host '          https://huggingface.co/join' -ForegroundColor Green
    Write-Host ''
    Write-Host '  Step 2: Go to the model page and click "Agree and access repository"' -ForegroundColor White
    Write-Host '          https://huggingface.co/CohereLabs/cohere-transcribe-03-2026' -ForegroundColor Green
    Write-Host ''
    Write-Host '  Step 3: Create an access token (Read permission is sufficient)' -ForegroundColor White
    Write-Host '          https://huggingface.co/settings/tokens' -ForegroundColor Green
    Write-Host ''
}

function Start-Download {
    while ($true) {
        Write-Host ''
        $token = Read-Host 'Paste your HuggingFace access token (or type "skip" to cancel)'

        if ($token -eq 'skip' -or $token -eq '') {
            Write-Host ''
            Write-Host 'Skipped. You can run this setup later:' -ForegroundColor Yellow
            Write-Host "  $Exe download-model --engine cohere --token <YOUR_TOKEN>" -ForegroundColor Gray
            return 1
        }

        Write-Host ''
        Write-Host 'Downloading Cohere model — this may take several minutes...' -ForegroundColor Cyan

        $process = Start-Process -FilePath $Exe `
            -ArgumentList "download-model --engine cohere --token $token" `
            -Wait -PassThru -NoNewWindow

        switch ($process.ExitCode) {
            0 {
                Write-Host ''
                Write-Host 'Cohere model downloaded successfully!' -ForegroundColor Green
                return 0
            }
            2 {
                Write-Host ''
                Write-Host 'Authentication failed.' -ForegroundColor Red
                Write-Host 'Possible causes:' -ForegroundColor Yellow
                Write-Host '  - Invalid or expired token' -ForegroundColor Yellow
                Write-Host '  - You have not accepted the license at:' -ForegroundColor Yellow
                Write-Host '    https://huggingface.co/CohereLabs/cohere-transcribe-03-2026' -ForegroundColor Green
                Write-Host ''
                Write-Host 'Would you like to try again?' -ForegroundColor White
            }
            default {
                Write-Host ''
                Write-Host "Download failed (exit code $($process.ExitCode))." -ForegroundColor Red
                Write-Host 'This may be a network error. Would you like to try again?' -ForegroundColor White
            }
        }

        $retry = Read-Host '[R]etry or [S]kip? (R/S)'
        if ($retry -ne 'R' -and $retry -ne 'r') {
            Write-Host ''
            Write-Host 'Skipped. You can run this setup later:' -ForegroundColor Yellow
            Write-Host "  $Exe download-model --engine cohere --token <YOUR_TOKEN>" -ForegroundColor Gray
            return 1
        }
    }
}

# ── Main ─────────────────────────────────────────────────────────────────────

Write-Banner
Write-Instructions
$exitCode = Start-Download

Write-Host ''
Write-Host 'Press any key to close...' -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')

exit $exitCode

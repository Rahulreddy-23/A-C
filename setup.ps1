<#
Set up DHF Automation on Windows.

Run it from the A-C folder in PowerShell:
    powershell -ExecutionPolicy Bypass -File .\setup.ps1
    powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Start
    powershell -ExecutionPolicy Bypass -File .\setup.ps1 -NativeTls   (company HTTPS inspection)

It installs uv with winget if uv is missing, installs Python and the libraries (uv sync),
then creates .env with a key for saved PATs (uv run dhf setup). With -Start it then opens
the workspace. Running it again is safe: it never replaces an existing .env key.
#>
param(
    [switch]$Start,
    [switch]$NativeTls,
    [string]$ProjectId = 'my-project'
)
# No global ErrorActionPreference = Stop: Windows PowerShell 5.1 can treat uv's progress
# output on stderr as an error. Each step checks its own result instead.
Set-Location -LiteralPath $PSScriptRoot -ErrorAction Stop
# Trust the Windows certificate store, for networks that inspect HTTPS.
if ($NativeTls) { $env:UV_NATIVE_TLS = 'true' }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host 'uv is not installed. Installing it with winget...'
        winget install --id astral-sh.uv -e
        # Pick up the new PATH entry without opening a new window.
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'uv was not found. Install it (https://docs.astral.sh/uv/getting-started/installation/), open a new PowerShell window and run this script again.'
    }
}

Write-Host 'Installing Python and the project libraries (uv sync)...'
uv sync
if ($LASTEXITCODE -ne 0) {
    throw 'uv sync failed. On a company network that inspects HTTPS, run this script again with -NativeTls.'
}

uv run dhf setup
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Start) {
    Write-Host 'Starting the workspace. Keep this window open; press Ctrl+C to stop.'
    uv run dhf serve --project-id $ProjectId
}

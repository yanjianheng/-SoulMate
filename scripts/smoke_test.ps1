param(
    [string]$Model = "qwen3:8b-q4_K_M",
    [string]$TestUser = "smoke",
    [string]$ProjectDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$PassCount = 0
$FailCount = 0

function Write-Step([string]$Message) {
    Write-Host ("`n== {0} ==" -f $Message) -ForegroundColor Cyan
}

function Add-Pass([string]$Name) {
    $script:PassCount++
    Write-Host ("[ok] {0}" -f $Name) -ForegroundColor Green
}

function Add-Fail([string]$Name, [string]$Detail = "") {
    $script:FailCount++
    Write-Host ("[fail] {0}" -f $Name) -ForegroundColor Red
    if (-not [string]::IsNullOrWhiteSpace($Detail)) {
        Write-Host $Detail
    }
}

function Invoke-Test([string]$Name, [scriptblock]$Action) {
    try {
        & $Action
        Add-Pass $Name
    } catch {
        Add-Fail $Name $_.Exception.Message
    }
}

function Invoke-TestMatch([string]$Name, [string]$Pattern, [scriptblock]$Action) {
    try {
        $output = & $Action 2>&1 | Out-String
        if ($output -match $Pattern) {
            Add-Pass $Name
        } else {
            Add-Fail $Name ("pattern not found: {0}`noutput:`n{1}" -f $Pattern, $output)
        }
    } catch {
        Add-Fail $Name $_.Exception.Message
    }
}

Write-Step "Project"
Write-Host ("[info] project: {0}" -f $ProjectDir)
if (-not (Test-Path (Join-Path $ProjectDir "app\main.py"))) {
    throw "app/main.py not found. Run under project root."
}
Set-Location $ProjectDir

$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

if ([string]::IsNullOrWhiteSpace($env:OLLAMA_HOST)) {
    $env:OLLAMA_HOST = "127.0.0.1:11434"
    Write-Host ("[info] OLLAMA_HOST defaulted to {0}" -f $env:OLLAMA_HOST)
}

$env:SOULMATE_SMOKE_USER = $TestUser

Write-Step "Python Environment"
Invoke-Test "python exists" { & $Python -V | Out-Null }
Invoke-Test "import ollama package" { & $Python -c "import ollama" | Out-Null }

Write-Step "Ollama API"
Invoke-Test "GET /api/tags" {
    $null = Invoke-RestMethod -Uri ("http://{0}/api/tags" -f $env:OLLAMA_HOST) -Method Get -TimeoutSec 10
}

Write-Step "CLI Basics"
Invoke-Test "python -m app.main --help" {
    & $Python -m app.main --help | Out-Null
}
Invoke-Test "python init_db.py" {
    & $Python init_db.py | Out-Null
}

Write-Step "Single Ask"
Invoke-TestMatch "single ask returns AI or empty warning" "AI>|\\[warn\\] empty response from model" {
    & $Python -m app.main --model $Model --user $TestUser --ask "This is a smoke test, reply briefly."
}

Write-Step "DB Sanity"
Invoke-Test "tables exist" {
    @'
from app.db.sqlite_store import get_connection
required = {"users", "sessions", "messages"}
with get_connection() as conn:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
tables = {r[0] for r in rows}
missing = required - tables
if missing:
    raise SystemExit(f"missing tables: {sorted(missing)}")
print("tables ok")
'@ | & $Python -
}

Invoke-Test "latest session exists for smoke user" {
    @'
import os
from app.db.sqlite_store import get_connection, get_or_create_user, get_latest_session_id
test_user = os.getenv("SOULMATE_SMOKE_USER", "smoke")
with get_connection() as conn:
    uid = get_or_create_user(conn, test_user)
    sid = get_latest_session_id(conn, uid)
if sid is None:
    raise SystemExit("no latest session")
print(f"latest session: {sid}")
'@ | & $Python -
}

Write-Step "Summary"
Write-Host ("[summary] pass={0} fail={1}" -f $PassCount, $FailCount)
if ($FailCount -gt 0) {
    exit 1
}
exit 0

